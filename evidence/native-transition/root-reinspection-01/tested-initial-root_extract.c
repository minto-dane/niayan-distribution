/* SPDX-License-Identifier: BSD-3-Clause */
#define _GNU_SOURCE
#include <archive.h>
#include <archive_entry.h>
#include <sodium.h>
#include <signal.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <locale.h>
#include <linux/audit.h>
#include <linux/capability.h>
#include <linux/filter.h>
#include <linux/openat2.h>
#include <sys/sysmacros.h>
#include <linux/seccomp.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/time.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>
#include "tar_clocks.h"

/* Internal, non-setuid worker. FD 3 is an authorized uncompressed root tar;
 * FD 4 is its private, root-owned staging parent containing an empty "root".
 * FD 6 retains the caller's actual writer reservation throughout extraction.
 * The invoking service owns admission and publication; successful extraction
 * never publishes a generation. No scripts, executable children or sockets. */
#define MAX_BYTES (UINT64_C(8) * 1024 * 1024 * 1024)
#define MAX_ENTRIES 524288U
struct input {
    unsigned char buffer[65536];
    crypto_hash_sha256_state hash;
    uint64_t size, offset, deadline;
};
static int rechecking;
static uint64_t now_ms(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_BOOTTIME, &t) || t.tv_sec < 0) return UINT64_MAX;
    return (uint64_t)t.tv_sec * 1000 + (uint64_t)t.tv_nsec / 1000000;
}
static int fail(const char *reason) {
    /* Fixed language-neutral diagnostics; archive-controlled text is not emitted. */
    fprintf(stderr, "{\"result\":\"failed\",\"reason\":\"%s\"}\n", reason);
    return 1;
}
static int number(const char *s, uint64_t *n) {
    if (!s || !*s || (*s == '0' && s[1])) return -1;
    uint64_t value = 0;
    for (; *s; ++s) {
        if (*s < '0' || *s > '9' || value > (UINT64_MAX - (*s - '0')) / 10) return -1;
        value = value * 10 + (*s - '0');
    }
    *n = value; return 0;
}
static int empty_directory(int fd) {
    int copy = openat(fd, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    if (copy < 0) return -1;
    DIR *d = fdopendir(copy); if (!d) { close(copy); return -1; }
    struct dirent *e; int result = 0;
    errno = 0;
    while ((e = readdir(d))) {
        if (strcmp(e->d_name, ".") && strcmp(e->d_name, "..")) { result = -1; break; }
    }
    if (errno) result = -1;
    closedir(d); return result;
}
static la_ssize_t read_archive(struct archive *a, void *opaque, const void **data) {
    struct input *in = opaque;
    if (now_ms() >= in->deadline) { archive_set_error(a, ETIMEDOUT, "deadline"); return -1; }
    if (in->offset == in->size) return 0;
    size_t length = sizeof(in->buffer);
    if (in->size - in->offset < length) length = (size_t)(in->size - in->offset);
    ssize_t got;
    do { got = pread(3, in->buffer, length, (off_t)in->offset); } while (got < 0 && errno == EINTR);
    if (got <= 0) { archive_set_error(a, EIO, "input"); return -1; }
    crypto_hash_sha256_update(&in->hash, in->buffer, (unsigned long long)got);
    in->offset += (uint64_t)got; *data = in->buffer; return got;
}
static int restrict_process(uint64_t deadline) {
    struct rlimit core = {0, 0}, memory = {512 * 1024 * 1024, 512 * 1024 * 1024};
    struct rlimit files = {64, 64}, filesize = {MAX_BYTES, MAX_BYTES};
    uint64_t sample = now_ms(); if (sample >= deadline) return -1;
    uint64_t remaining = deadline - sample;
    struct itimerval timer = {.it_value = {.tv_sec = (time_t)(remaining / 1000),
        .tv_usec = (suseconds_t)((remaining % 1000) * 1000)}};
    if (setitimer(ITIMER_REAL, &timer, NULL) || setrlimit(RLIMIT_NOFILE, &files) || setrlimit(RLIMIT_FSIZE, &filesize) ||
        setrlimit(RLIMIT_CORE, &core) || setrlimit(RLIMIT_AS, &memory) ||
        prctl(PR_SET_DUMPABLE, 0) || prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)) return -1;
    /* Retain only filesystem metadata capabilities after entering the empty root. */
    uint64_t keep = (UINT64_C(1) << CAP_CHOWN) | (UINT64_C(1) << CAP_DAC_OVERRIDE) |
        (UINT64_C(1) << CAP_FOWNER) | (UINT64_C(1) << CAP_FSETID) |
        (UINT64_C(1) << CAP_MKNOD) | (UINT64_C(1) << CAP_SETFCAP);
    struct __user_cap_header_struct h = {_LINUX_CAPABILITY_VERSION_3, 0};
    struct __user_cap_data_struct d[2] = {{0}};
    for (unsigned i = 0; i < 2; ++i) d[i].effective = d[i].permitted = (uint32_t)(keep >> (32 * i));
    if (syscall(SYS_capset, &h, d)) return -1;
    /* This filter supplements chroot, closed outside directory descriptors,
     * private parent ownership and mandatory nodev/nosuid/noexec storage. */
#define GUARD_LEASE(n) BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, (n), 0, 4), \
    BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[0])), \
    BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, 6, 0, 1), \
    BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS), \
    BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr))
#define REFUSE(n) BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, (n), 0, 1), BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS)
#if defined(__x86_64__)
#define WORKER_ARCH AUDIT_ARCH_X86_64
#elif defined(__aarch64__)
#define WORKER_ARCH AUDIT_ARCH_AARCH64
#else
#error "Define and validate the native syscall ABI before building this worker"
#endif
    struct sock_filter filter[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, WORKER_ARCH, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
#if defined(__x86_64__)
        BPF_JUMP(BPF_JMP | BPF_JSET | BPF_K, 0x40000000U, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
#endif
        /* The outside reservation FD is retained solely as a lock, not as a
         * writable inode capability. It cannot be closed, copied or mutated. */
        GUARD_LEASE(SYS_flock), GUARD_LEASE(SYS_close), GUARD_LEASE(SYS_dup), GUARD_LEASE(SYS_fcntl),
        GUARD_LEASE(SYS_write), GUARD_LEASE(SYS_writev), GUARD_LEASE(SYS_pwrite64),
        GUARD_LEASE(SYS_pwritev), GUARD_LEASE(SYS_pwritev2), GUARD_LEASE(SYS_ftruncate),
        GUARD_LEASE(SYS_fallocate), GUARD_LEASE(SYS_fchmod), GUARD_LEASE(SYS_fchown),
        GUARD_LEASE(SYS_fchmodat), GUARD_LEASE(SYS_fchownat), GUARD_LEASE(SYS_utimensat),
        GUARD_LEASE(SYS_fsetxattr), GUARD_LEASE(SYS_fremovexattr), GUARD_LEASE(SYS_ioctl),
        GUARD_LEASE(SYS_linkat),
#ifdef SYS_fchmodat2
        GUARD_LEASE(SYS_fchmodat2),
#endif
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_mmap, 0, 4),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[4])),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, 6, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        REFUSE(SYS_dup3), REFUSE(SYS_close_range), REFUSE(SYS_sendfile),
        REFUSE(SYS_splice), REFUSE(SYS_vmsplice), REFUSE(SYS_tee), REFUSE(SYS_copy_file_range),
#ifdef SYS_dup2
        REFUSE(SYS_dup2),
#endif
        REFUSE(SYS_execve), REFUSE(SYS_execveat), REFUSE(SYS_mount), REFUSE(SYS_umount2),
        REFUSE(SYS_chroot), REFUSE(SYS_pivot_root), REFUSE(SYS_unshare), REFUSE(SYS_setns),
        REFUSE(SYS_socket), REFUSE(SYS_socketpair), REFUSE(SYS_ptrace), REFUSE(SYS_bpf),
#ifdef SYS_fork
        REFUSE(SYS_fork),
#endif
#ifdef SYS_vfork
        REFUSE(SYS_vfork),
#endif
        REFUSE(SYS_keyctl), REFUSE(SYS_clone), REFUSE(SYS_clone3),
        REFUSE(SYS_io_uring_setup), REFUSE(SYS_io_uring_enter), REFUSE(SYS_io_uring_register),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW)
    };
#undef REFUSE
#undef GUARD_LEASE
    struct sock_fprog program = {(unsigned short)(sizeof(filter) / sizeof(filter[0])), filter};
    return prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &program);
}
struct retained {
    char *path;
    struct stat observed;
    int hardlink;
    struct archive_entry *entry;
    unsigned char content[crypto_hash_sha256_BYTES];
};
static int same_acl(struct archive_entry *expected, struct archive_entry *actual) {
    int types = ARCHIVE_ENTRY_ACL_TYPE_ACCESS | ARCHIVE_ENTRY_ACL_TYPE_DEFAULT |
        ARCHIVE_ENTRY_ACL_TYPE_NFS4;
    int count = archive_entry_acl_reset(expected, types);
    if (count != archive_entry_acl_reset(actual, types)) return -1;
    int type, perm, tag, qualifier; const char *name;
    while (archive_entry_acl_next(expected, types, &type, &perm, &tag, &qualifier, &name) == ARCHIVE_OK) {
        int at, ap, ag, aq, found = 0; const char *an;
        archive_entry_acl_reset(actual, types);
        while (archive_entry_acl_next(actual, types, &at, &ap, &ag, &aq, &an) == ARCHIVE_OK)
            if (type == at && perm == ap && tag == ag && qualifier == aq) found = 1;
        if (!found) return -1;
    }
    return 0;
}
static int same_declared_xattrs(struct archive_entry *expected, struct archive_entry *actual) {
    const char *name; const void *value; size_t size;
    archive_entry_xattr_reset(expected);
    while (archive_entry_xattr_next(expected, &name, &value, &size) == ARCHIVE_OK) {
        const char *an; const void *av; size_t as; int found = 0;
        archive_entry_xattr_reset(actual);
        while (archive_entry_xattr_next(actual, &an, &av, &as) == ARCHIVE_OK)
            if (!strcmp(name, an) && size == as && !memcmp(value, av, size)) found = 1;
        if (!found) return -1;
    }
    return 0;
}
/* libarchive stores ACL_GROUP_OBJ in its entry mode. POSIX st_mode uses
 * ACL_MASK for the group class when present. Do not set the entry's mode:
 * doing so would overwrite the distinct original ACL_GROUP_OBJ permissions. */
static int inode_mode(struct archive_entry *entry, mode_t *mode) {
    int count = archive_entry_acl_reset(entry, ARCHIVE_ENTRY_ACL_TYPE_ACCESS);
    if (count < 0 || count > 1024) return -1;
    *mode = archive_entry_mode(entry);
    int type, perm, tag, qualifier, mask = 0; const char *name;
    for (int i = 0; i < count; ++i) {
        if (archive_entry_acl_next(entry, ARCHIVE_ENTRY_ACL_TYPE_ACCESS,
            &type, &perm, &tag, &qualifier, &name) != ARCHIVE_OK) return -1;
        if (type == ARCHIVE_ENTRY_ACL_TYPE_ACCESS && tag == ARCHIVE_ENTRY_ACL_MASK) {
            if (mask++ || perm < 0 || perm > 7) return -1;
            *mode = (*mode & ~(mode_t)0070) | (mode_t)(perm << 3);
        }
    }
    return 0;
}
static int verify(struct archive *disk, struct retained *record, struct input *in) {
    struct archive_entry *expected = record->entry;
    const char *path = archive_entry_pathname(expected), *hard = archive_entry_hardlink(expected);
    struct stat st; mode_t expected_mode;
    if (inode_mode(expected, &expected_mode)) return -3;
    if (!path || now_ms() >= in->deadline || lstat(path, &st)) return -1;
    record->observed = st;
    if (hard) {
        /* Hardlink inode attributes belong to the target entry, not its alias header. */
        struct stat target;
        return lstat(hard, &target) || st.st_dev != target.st_dev || st.st_ino != target.st_ino ? -2 : 0;
    }
    if ((la_int64_t)st.st_uid != archive_entry_uid(expected) || (la_int64_t)st.st_gid != archive_entry_gid(expected) ||
        st.st_mode != expected_mode ||
        (archive_entry_mtime_is_set(expected) && (st.st_mtim.tv_sec != archive_entry_mtime(expected) ||
            st.st_mtim.tv_nsec != archive_entry_mtime_nsec(expected))) ||
        (archive_entry_atime_is_set(expected) && (st.st_atim.tv_sec != archive_entry_atime(expected) ||
            st.st_atim.tv_nsec != archive_entry_atime_nsec(expected)))) return -3;
    if ((S_ISCHR(st.st_mode) || S_ISBLK(st.st_mode)) && st.st_rdev != archive_entry_rdev(expected)) return -4;
    struct archive_entry *observed = archive_entry_new();
    if (!observed) return -5;
    archive_entry_copy_pathname(observed, path);
    int error = archive_read_disk_entry_from_file(disk, observed, -1, &st) == ARCHIVE_OK ? 0 : -6;
    unsigned long set, clear, actual_set, actual_clear;
    archive_entry_fflags(expected, &set, &clear); archive_entry_fflags(observed, &actual_set, &actual_clear);
    if ((actual_set & set) != set || (actual_set & clear)) error = -7;
    if (same_acl(expected, observed)) error = -8;
    if (same_declared_xattrs(expected, observed) || (rechecking &&
        archive_entry_xattr_count(expected) != archive_entry_xattr_count(observed))) error = -9;
    if (S_ISLNK(st.st_mode)) {
        const char *want = archive_entry_symlink(expected), *got = archive_entry_symlink(observed);
        if (!want || !got || strcmp(want, got)) error = -10;
        /* Reading a link can change its atime; restore the sampled times. */
        struct timespec times[2] = {st.st_atim, st.st_mtim};
        if (!rechecking && utimensat(AT_FDCWD, path, times, AT_SYMLINK_NOFOLLOW)) error = -11;
    }
    archive_entry_free(observed);
    if (error) return error;
    if (S_ISREG(st.st_mode)) {
        if (st.st_size != archive_entry_size(expected)) return -1;
        int fd = open(path, O_RDONLY | O_NOFOLLOW | O_NOATIME | O_CLOEXEC);
        if (fd < 0) return -1;
        crypto_hash_sha256_state hash; crypto_hash_sha256_init(&hash);
        unsigned char buffer[65536], digest[crypto_hash_sha256_BYTES]; ssize_t n; uint64_t total = 0;
        while ((n = read(fd, buffer, sizeof(buffer))) > 0) {
            total += (uint64_t)n;
            if (total > in->size || now_ms() >= in->deadline) { close(fd); return -1; }
            crypto_hash_sha256_update(&hash, buffer, (unsigned long long)n);
        }
        close(fd); if (n < 0 || total != (uint64_t)st.st_size) return -1;
        crypto_hash_sha256_final(&hash, digest);
        if (sodium_memcmp(digest, record->content, sizeof(digest))) return -1;
    }
    return 0;
}
/* Reinspection is confined to an independently frozen read-only mount. The
 * service/CAS reservations exclude cooperating writers and mount changes.
 * Each path crosses no symlink or child mount; an exact namespace and inode
 * link count check rejects both extra entries and undeclared hardlinks. */
static char *normal_path(const char *name) {
    if (!name || !*name || strlen(name) >= PATH_MAX) return NULL;
    if (!strcmp(name, ".") || !strcmp(name, "./")) return strdup(".");
    if (!strncmp(name, "./", 2)) name += 2;
    char *path = strdup(name); if (!path) return NULL;
    size_t length = strlen(path);
    if (length && path[length - 1] == '/') path[--length] = 0;
    const char *start = path;
    for (size_t i = 0; i <= length; ++i) {
        if (path[i] && path[i] != '/') continue;
        size_t n = (size_t)(path + i - start);
        if (!n || (n == 1 && start[0] == '.') || (n == 2 && start[0] == '.' && start[1] == '.')) {
            free(path); return NULL;
        }
        start = path + i + 1;
    }
    return path;
}
static int confined(const char *path, int directory) {
    struct open_how how = {.flags = (uint64_t)(directory ? O_RDONLY | O_DIRECTORY | O_NOATIME : O_PATH) |
        O_CLOEXEC | O_NOFOLLOW, .resolve = RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_XDEV};
    return (int)syscall(SYS_openat2, 5, path, &how, sizeof(how));
}
static int by_path(const void *left, const void *right) {
    const struct retained *a = *(struct retained * const *)left, *b = *(struct retained * const *)right;
    return strcmp(a->path, b->path);
}
static int by_inode(const void *left, const void *right) {
    const struct stat *a = &(*(struct retained * const *)left)->observed;
    const struct stat *b = &(*(struct retained * const *)right)->observed;
    if (a->st_dev != b->st_dev) return a->st_dev < b->st_dev ? -1 : 1;
    return a->st_ino == b->st_ino ? 0 : a->st_ino < b->st_ino ? -1 : 1;
}
static int complete_tree(struct retained *records, size_t count, struct input *in) {
    struct retained **index = calloc(count, sizeof(*index));
    if (!index) return -1;
    for (size_t i = 0; i < count; ++i) index[i] = &records[i];
    qsort(index, count, sizeof(*index), by_path);
    for (size_t i = 1; i < count; ++i) if (!strcmp(index[i-1]->path, index[i]->path)) { free(index); return -1; }
    size_t children = 0;
    for (size_t i = 0; i < count; ++i) {
        if (now_ms() >= in->deadline) { free(index); return -1; }
        if (!S_ISDIR(records[i].observed.st_mode)) continue;
        int fd = confined(records[i].path, 1); if (fd < 0) { free(index); return -1; }
        DIR *directory = fdopendir(fd);
        if (!directory) { close(fd); free(index); return -1; }
        struct dirent *entry; int failed = 0; errno = 0;
        while ((entry = readdir(directory))) {
            if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
            char path[PATH_MAX];
            int length = !strcmp(records[i].path, ".") ? snprintf(path, sizeof(path), "%s", entry->d_name) :
                snprintf(path, sizeof(path), "%s/%s", records[i].path, entry->d_name);
            struct retained key = {.path = path}; struct retained *needle = &key;
            if (length < 0 || (size_t)length >= sizeof(path) || ++children >= count ||
                now_ms() >= in->deadline || !bsearch(&needle, index, count, sizeof(*index), by_path)) { failed = 1; break; }
            errno = 0;
        }
        if (errno) failed = 1;
        closedir(directory); if (failed) { free(index); return -1; }
    }
    if (children != count - 1) { free(index); return -1; }
    qsort(index, count, sizeof(*index), by_inode);
    for (size_t first = 0; first < count;) {
        size_t end = first + 1, originals = !index[first]->hardlink;
        while (end < count && !by_inode(&index[first], &index[end])) { originals += !index[end]->hardlink; ++end; }
        if (!S_ISDIR(index[first]->observed.st_mode) &&
            (originals != 1 || index[first]->observed.st_nlink != end - first)) { free(index); return -1; }
        first = end;
    }
    free(index); return 0;
}
int main(int argc, char **argv) {
    struct input in = {0}; uint64_t count_limit, supplied[3];
    unsigned char expected[crypto_hash_sha256_BYTES], actual[crypto_hash_sha256_BYTES];
    size_t decoded = 0; struct stat parent, root, original; struct statvfs fs;
    if (geteuid() != 0 || getuid() != 0) return fail("privilege");
    rechecking = argc == 9 && !strcmp(argv[8], "--verify");
    if ((argc != 8 && !rechecking) || strlen(argv[1]) != 64 || sodium_init() < 0 ||
        sodium_hex2bin(expected, sizeof(expected), argv[1], 64, NULL, &decoded, NULL) || decoded != sizeof(expected) ||
        number(argv[2], &in.size) || in.size < 1024 || in.size > MAX_BYTES || in.size % 512 ||
        number(argv[3], &count_limit) || !count_limit || count_limit > MAX_ENTRIES ||
        number(argv[4], &in.deadline) || in.deadline <= now_ms() || in.deadline - now_ms() > 600000)
        return fail("arguments");
    for (unsigned i = 0; i < 3; ++i)
        if (number(argv[5 + i], &supplied[i]) || supplied[i] < 3 || supplied[i] > INT_MAX) return fail("descriptors");
    int copies[3];
    for (unsigned i = 0; i < 3; ++i) {
        copies[i] = fcntl((int)supplied[i], F_DUPFD_CLOEXEC, 10);
        if (copies[i] < 0) return fail("descriptors");
    }
    if (dup2(copies[0], 3) < 0 || dup2(copies[1], 4) < 0 || dup2(copies[2], 6) < 0) return fail("descriptors");
    for (unsigned i = 0; i < 3; ++i) close(copies[i]);
    struct stat reservation;
    if (fstat(6, &reservation) || !S_ISREG(reservation.st_mode) || reservation.st_nlink != 1 ||
        (fcntl(6, F_GETFL) & O_ACCMODE) != O_RDWR || flock(6, LOCK_EX | LOCK_NB)) return fail("reservation");
    pid_t parent_pid = getppid();
    if (prctl(PR_SET_PDEATHSIG, SIGKILL) || getppid() != parent_pid) return fail("parent");
    /* Filenames are filesystem bytes. Fix PAX UTF-8 decoding independently of
     * the user's UI locale; binary tar names remain binary. Load locale data
     * before entering the empty root and discard override search paths. */
    if (unsetenv("LOCPATH") || unsetenv("GCONV_PATH") || !setlocale(LC_CTYPE, "C.UTF-8")) return fail("locale");
    if (fstat(3, &original) || !S_ISREG(original.st_mode) || original.st_size < 0 ||
        (uint64_t)original.st_size != in.size || (fcntl(3, F_GETFL) & O_ACCMODE) != O_RDONLY ||
        fstat(4, &parent) || !S_ISDIR(parent.st_mode) || parent.st_uid || (parent.st_mode & 07777) != 0700)
        return fail("descriptors");
    int target = openat(4, "root", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (target < 0 || fstat(target, &root) || !S_ISDIR(root.st_mode) ||
        (!rechecking && (root.st_uid || (root.st_mode & 07777) != 0700 || empty_directory(target))) ||
        flock(target, LOCK_EX | LOCK_NB) ||
        fstatvfs(target, &fs) || (fs.f_flag & (ST_NODEV | ST_NOSUID | ST_NOEXEC)) != (ST_NODEV | ST_NOSUID | ST_NOEXEC))
        return fail("staging");
    if (rechecking && !(fs.f_flag & ST_RDONLY)) return fail("read-only-root");
    struct statx root_identity;
    if (rechecking && (statx(target, "", AT_EMPTY_PATH | AT_SYMLINK_NOFOLLOW, STATX_BASIC_STATS | STATX_MNT_ID, &root_identity) ||
        !(root_identity.stx_mask & STATX_MNT_ID))) return fail("root-identity");
    if (dup2(target, 5) < 0) return fail("descriptors");
    if (target != 5) close(target);
    if (fchdir(5) || chroot(".") || chdir("/")) return fail("chroot");
    close(0); close(4);
    if (syscall(SYS_close_range, 7U, UINT_MAX, 0)) return fail("descriptors");
    if (restrict_process(in.deadline)) return fail("process-policy");
    umask(077);
    struct archive *reader = archive_read_new(), *writer = rechecking ? NULL : archive_write_disk_new();
    if (!reader || (!rechecking && !writer)) return fail("memory");
    crypto_hash_sha256_init(&in.hash);
    int options = ARCHIVE_EXTRACT_OWNER | ARCHIVE_EXTRACT_PERM | ARCHIVE_EXTRACT_TIME |
        ARCHIVE_EXTRACT_ACL | ARCHIVE_EXTRACT_FFLAGS | ARCHIVE_EXTRACT_XATTR |
        ARCHIVE_EXTRACT_SECURE_SYMLINKS | ARCHIVE_EXTRACT_SECURE_NODOTDOT |
        ARCHIVE_EXTRACT_SECURE_NOABSOLUTEPATHS | ARCHIVE_EXTRACT_NO_AUTODIR;
    /* Deliberately no symbolic user/group lookup into the host's account DB. */
    if (archive_read_support_format_tar(reader) != ARCHIVE_OK ||
        (!rechecking && archive_write_disk_set_options(writer, options) != ARCHIVE_OK) ||
        archive_read_open(reader, &in, NULL, read_archive, NULL) != ARCHIVE_OK) return fail("archive");
    struct retained *records = calloc((size_t)count_limit, sizeof(*records));
    if (!records) return fail("memory");
    struct archive_entry *entry; uint64_t entries = 0; int status;
    struct nia_tar_clocks clocks = {3, in.size, 0, in.deadline, 0};
    while ((status = archive_read_next_header(reader, &entry)) == ARCHIVE_OK) {
        if (++entries > count_limit || now_ms() >= in.deadline) return fail("bounds");
        if (nia_tar_clocks_next(&clocks, entry) != 1) return fail("clock-framing");
        if (archive_entry_size(entry) < 0 || (uint64_t)archive_entry_size(entry) > in.size)
            return fail("bounds");
        if (!archive_entry_pathname(entry)) return fail("path");
        if (entries == 1 && (archive_entry_filetype(entry) != AE_IFDIR ||
            (strcmp(archive_entry_pathname(entry), ".") && strcmp(archive_entry_pathname(entry), "./"))))
            return fail("root-entry");
        /* Retain only root timestamps and per-file digests, not an entire
         * clone of every entry's variable-sized metadata. */
        if (entries == 1 && !rechecking) {
            records[0].entry = archive_entry_clone(entry);
            if (!records[0].entry) return fail("memory");
        }
        crypto_hash_sha256_state content; crypto_hash_sha256_init(&content); uint64_t written = 0;
        if (rechecking) {
            records[entries-1].path = normal_path(archive_entry_pathname(entry));
            records[entries-1].hardlink = archive_entry_hardlink(entry) != NULL;
            if (!records[entries-1].path) return fail("verification-path");
            int fd = confined(records[entries-1].path, 0);
            if (fd < 0) return fail("verification-path");
            close(fd);
            if (archive_entry_hardlink(entry)) {
                char *path = normal_path(archive_entry_hardlink(entry));
                if (!path) return fail("verification-link");
                fd = confined(path, 0); free(path);
                if (fd < 0) return fail("verification-link");
                close(fd);
            }
        }
        if (!rechecking && archive_write_header(writer, entry) != ARCHIVE_OK) {
            fprintf(stderr, "{\"result\":\"failed\",\"reason\":\"metadata\",\"entry\":%" PRIu64 ",\"errno\":%d}\n", entries, archive_errno(writer));
            return 1;
        }
        const void *data; size_t size; la_int64_t offset;
        while ((status = archive_read_data_block(reader, &data, &size, &offset)) == ARCHIVE_OK) {
            if (offset < 0 || (uint64_t)offset != written || size > in.size - written) return fail("layout");
            written += size; crypto_hash_sha256_update(&content, data, size);
            if (now_ms() >= in.deadline || (!rechecking && archive_write_data_block(writer, data, size, offset) != ARCHIVE_OK))
                return fail("data");
        }
        crypto_hash_sha256_final(&content, records[entries - 1].content);
        if (status != ARCHIVE_EOF || (!rechecking && archive_write_finish_entry(writer) != ARCHIVE_OK)) return fail("entry");
    }
    if (status != ARCHIVE_EOF || entries != count_limit || nia_tar_clocks_next(&clocks, NULL) != 0) return fail("archive");
    /* Read all bytes even when tar EOF precedes the end of the retained file. */
    const void *unused;
    while (in.offset < in.size) if (read_archive(reader, &in, &unused) <= 0) return fail("input");
    crypto_hash_sha256_final(&in.hash, actual);
    if (sodium_memcmp(expected, actual, sizeof(actual))) return fail("digest");
    if (archive_read_close(reader) != ARCHIVE_OK || archive_read_free(reader) != ARCHIVE_OK ||
        (!rechecking && (archive_write_close(writer) != ARCHIVE_OK || archive_write_free(writer) != ARCHIVE_OK)))
        return fail("final-metadata");
    /* The existing extraction root is not a newly created tar directory.
     * Finalize its requested timestamps after creating all children. */
    if (!rechecking) {
    struct timespec root_times[2] = {{.tv_nsec = UTIME_OMIT}, {.tv_nsec = UTIME_OMIT}};
    if (archive_entry_atime_is_set(records[0].entry)) root_times[0] = (struct timespec){
        archive_entry_atime(records[0].entry), archive_entry_atime_nsec(records[0].entry)};
    if (archive_entry_mtime_is_set(records[0].entry)) root_times[1] = (struct timespec){
        archive_entry_mtime(records[0].entry), archive_entry_mtime_nsec(records[0].entry)};
    if (futimens(5, root_times)) return fail("root-time");
    archive_entry_free(records[0].entry); records[0].entry = NULL;
    }
    struct archive *disk = archive_read_disk_new();
    reader = archive_read_new(); in.offset = 0; crypto_hash_sha256_init(&in.hash);
    clocks = (struct nia_tar_clocks){3, in.size, 0, in.deadline, 0};
    if (!disk || !reader || archive_read_disk_set_symlink_physical(disk) != ARCHIVE_OK ||
        archive_read_support_format_tar(reader) != ARCHIVE_OK ||
        archive_read_open(reader, &in, NULL, read_archive, NULL) != ARCHIVE_OK) return fail("verification");
    for (uint64_t i = 0; i < entries; ++i) {
        if (archive_read_next_header(reader, &entry) != ARCHIVE_OK) return fail("verification-input");
        if (nia_tar_clocks_next(&clocks, entry) != 1) return fail("verification-clocks");
        records[i].entry = entry;  /* Borrowed until the next header. */
        int result = verify(disk, &records[i], &in);
        records[i].entry = NULL;
        if (result) {
            fprintf(stderr, "{\"result\":\"failed\",\"reason\":\"verification\",\"entry\":%" PRIu64 ",\"detail\":%d}\n", i + 1, -result);
            return 1;
        }
        if (archive_read_data_skip(reader) != ARCHIVE_OK) return fail("verification-input");
    }
    if (archive_read_next_header(reader, &entry) != ARCHIVE_EOF || nia_tar_clocks_next(&clocks, NULL) != 0) return fail("verification-input");
    while (in.offset < in.size) if (read_archive(reader, &in, &unused) <= 0) return fail("verification-input");
    crypto_hash_sha256_final(&in.hash, actual);
    if (sodium_memcmp(expected, actual, sizeof(actual))) return fail("verification-digest");
    if (rechecking && complete_tree(records, (size_t)entries, &in)) return fail("verification-namespace");
    for (uint64_t i = 0; i < entries; ++i) free(records[i].path);
    free(records);
    if (archive_read_close(reader) != ARCHIVE_OK || archive_read_free(reader) != ARCHIVE_OK ||
        archive_read_free(disk) != ARCHIVE_OK) return fail("verification");
    if (now_ms() >= in.deadline || (!rechecking && syncfs(5)) || now_ms() >= in.deadline) return fail("durability");
    if (rechecking) {
        if (printf("{\"result\":\"verified\",\"profile\":\"linux-inode-v1\",\"archive_sha256\":\"%s\",\"entries\":%" PRIu64
            ",\"mount_id\":%" PRIu64 ",\"inode\":%" PRIu64 ",\"device_major\":%u,\"device_minor\":%u,\"published\":false}\n",
            argv[1], entries, (uint64_t)root_identity.stx_mnt_id, (uint64_t)root_identity.stx_ino,
            root_identity.stx_dev_major, root_identity.stx_dev_minor) < 0 || fflush(stdout)) return 1;
        return 0;
    }
    if (printf("{\"result\":\"extracted\",\"profile\":\"linux-inode-v1\",\"archive_sha256\":\"%s\",\"entries\":%" PRIu64 ",\"published\":false}\n", argv[1], entries) < 0 || fflush(stdout)) return 1;
    return 0;
}

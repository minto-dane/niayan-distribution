/* SPDX-License-Identifier: BSD-3-Clause */
#define _GNU_SOURCE
#include "tar_clocks.h"
#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

/* Test-only driver: the independent clock cursor receives a known empty
 * regular entry. No extraction or privileged filesystem operation occurs. */
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    int fd = open(argv[1], O_RDONLY | O_CLOEXEC);
    struct stat st; struct timespec now;
    if (fd < 0 || fstat(fd, &st) || st.st_size < 0 || clock_gettime(CLOCK_BOOTTIME, &now)) return 2;
    struct nia_tar_clocks cursor = {fd, (uint64_t)st.st_size, 0,
        (uint64_t)now.tv_sec * 1000 + (uint64_t)now.tv_nsec / 1000000 + 10000, 0};
    if (!strcmp(argv[2], "expired")) cursor.deadline = 0;
    struct archive_entry *entry = archive_entry_new();
    if (!entry) return 2;
    archive_entry_set_filetype(entry, AE_IFREG);
    archive_entry_set_size(entry, 0);
    archive_entry_set_mtime(entry, 123, 456); /* Must be replaced even by zero. */
    int result = nia_tar_clocks_next(&cursor, entry);
    if (result == 1 && nia_tar_clocks_next(&cursor, NULL) == 0 && lseek(fd, 0, SEEK_CUR) == 0) {
        printf("[[%" PRId64 ",%ld],[%" PRId64 ",%ld],[%" PRId64 ",%ld],[%" PRId64 ",%ld]]\n",
            (int64_t)archive_entry_mtime(entry), archive_entry_mtime_nsec(entry),
            (int64_t)archive_entry_atime(entry), archive_entry_atime_nsec(entry),
            (int64_t)archive_entry_ctime(entry), archive_entry_ctime_nsec(entry),
            (int64_t)archive_entry_birthtime(entry), archive_entry_birthtime_nsec(entry));
        result = 0;
    } else result = 1;
    archive_entry_free(entry); close(fd); return result;
}

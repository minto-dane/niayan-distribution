/* SPDX-License-Identifier: BSD-3-Clause */
#define _GNU_SOURCE
#include "tar_clocks.h"
#include <errno.h>
#include <limits.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define MAX_EXTENSION (1024U * 1024U)
#define MAX_EXTENSIONS (UINT64_C(64) * 1024 * 1024)
_Static_assert(sizeof(time_t) >= sizeof(int64_t) && (time_t)-1 < 0, "signed 64-bit time_t required");
struct clock_value { int present; int64_t seconds; long nanos; };
static int live(const struct nia_tar_clocks *in) {
    struct timespec now;
    return !clock_gettime(CLOCK_BOOTTIME, &now) && now.tv_sec >= 0 &&
        (uint64_t)now.tv_sec * 1000 + (uint64_t)now.tv_nsec / 1000000 < in->deadline;
}
static int read_at(const struct nia_tar_clocks *in, uint64_t at, void *buffer, size_t size) {
    if (at > in->size || size > in->size - at || at > INT64_MAX) return -1;
    size_t used = 0;
    while (used < size) {
        if (!live(in)) return -1;
        ssize_t n = pread(in->fd, (unsigned char *)buffer + used, size - used, (off_t)(at + used));
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return -1;
        used += (size_t)n;
    }
    return 0;
}
static int zero(const unsigned char *p, size_t n) {
    for (size_t i = 0; i < n; ++i) if (p[i]) return 0;
    return 1;
}
static int zero_range(const struct nia_tar_clocks *in, uint64_t at, uint64_t size) {
    unsigned char buffer[65536];
    while (size) {
        size_t n = size > sizeof(buffer) ? sizeof(buffer) : (size_t)size;
        if (read_at(in, at, buffer, n) || !zero(buffer, n)) return -1;
        at += n; size -= n;
    }
    return 0;
}
static int integer(const unsigned char *p, size_t n, int64_t *result, int signed_value) {
    uint64_t value = 0; size_t at = 0; int negative = 0;
    if (p[0] == 0x80 || (signed_value && p[0] == 0xff)) {
        negative = p[0] == 0xff;
        for (at = 1; at < n; ++at) {
            unsigned digit = negative ? 255U - p[at] : p[at];
            if (value > ((uint64_t)INT64_MAX - digit) / 256) return -1;
            value = value * 256 + digit;
        }
    } else {
        while (at < n && p[at] == ' ') ++at;
        while (at < n && p[at] >= '0' && p[at] <= '7') {
            unsigned digit = p[at++] - '0';
            if (value > ((uint64_t)INT64_MAX - digit) / 8) return -1;
            value = value * 8 + digit;
        }
        while (at < n) {
            if (p[at] != 0 && p[at] != ' ') return -1;
            ++at;
        }
    }
    *result = negative ? -1 - (int64_t)value : (int64_t)value; return 0;
}
static int clock_text(const unsigned char *p, size_t n, struct clock_value *result) {
    size_t at = 0, digits = 0; int negative = n && p[0] == '-';
    int64_t seconds = 0; long nanos = 0;
    if (negative) ++at;
    while (at < n && p[at] >= '0' && p[at] <= '9') {
        int64_t digit = p[at++] - '0';
        if (seconds < (INT64_MIN + digit) / 10) return -1;
        seconds = seconds * 10 - digit; ++digits;
    }
    if (!digits || (!negative && seconds == INT64_MIN)) return -1;
    if (at < n) {
        if (p[at++] != '.' || at == n) return -1;
        digits = 0;
        while (at < n) {
            unsigned c = p[at++];
            if (c < '0' || c > '9' || (digits >= 9 && c != '0')) return -1;
            if (digits < 9) nanos = nanos * 10 + (long)(c - '0');
            ++digits;
        }
        while (digits++ < 9) nanos *= 10;
    }
    if (negative) {
        if (nanos) {
            if (seconds == INT64_MIN) return -1;
            --seconds; nanos = 1000000000L - nanos;
        }
    } else seconds = -seconds;
    *result = (struct clock_value){1, seconds, nanos}; return 0;
}
static int pax(const unsigned char *p, size_t n, struct clock_value clocks[4], uint64_t *size, int *have_size) {
    size_t at = 0;
    static const char *keys[] = {"mtime", "atime", "ctime", "LIBARCHIVE.creationtime"};
    while (at < n) {
        size_t start = at, length = 0;
        while (at < n && p[at] >= '0' && p[at] <= '9') {
            unsigned digit = p[at++] - '0';
            if (length > (MAX_EXTENSION - digit) / 10) return -1;
            length = length * 10 + digit;
        }
        if (at == start || at == n || p[at++] != ' ' || length > n - start || length < at - start + 3) return -1;
        size_t end = start + length - 1, key = at;
        if (p[end] != '\n') return -1;
        while (at < end && p[at] != '=') {
            if (p[at] < '!' || p[at] > '~') return -1;
            ++at;
        }
        if (at == key || at == end) return -1;
        size_t key_size = at - key, value = at + 1;
        if (key_size == 4 && !memcmp(p + key, "size", 4)) {
            if (*have_size || value == end) return -1;
            uint64_t number = 0;
            for (size_t i = value; i < end; ++i) {
                if (p[i] < '0' || p[i] > '9' || number > ((uint64_t)INT64_MAX - (p[i] - '0')) / 10) return -1;
                number = number * 10 + (p[i] - '0');
            }
            *size = number; *have_size = 1;
        }
        for (unsigned i = 0; i < 4; ++i) if (key_size == strlen(keys[i]) && !memcmp(p + key, keys[i], key_size)) {
            if (clocks[i].present || clock_text(p + value, end - value, &clocks[i])) return -1;
        }
        at = start + length;
    }
    return 0;
}
static int kind_matches(unsigned char kind, struct archive_entry *entry, uint64_t size) {
    if (!entry || archive_entry_size(entry) < 0 || (uint64_t)archive_entry_size(entry) != size) return 0;
    if (kind == '1') return archive_entry_hardlink(entry) != NULL;
    if (archive_entry_hardlink(entry)) return 0;
    unsigned type = archive_entry_filetype(entry);
    return ((kind == 0 || kind == '0' || kind == '7') && type == AE_IFREG) ||
        (kind == '2' && type == AE_IFLNK) || (kind == '3' && type == AE_IFCHR) ||
        (kind == '4' && type == AE_IFBLK) || (kind == '5' && type == AE_IFDIR) ||
        (kind == '6' && type == AE_IFIFO);
}
int nia_tar_clocks_next(struct nia_tar_clocks *in, struct archive_entry *entry) {
    struct clock_value clocks[4] = {{0}};
    int seen_pax = 0, seen_name = 0, seen_link = 0, have_size = 0;
    uint64_t pax_size = 0;
    while (in->offset < in->size) {
        unsigned char header[512]; int64_t number, checksum; uint64_t sum = 0;
        if (read_at(in, in->offset, header, sizeof(header))) return -1;
        if (zero(header, sizeof(header))) {
            if (entry || seen_pax || seen_name || seen_link || in->size - in->offset < 1024 ||
                zero_range(in, in->offset, in->size - in->offset)) return -1;
            in->offset = in->size; return 0;
        }
        if (!entry || integer(header + 148, 8, &checksum, 0)) return -1;
        for (unsigned i = 0; i < 512; ++i) sum += i >= 148 && i < 156 ? ' ' : header[i];
        if (sum != (uint64_t)checksum || integer(header + 124, 12, &number, 0)) return -1;
        unsigned char kind = header[156]; uint64_t size = (uint64_t)number;
        int extension = kind == 'x' || kind == 'L' || kind == 'K';
        if (!extension && have_size) size = pax_size;
        uint64_t body = in->offset + 512, padding = (512 - size % 512) % 512;
        if (size > in->size - body || padding > in->size - body - size || zero_range(in, body + size, padding)) return -1;
        in->offset = body + size + padding;
        if (extension) {
            if (!size || size > MAX_EXTENSION || size > MAX_EXTENSIONS - in->extensions) return -1;
            in->extensions += size;
            if ((kind == 'x' && (seen_pax || seen_name || seen_link)) ||
                (kind == 'L' && (seen_pax || seen_name)) || (kind == 'K' && (seen_pax || seen_link))) return -1;
            unsigned char *data = malloc((size_t)size); if (!data) return -1;
            int bad = read_at(in, body, data, (size_t)size);
            if (!bad && kind == 'x') bad = pax(data, (size_t)size, clocks, &pax_size, &have_size);
            if (!bad && kind != 'x') bad = data[size - 1] || memchr(data, 0, (size_t)size - 1) != NULL;
            free(data); if (bad) return -1;
            if (kind == 'x') seen_pax = 1; else if (kind == 'L') seen_name = 1; else seen_link = 1;
            continue;
        }
        if (!kind_matches(kind, entry, size) || (kind >= '1' && kind <= '6' && size)) return -1;
        if (!clocks[0].present) {
            if (integer(header + 136, 12, &number, 1)) return -1;
            clocks[0] = (struct clock_value){1, number, 0};
        }
        archive_entry_set_mtime(entry, (time_t)clocks[0].seconds, clocks[0].nanos);
        if (clocks[1].present) archive_entry_set_atime(entry, (time_t)clocks[1].seconds, clocks[1].nanos);
        if (clocks[2].present) archive_entry_set_ctime(entry, (time_t)clocks[2].seconds, clocks[2].nanos);
        if (clocks[3].present) archive_entry_set_birthtime(entry, (time_t)clocks[3].seconds, clocks[3].nanos);
        return 1;
    }
    return -1; /* A tar without its complete terminator is never complete. */
}

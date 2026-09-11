/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef NIA_TAR_CLOCKS_H
#define NIA_TAR_CLOCKS_H
#include <archive_entry.h>
#include <stdint.h>
/* Independent sequential cursor over the same authorized raw tar FD. It owns
 * no descriptor and changes no file offset. No filesystem attribute writes. */
struct nia_tar_clocks {
    int fd;
    uint64_t size, offset, deadline, extensions;
};
/* One entry is parsed and its canonical clocks replace the library's decoded
 * clocks. Returns 1 for an entry, 0 for a complete zero terminator, -1 on error.
 * Pass NULL only when checking the terminator after the library reports EOF. */
int nia_tar_clocks_next(struct nia_tar_clocks *, struct archive_entry *);
#endif

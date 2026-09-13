# SPDX-License-Identifier: BSD-3-Clause
"""Protected native executable pinning shared by private observer children."""
import os
import stat


class Rejected(ValueError):
    pass


def executable(name: str) -> int:
    # Fixed path only. Pin every protected ancestor and the final ELF. No
    # caller-selected executable, environment lookup or implicit escalation.
    if name not in ('pkg_operator_guard', 'pkg_supply_guard', 'pkg_catalog_query'):
        raise Rejected('unknown-private-helper')
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    result = -1
    try:
        for name in ('usr', 'libexec', 'nia'):
            info = os.fstat(directory)
            if info.st_uid or info.st_mode & 0o022:
                raise Rejected('unprotected-helper-directory')
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                            dir_fd=directory)
            previous, directory = directory, child
            os.close(previous)
        info = os.fstat(directory)
        if info.st_uid or info.st_mode & 0o022:
            raise Rejected('unprotected-helper-directory')
        result = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                         dir_fd=directory)
        info = os.fstat(result)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid or info.st_nlink != 1
                or info.st_mode & 0o6022 or not info.st_mode & 0o111 or os.read(result, 4) != b'\x7fELF'):
            raise Rejected('unprotected-native-helper')
    except BaseException:
        if result >= 0:
            owned, result = result, -1
            os.close(owned)
        raise
    finally:
        try:
            os.close(directory)
        except BaseException:
            if result >= 0:
                os.close(result)
            raise
    return result



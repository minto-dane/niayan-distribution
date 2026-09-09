# SPDX-License-Identifier: MIT
"""Stable public error codes and translatable messages, independent of errno text.

Internal exception details remain available to SDK callers. Do not interpolate
arbitrary exception strings, server responses or metadata into message IDs.
"""
import errno
from i18n import N_

INPUT_MESSAGES = {
    'command label differs from interim control': ('NIA-E-LABEL', N_('The command label differs from the package control file.')),
    'original DEB identity differs from interim manifest': ('NIA-E-IDENTITY', N_('The original package identity differs from the manifest.')),
    'artifact size or digest mismatch': ('NIA-E-CONTENT', N_('The package size or checksum does not match.')),
    'interim artifact is expired or not yet valid': ('NIA-E-EXPIRY', N_('The interim package has expired or is not yet valid.')),
    'interim artifact expired during intake': ('NIA-E-EXPIRY', N_('The interim package expired during download.')),
    'interim security epoch below trusted floor': ('NIA-E-EPOCH', N_('The interim package is older than the trusted security minimum.')),
    'authenticated reference differs from interim manifest': ('NIA-E-REFERENCE', N_('The authenticated reference differs from the package manifest.')),
    'repository policy changed during intake': ('NIA-E-POLICY-CHANGED', N_('Repository policy changed during download; retry with the current policy.')),
    'input is not protected policy owned by the expected authority': ('NIA-E-POLICY', N_('Repository policy ownership or permissions are not trusted.')),
    'download URL is outside the configured target repository': ('NIA-E-REPOSITORY', N_('The download URL is outside the configured repository.')),
    'target is absent from authenticated repository': ('NIA-E-NO-TARGET', N_('The requested artifact is absent from the authenticated repository.')),
}

IO_MESSAGES = {
    errno.ENOENT: ('NIA-E-NOT-FOUND', N_('A required file or directory does not exist.')),
    errno.EEXIST: ('NIA-E-EXISTS', N_('The output already exists and was not overwritten.')),
    errno.EACCES: ('NIA-E-ACCESS', N_('Permission to access a required file or directory was denied.')),
    errno.EPERM: ('NIA-E-ACCESS', N_('Permission to access a required file or directory was denied.')),
    errno.ENOSPC: ('NIA-E-NO-SPACE', N_('Storage is full; the operation did not complete.')),
    errno.EDQUOT: ('NIA-E-QUOTA', N_('The storage quota was exceeded; the operation did not complete.')),
    errno.ELOOP: ('NIA-E-LINK', N_('A symbolic link was encountered where an ordinary path is required.')),
    errno.EAGAIN: ('NIA-E-BUSY', N_('The repository is in use; retry after the current operation finishes.')),
}


def public_error(error, ui, *, repository=False):
    from nia_common import Invalid
    if isinstance(error, OSError):
        code, message = IO_MESSAGES.get(error.errno, ('NIA-E-IO', N_('An input/output operation failed; completion is not established.')))
    elif isinstance(error, Invalid):
        code, message = INPUT_MESSAGES.get(str(error), ('NIA-E-INPUT', N_('The input is invalid or is not supported by this operation.')))
    elif repository:
        from tuf.api import exceptions
        if isinstance(error, exceptions.DownloadError):
            code, message = 'NIA-E-DOWNLOAD', N_('Repository download failed; check the connection and repository configuration.')
        elif isinstance(error, exceptions.RepositoryError):
            code, message = 'NIA-E-AUTHENTICATION', N_('Repository authentication failed; no artifact was accepted.')
        else:
            code, message = 'NIA-E-INPUT', N_('The input is invalid or is not supported by this operation.')
    else:
        code, message = 'NIA-E-OPERATION', N_('The operation could not be completed.')
    return '[' + code + '] ' + ui.message(message)

# SPDX-License-Identifier: BSD-3-Clause
"""Public interim download action through the shared authenticated repository."""
from __future__ import annotations

import os
from pathlib import Path
import sys

from interim_commands import _directory
from i18n import UI, write_text
from diagnostics import public_error
from interim_intake import authenticate
from repository import Repository, base_url, target_path, tuf_errors
from nia_common import Invalid, canonical, digest, fields, integer, parse_json, read_file, write_new

POLICY_PATH = Path('/etc/nia/repository.json')


def load_policy(path: Path, *, owner=0):
    raw = read_file(path, 16 * 1024, owner=owner)
    policy = parse_json(raw)
    fields(policy, {'schema', 'cache', 'bootstrap_sha256', 'metadata_url', 'targets_url', 'security_epoch'},
           'repository policy')
    if policy['schema'] != 'org.niaos.repository-policy/v1':
        raise Invalid('repository policy version')
    if (not isinstance(policy['cache'], str) or not policy['cache'].startswith('/')
            or len(policy['cache']) > 4096 or '\\' in policy['cache']
            or any(ord(c) < 32 or ord(c) == 127 for c in policy['cache'])
            or any(p in ('', '.', '..') for p in policy['cache'].split('/')[1:])):
        raise Invalid('repository cache must be an absolute canonical path')
    digest(policy['bootstrap_sha256'])
    integer(policy['security_epoch'], 1, 2**53 - 1, 'security epoch')
    for key in ('metadata_url', 'targets_url'):
        if base_url(policy[key]) != policy[key]:
            raise Invalid('repository base URL must have one trailing slash')
    return policy


def download(policy, url: str, directory: Path, *, fetcher=None, recheck):
    """recheck must re-read local authority before output, never a public Boolean.

    Output is the original artifact only. References are authenticated during
    intake, but this is not an offline install bundle or an execution receipt.
    """
    expected_policy = canonical(policy)
    policy = parse_json(expected_policy)
    base = policy['targets_url']
    if not isinstance(url, str) or not url.startswith(base):
        raise Invalid('download URL is outside the configured target repository')
    target = target_path(url[len(base):])
    if not target.endswith('.epkg'):
        raise Invalid('download target is not a native interim package')
    with Repository(Path(policy['cache']), policy['bootstrap_sha256'],
                    policy['metadata_url'], policy['targets_url'], fetcher=fetcher) as repository:
        verified = authenticate(repository, target, minimum_security_epoch=policy['security_epoch'])
        current = recheck()
        if canonical(current) != expected_policy:
            raise Invalid('repository policy changed during intake')
        _directory(directory)
        output = directory / target.rsplit('/', 1)[-1]
        write_new(output, verified.artifact)
        return output


def execute_download(request, *, ui=None):
    ui = ui or UI.from_environment()
    try:
        values = dict(request.values)
        policy = load_policy(POLICY_PATH)
        output = download(policy, values['L'],
                          Path(values.get('P', '/tmp/ifix_' + str(os.getpid()))),
                          recheck=lambda: load_policy(POLICY_PATH))
        write_text(sys.stdout, ui.message('Downloaded interim fix: {path}', path=output) + '\n')
        return 0
    except (Invalid, OSError, ValueError, tuf_errors.RepositoryError, tuf_errors.DownloadError) as exc:
        write_text(sys.stderr, 'emgr_download_ifix: ' + public_error(exc, ui, repository=True) + '\n')
        return 1

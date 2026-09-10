# SPDX-License-Identifier: BSD-3-Clause
"""Validate Nia recovery domains. No disk formatting, mounting or authorization."""
from nia_common import Invalid, fields, relative

# Required, closed product layout: a catalog directory is the sole embedded entry.
REQUIRED = {
    'system': ('/', 'xfs', 'system-generation', True, True),
    'catalog': ('/var/lib/nia/catalog', 'embedded-in-system', 'system-generation', True, True),
    'control': ('/var/lib/nia/control', 'xfs', 'never-system-rollback', False, True),
    'trust': ('/var/lib/nia/trust', 'xfs', 'never-system-rollback', False, True),
    'objects': ('/var/lib/nia/objects', 'xfs', 'never-system-rollback', False, True),
    'secrets': ('/etc/nia/keys', 'xfs', 'never-system-rollback', False, True),
    'logs': ('/var/log', 'xfs', 'never-system-rollback', False, True),
    'cache': ('/var/cache', 'xfs', 'rebuildable', False, True),
    'data': ('/srv', 'xfs', 'application-recovery-only', False, True),
    'home': ('/home', 'xfs', 'user-recovery-only', False, True),
    'esp': ('/efi', 'vfat', 'signed-boot-selection-only', False, False),
    'run': ('/run', 'tmpfs', 'ephemeral', False, False),
    'tmp': ('/tmp', 'tmpfs', 'ephemeral', False, False),
    'vartmp': ('/var/tmp', 'xfs', 'rebuildable', False, True),
}

def check_layout(layout):
    fields(layout, {'schema', 'product', 'shared_inode_with_live_tree', 'snapshot_is_backup',
        'recursive_snapshot_assumed', 'disk_write_authorized', 'catalog_and_files_same_generation',
        'filesystem_snapshot_required', 'entries'}, 'layout')
    if layout['schema'] != 'org.niaos.layout/v2' or layout['product'] != 'nia-os':
        raise Invalid('layout identity')
    for key in ('shared_inode_with_live_tree', 'snapshot_is_backup', 'recursive_snapshot_assumed',
                'disk_write_authorized', 'filesystem_snapshot_required'):
        if layout[key] is not False: raise Invalid('unsupported storage assumption: ' + key)
    if layout['catalog_and_files_same_generation'] is not True:
        raise Invalid('catalog detached from file generation')
    entries = layout['entries']
    if not isinstance(entries, list) or len(entries) != len(REQUIRED): raise Invalid('layout size')
    seen = set(); paths = set(); volumes = set()
    for e in entries:
        fields(e, {'id','path','storage','rollback_domain','system_rollback','encrypted','contents',
                   'writer','volume','mount_required','format_allowed'}, 'layout entry')
        name = e['id']; p = e['path']
        if not isinstance(name, str) or name not in REQUIRED or name in seen:
            raise Invalid('unknown/duplicate recovery domain')
        if not isinstance(p, str) or not p.startswith('/') or p in paths:
            raise Invalid('invalid/duplicate mount path')
        if p != '/': relative(p[1:])
        for key in ('system_rollback', 'encrypted', 'mount_required', 'format_allowed'):
            if type(e[key]) is not bool: raise Invalid('noncanonical boolean')
        if tuple(e[k] for k in ('path','storage','rollback_domain','system_rollback','encrypted')) != REQUIRED[name]:
            raise Invalid('unsafe domain placement: ' + name)
        expected_volume = 'nia-system' if name in ('catalog','system') else 'nia-' + name
        if e['volume'] != expected_volume or e['mount_required'] != (name != 'catalog') or e['format_allowed']:
            raise Invalid('mount/volume/format policy: ' + name)
        if not all(isinstance(e[k], str) and 0 < len(e[k]) <= 256 for k in ('contents','writer')):
            raise Invalid('state owner unknown')
        if name != 'catalog':
            if e['volume'] in volumes: raise Invalid('independent domains share a volume')
            volumes.add(e['volume'])
        seen.add(name); paths.add(p)
    if seen != set(REQUIRED): raise Invalid('incomplete recovery domain coverage')
    return {'layout_valid': True, 'execution_permit': False, 'mounted_or_formatted': False,
            'physical_durability_tested': False, 'domains': len(entries),
            'physical_mount_bindings_verified': False, 'persistent_filesystem': 'xfs'}

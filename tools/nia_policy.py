# SPDX-License-Identifier: BSD-3-Clause
"""Product policy and explicit implementation/readiness boundaries."""
from __future__ import annotations
from nia_common import Invalid,fields,canonical

SUPPLY={'distribution':'debian','codename':'forky','major':14,'format':'deb','mode':'pinned-snapshot',
    'rolling_aliases':False,'mix_families':False,'architecture':'amd64','independent_architecture':'all',
    'required_component':'main','exception_components':['contrib','non-free','non-free-firmware'],
    'archive_authentication':'openpgp-inrelease-sha256-chain',
    'reproduction':'exact-deb-source-buildinfo-independent-receipts'}
OWNERSHIP={'host_package_authority':'nia','native_manager_writers':[],
    'native_database':'nia-catalog-v1','requires_native_db_handoff':False,
    'upstream_abi_reuse':True,'maintainer_scripts':'reviewed-effect-contract-only'}
SYSTEM={'architecture':'x86_64','cpu_baseline':'x86-64-v2','libc':'glibc','init':'systemd',
    'network':'NetworkManager','mac':'apparmor-enforcing-scoped-profiles','root_filesystem':'xfs',
    'data_filesystem':'xfs','persistent_filesystem':'xfs','storage_contract':'org.niaos.xfs-policy/v1','at_rest_encryption':'luks2','boot':'systemd-boot-signed-uki',
    'secure_boot_required':True,'root_update':'mutable-managed','unconditional_reboot':False,
    'hibernation_default':False,'kernel':'debian-forky-signed-cohort-upstream-lag-gated'}
PRODUCT={'configuration_authority':'configcore','change_authority':'controlcore',
    'solver_authority':'resolvercore-independent-checker','host_console':'nia',
    'internal_compatibility_names':['missionctl','MC_*'],'default_package_execution':False,
    'bootable_image_available':False,'production_qualified':False}

def check_profile(p:dict)->dict:
    fields(p,{'schema','id','name','version','qualification','supply','ownership','system','product'},'Nia profile')
    if (p['schema'],p['id'],p['name'],p['version'],p['qualification'])!=('org.niaos.product/v2','nia-os','Nia OS','0.1-dev','unqualified-source'):raise Invalid('unsupported product identity')
    for name,expected in [('supply',SUPPLY),('ownership',OWNERSHIP),('system',SYSTEM),('product',PRODUCT)]:
        if canonical(p[name])!=canonical(expected):raise Invalid('unreviewed product change: '+name)
    return {'product':'Nia OS','profile_valid':True,'execution_permit':False,'production_qualified':False}

GATES=('toolchain-build','spark-flow-proof','native-parser-revalidation','deb-native-semantics',
 'maintainer-effect-closure','configuration-observer-closure','archive-authentication',
 'exact-binary-reproduction','supplier-maintenance-qualified','security-lag-service','catalog-file-wal-binding',
 'no-competing-writer','root-file-executor','root-generation-recovery','power-loss-recovery',
 'secure-boot-enrollment','signed-uki-boot-test','initramfs-kernel-module-cohort',
 'apparmor-effective-policy','identity-secret-provisioning','independent-trust-floor',
 'signed-installation','installer-disk-identity','network-loss-recovery','systemd-health-observers',
 'hardware-fencing','data-backup-restore-drill','management-ha','long-term-log-retention',
 'software-licenses-source-offer','operational-review',
 'xfs-runtime-capability-cohort','xfs-rescue-feature-compatibility',
 'xfs-scrub-observer-coverage','xfs-online-repair-qualification',
 'content-integrity-and-backup','xfs-layout-physical-binding',
 'consent-peer-and-backend-identity','consent-exact-scope-ui-response',
 'portal-intent-before-effect','grant-revocation-observed',
 'consent-anchor-and-reservation','real-desktop-session-switch-tests')

def readiness(product_digest:str,evidence:list[dict])->dict:
    """Structural planning only. Actual qualification requires signature verifiers.

This deliberately does not turn caller-provided PASS strings into authorization.
"""
    from nia_common import digest
    digest(product_digest)
    known={};duplicates=[]
    for row in evidence:
        fields(row,{'gate','state','scope_sha256','evidence_ref'},'readiness item')
        if row['gate'] not in GATES or row['state'] not in ('missing','planned','implemented-unvalidated','tested-tooling','requires-site-qualification'):raise Invalid('unknown or overstated readiness')
        if row['scope_sha256']!=product_digest or not isinstance(row['evidence_ref'],str):raise Invalid('readiness scope')
        if row['gate'] in known:raise Invalid('duplicate readiness gate')
        known[row['gate']]=row
    return {'product':'Nia OS','execution_permit':False,'production_qualified':False,
            'gates':[known.get(g,{'gate':g,'state':'missing','scope_sha256':product_digest,'evidence_ref':''}) for g in GATES]}

# SPDX-License-Identifier: MIT
"""Executable source/policy tests and bounded Linux read-only probes, not Ada proof."""
import copy, hashlib, json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nia_common import Invalid, canonical
from nia_xfs import assess, check_policy, parse_mountinfo, inspect_local, CAPABILITIES, DISK_FEATURES, COHORT, REPAIR_FACTS
from nia_layout import check_layout
from nia_policy import check_profile
ROOT=Path(__file__).resolve().parents[1]

class Layout(unittest.TestCase):
    def setUp(self): self.p=json.loads((ROOT/'profiles/nia-os.json').read_text());self.l=json.loads((ROOT/'contracts/state-domains.json').read_text())
    def test_current_xfs(self):
        self.assertTrue(check_layout(self.l)['layout_valid']);self.assertTrue(check_profile(self.p)['profile_valid'])
        self.assertEqual(self.p['system']['root_filesystem'],'xfs');self.assertEqual(self.p['system']['data_filesystem'],'xfs')
    def test_all_persistent_domains(self):
        self.assertEqual({e['storage'] for e in self.l['entries'] if e['encrypted']},{'xfs','embedded-in-system'})
    def test_embedded_catalog(self):
        c=next(e for e in self.l['entries'] if e['id']=='catalog');c['storage']='xfs'
        self.assertRaises(Invalid,check_layout,self.l)
    def test_shared_control_volume(self):
        next(e for e in self.l['entries'] if e['id']=='control')['volume']='nia-system'
        self.assertRaises(Invalid,check_layout,self.l)
    def test_missing_independent_mount(self):
        next(e for e in self.l['entries'] if e['id']=='trust')['mount_required']=False
        self.assertRaises(Invalid,check_layout,self.l)
    def test_data_rollback_forbidden(self):
        next(e for e in self.l['entries'] if e['id']=='data')['system_rollback']=True
        self.assertRaises(Invalid,check_layout,self.l)
    def test_old_profile_rejected(self):
        self.p['schema']='org.niaos.product/v1';self.assertRaises(Invalid,check_profile,self.p)
    def test_old_filesystem_rejected(self):
        for fs in ('ext4','btrfs'):
            p=copy.deepcopy(self.p);p['system']['root_filesystem']=fs
            self.assertRaises(Invalid,check_profile,p)
    def test_fs_snapshot_not_required(self):
        self.l['filesystem_snapshot_required']=True;self.assertRaises(Invalid,check_layout,self.l)
    def test_format_not_authorized(self):
        self.l['entries'][0]['format_allowed']=True;self.assertRaises(Invalid,check_layout,self.l)
    def test_unknown_domain_rejected(self):
        self.l['entries'].append(copy.deepcopy(self.l['entries'][0]));self.assertRaises(Invalid,check_layout,self.l)
    def test_no_esp_encryption_claim(self):
        next(e for e in self.l['entries'] if e['id']=='esp')['encrypted']=True
        self.assertRaises(Invalid,check_layout,self.l)

class Evidence(unittest.TestCase):
    def setUp(self):
        self.p=json.loads((ROOT/'contracts/xfs-policy.json').read_text())
        self.e={'node':'11111111-1111-1111-1111-111111111111','boot':'22222222-2222-2222-2222-222222222222',
                'fs_uuid':'33333333-3333-3333-3333-333333333333','mount_id':17,'mount_namespace':18,
                'cohort':{k:hashlib.sha256(k.encode()).hexdigest() for k in COHORT}}
        self.e['cohort']['policy']=hashlib.sha256(canonical(self.p)).hexdigest()
        self.o={'schema':'org.niaos.xfs-observation/v1','subject':copy.deepcopy(self.e),'observed_ms':100,
                'expires_ms':400,'kernel_version':'7.1.12','xfsprogs_version':'7.0.0',
                'capabilities':{k:'satisfied' for k in CAPABILITIES},'disk_features':{k:'satisfied' for k in DISK_FEATURES},
                'repair_facts':{k:'satisfied' for k in REPAIR_FACTS},'metadata':'satisfied','media':'satisfied','content':'satisfied',
                'stream_complete':True,'last_event_sequence':10,'scrub_covers_sequence':10,
                'scrub_started_ms':20,'scrub_finished_ms':50,'repair_attempts':0,'unresolved_operation':False}
    def go(self):return assess(self.p,self.o,self.e,120)
    def test_complete_diagnostic_is_not_permission(self):
        r=self.go();self.assertEqual(r['action'],'metadata-media-content-candidate-consistent')
        self.assertFalse(r['execution_permit']);self.assertFalse(r['facts_authenticated'])
    def test_version_alone_not_capability(self):
        self.o['capabilities']={k:'unknown' for k in CAPABILITIES}
        self.assertEqual(self.go()['action'],'hold-new-changes-capability-gap')
    def test_debian_userspace_gap_visible(self):
        self.o['xfsprogs_version']='6.19.0';self.assertIn('xfsprogs-floor',self.go()['missing'])
    def test_false_rescue_prevents_admission(self):
        self.o['cohort']={} # unknown key cannot be silently discarded
        self.assertRaises(Invalid,self.go)
    def test_every_capability_required(self):
        for key in CAPABILITIES:
            old=self.o['capabilities'][key];self.o['capabilities'][key]='unknown'
            self.assertEqual(self.go()['action'],'hold-new-changes-capability-gap');self.o['capabilities'][key]=old
    def test_reverse_indices_required(self):
        for key in DISK_FEATURES:
            self.o['disk_features'][key]='violated';self.assertIn('disk_features.'+key,self.go()['missing'])
            self.o['disk_features'][key]='satisfied'
    def test_filesystem_substitution_rejected(self):
        self.o['subject']['fs_uuid']='44444444-4444-4444-4444-444444444444';self.assertRaises(Invalid,self.go)
    def test_mount_substitution_rejected(self):
        self.o['subject']['mount_id']+=1;self.assertRaises(Invalid,self.go)
    def test_namespace_substitution_rejected(self):
        self.o['subject']['mount_namespace']+=1;self.assertRaises(Invalid,self.go)
    def test_different_policy_rejected(self):
        self.o['subject']['cohort']['policy']='a'*64;self.assertRaises(Invalid,self.go)
    def test_expiry_rejected(self):self.o['expires_ms']=120;self.assertRaises(Invalid,self.go)
    def test_future_rejected(self):self.o['observed_ms']=121;self.assertRaises(Invalid,self.go)
    def test_excessive_ttl_rejected(self):self.o['expires_ms']=90000;self.assertRaises(Invalid,self.go)
    def test_boolean_is_not_sequence(self):self.o['last_event_sequence']=True;self.assertRaises(Invalid,self.go)
    def test_negative_rejected(self):self.o['repair_attempts']=-1;self.assertRaises(Invalid,self.go)
    def test_sequence_overflow_rejected(self):self.o['last_event_sequence']=1<<64;self.assertRaises(Invalid,self.go)
    def test_signed_counter_upper_bound(self):
        self.o['last_event_sequence']=1<<63;self.assertRaises(Invalid,self.go)
    def test_axis_encoding_rejects_nested_values(self):
        for key in ('metadata','media','content'):
            old=self.o[key];self.o[key]=[]
            self.assertRaises(Invalid,self.go);self.o[key]=old
    def test_unknown_event_coverage(self):
        self.o['stream_complete']=False;self.assertEqual(self.go()['action'],'reestablish-stream-and-full-readonly-scrub')
    def test_scrub_watermark_mismatch(self):
        self.o['scrub_covers_sequence']=9;self.assertEqual(self.go()['action'],'schedule-full-readonly-scrub')
    def test_future_watermark_rejected(self):self.o['scrub_covers_sequence']=11;self.assertRaises(Invalid,self.go)
    def test_metadata_not_content(self):
        self.o['content']='unknown';self.assertEqual(self.go()['action'],'hold-new-changes-content-or-media-unverified')
    def test_content_failure_not_metadata_repair(self):
        self.o['content']='violated';self.assertEqual(self.go()['action'],'contain-preserve-and-plan-content-recovery')
    def test_media_failure_overrides_other_gaps(self):
        self.o['media']='violated';self.o['stream_complete']=False
        self.assertEqual(self.go()['action'],'contain-preserve-and-plan-content-recovery')
    def test_no_retry_on_pending(self):
        self.o['unresolved_operation']=True;self.assertEqual(self.go()['action'],'reconcile-existing-operation')
    def test_repair_is_only_candidate(self):
        self.o['metadata']='violated';r=self.go();self.assertEqual(r['action'],'qualified-repair-session-candidate')
        self.assertFalse(r['execution_permit'])
    def test_each_repair_prerequisite(self):
        self.o['metadata']='violated'
        for key in REPAIR_FACTS:
            self.o['repair_facts'][key]='unknown'
            self.assertEqual(self.go()['action'],'preserve-evidence-and-plan-offline-recovery')
            self.o['repair_facts'][key]='satisfied'
    def test_budget_exhaustion(self):
        self.o['metadata']='violated';self.o['repair_attempts']=2
        self.assertEqual(self.go()['action'],'preserve-evidence-and-plan-offline-recovery')
    def test_no_unknown_extension(self):self.o['automatically_trust_me']=True;self.assertRaises(Invalid,self.go)
    def test_policy_no_forced_repair(self):
        for k in ('generic_force_repair_allowed','log_zeroing_allowed','mount_norecovery_allowed','fsverity_assumed',
                  'metadata_healthy_is_content_healthy','production_qualified'):
            p=copy.deepcopy(self.p);p[k]=True;self.assertRaises(Invalid,check_policy,p)
    def test_zero_digest_not_binding(self):
        self.e['cohort']['kernel']=self.o['subject']['cohort']['kernel']='0'*64
        self.assertRaises(Invalid,self.go)
    def test_current_policy(self):self.assertTrue(check_policy(self.p)['policy_valid'])

class ReadOnlyInventory(unittest.TestCase):
    def test_mountinfo_parse(self):
        r=parse_mountinfo(b'37 1 8:2 / / rw,relatime - xfs /dev/mapper/root rw\n')[0]
        self.assertEqual(r['filesystem'],'xfs');self.assertEqual(r['mount_id'],37)
    def test_mountinfo_spaces(self):
        r=parse_mountinfo(b'37 1 8:2 / /a\\040b rw - xfs /dev/a rw\n')[0]
        self.assertEqual(r['mount_point'],'/a b')
    def test_namespace_external_bind_root(self):
        r=parse_mountinfo(b'37 1 0:42 /../../../../../.. /run/host rw - btrfs /dev/a rw\n')[0]
        self.assertEqual(r['root'],'/../../../../../..')
        self.assertEqual(r['mount_point'],'/run/host')
    def test_relative_mount_root_rejected(self):
        self.assertRaises(Invalid,parse_mountinfo,b'37 1 0:42 ../outside /run/host rw - btrfs /dev/a rw\n')
    def test_duplicate_id(self):
        self.assertRaises(Invalid,parse_mountinfo,b'37 1 8:2 / / rw - xfs /dev/a rw\n37 1 8:3 / /b rw - xfs /dev/b rw\n')
    def test_traversal(self):self.assertRaises(Invalid,parse_mountinfo,b'37 1 8:2 / /a/../b rw - xfs /dev/a rw\n')
    def test_live_mount_inventory(self):
        r=inspect_local('/');self.assertFalse(r['execution_permit'])
        self.assertEqual(r['metadata_health'],'unknown');self.assertEqual(r['healthmon'],'not-probed')
    def test_nonmount_rejected(self):
        with tempfile.TemporaryDirectory() as d:self.assertRaises(Invalid,inspect_local,d)
    def test_symlink_mount_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'alias';p.symlink_to('/');self.assertRaises(Invalid,inspect_local,str(p))

if __name__=='__main__':unittest.main()

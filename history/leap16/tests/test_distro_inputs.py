# SPDX-License-Identifier: MIT
"""Executes actual build-time verifier/renderer against synthetic signed RPM-MD.
These are NOT valid RPM payloads and NOT tests of Ada, KIWI boot or vendor keys.
"""
from __future__ import annotations
import copy,gzip,hashlib,importlib.util,json,os,sys,tempfile,unittest,xml.etree.ElementTree as ET
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
D=Path(__file__).resolve().parents[1];sys.path.insert(0,str(D/'tools'))
import distroctl as dc
import repo_metadata as rm
H=lambda b:hashlib.sha256(b).hexdigest()
class Inputs(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.cache=self.root/'cache';self.cache.mkdir(mode=0o700)
  self.prof=dc.profile(D,'leap-16.0');self.now=1000
  self.private={r:Ed25519PrivateKey.from_private_bytes(hashlib.sha256(('PUBLIC ARTIFICIAL TEST ONLY '+r).encode()).digest()) for r in ('build','security')}
  self.trust={'format':1,'test_only':True,'not_before':900,'expires':2000,'profile':'leap-16.0','keys':[
   {'id':r+'-fixture','role':r,'domain':r+'-domain','public_key':k.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()}
   for r,k in self.private.items()]}
  self.rpm=b'PUBLIC SYNTHETIC BYTES, NOT AN INSTALLABLE RPM\n';self.put('repos/main/x86_64/unit-1-1.x86_64.rpm',self.rpm)
  self.put('keys/upstream-test.key',b'public-key-placeholder: not a vendor key\n')
  self.primary=('''<metadata xmlns="http://linux.duke.edu/metadata/common" packages="1"><package type="rpm"><name>unit</name><arch>x86_64</arch><version epoch="0" ver="1" rel="1"/><checksum type="sha256">'''+H(self.rpm)+'''</checksum><location href="x86_64/unit-1-1.x86_64.rpm"/></package></metadata>''').encode()
  self.payload={'format':1,'profile':'leap-16.0','family':'openSUSE-Leap','architecture':'x86_64','generation':7,'not_before':990,'expires':1100,
   'source_set':'1'*64,'contract_profile':'2'*64,'profile_sha256':H(dc.canonical(self.prof)),
   'repositories':[{'id':'main','family':'openSUSE-Leap','release':'16.0','upstream_url':'https://download.opensuse.org/distribution/leap/16.0/repo/oss/',
   'snapshot_path':'repos/main','repomd_sha256':'3'*64,'key_path':'keys/upstream-test.key','key_sha256':H((self.cache/'keys/upstream-test.key').read_bytes())}],
   'packages':[{'name':'unit','epoch':0,'version':'1','release':'1','arch':'x86_64','repo':'main','path':'repos/main/x86_64/unit-1-1.x86_64.rpm','sha256':H(self.rpm),'stage':'bootstrap'}],
   'input_files':[],'obligations':{'upstream-rpm-signatures':'not-run','installed-closure':'not-run'}}
  # Derive the exact family spelling from the externally selected profile.
  self.payload['family']=self.prof['family'];self.payload['repositories'][0]['family']=self.prof['family']
  self.catalog(self.primary);self.lock=self.sign()
 def tearDown(self):self.tmp.cleanup()
 def put(self,p,b):
  x=self.cache/p;x.parent.mkdir(parents=True,exist_ok=True);x.write_bytes(b)
 def catalog(self,raw):
  compressed=gzip.compress(raw,mtime=0);self.put('repos/main/repodata/primary.xml.gz',compressed)
  repomd=('''<repomd xmlns="http://linux.duke.edu/metadata/repo"><data type="primary"><checksum type="sha256">'''+H(compressed)+'''</checksum><location href="repodata/primary.xml.gz"/><size>'''+str(len(compressed))+'''</size><open-checksum type="sha256">'''+H(raw)+'''</open-checksum><open-size>'''+str(len(raw))+'''</open-size></data></repomd>''').encode()
  self.put('repos/main/repodata/repomd.xml',repomd);self.payload['repositories'][0]['repomd_sha256']=H(repomd);self.manifest()
 def manifest(self):
  self.payload['input_files']=[{'path':p.relative_to(self.cache).as_posix(),'sha256':H(p.read_bytes())} for p in sorted(self.cache.rglob('*')) if p.is_file() and not p.is_symlink()]
 def sign(self):
  p=copy.deepcopy(self.payload);msg=dc.DOMAIN+dc.canonical(p)
  return {'format':1,'payload':p,'signatures':[{'role':r,'key_id':r+'-fixture','signature':k.sign(r.encode()+b'\0'+msg).hex()} for r,k in self.private.items()]}
 def verify(self,e=None,t=None,**kw):
  args=dict(minimum_generation=7,allow_test=True,expected_source='1'*64,expected_contract='2'*64);args.update(kw)
  return dc.verify(e or self.lock,t or self.trust,self.prof,self.cache,self.now,**args)
 def reject(self,**kw):
  with self.assertRaises((ValueError,OSError,TypeError)):self.verify(**kw)
 def test_valid_input_not_qualified(self):
  r=self.verify();self.assertEqual(r['result'],'verified-inputs');self.assertFalse(r['production_qualified']);self.assertFalse(r['upstream_rpm_signatures_verified_by_this_tool'])
 def test_unknown_envelope_field(self):
  self.lock['execute']=True;self.reject()
 def test_no_independent_source(self):self.reject(expected_source=None)
 def test_wrong_source(self):self.reject(expected_source='9'*64)
 def test_wrong_contract(self):self.reject(expected_contract='9'*64)
 def test_release_downgrade(self):self.reject(minimum_generation=8)
 def test_expired(self):self.now=1100;self.reject()
 def test_future(self):self.now=980;self.reject()
 def test_test_trust_forbidden_in_cli_mode(self):self.reject(allow_test=False)
 def test_signature_byte_changed(self):
  x=self.lock['signatures'][0]['signature'];self.lock['signatures'][0]['signature']=('00' if x[:2]!='00' else '01')+x[2:];self.reject()
 def test_payload_modified_without_signature(self):self.lock['payload']['generation']=8;self.reject()
 def test_same_authority_key(self):self.trust['keys'][1]['public_key']=self.trust['keys'][0]['public_key'];self.reject()
 def test_same_authority_domain(self):self.trust['keys'][1]['domain']=self.trust['keys'][0]['domain'];self.reject()
 def test_duplicate_signature_role(self):self.lock['signatures'][1]=self.lock['signatures'][0];self.reject()
 def test_cross_family_repository(self):self.payload['repositories'][0]['family']='SLES';self.reject(e=self.sign())
 def test_cross_profile(self):self.payload['profile']='sles-16.0';self.reject(e=self.sign())
 def test_profile_security_drift(self):self.prof['secure_boot_required']=False;self.reject()
 def test_same_authority_identity(self):self.trust['keys'][1]['id']=self.trust['keys'][0]['id'];self.reject()
 def test_signed_weakened_profile_refused(self):
  self.prof['secure_boot_required']=False;self.payload['profile_sha256']=H(dc.canonical(self.prof));self.reject(e=self.sign())
 def test_qualification_claim_refused_even_if_signed(self):
  self.prof['production_qualified']=True;self.payload['profile_sha256']=H(dc.canonical(self.prof));self.reject(e=self.sign())
 def test_wrong_family_label_refused_even_if_consistent(self):
  self.prof['family']='sles';self.payload['family']='sles';self.payload['repositories'][0]['family']='sles'
  self.payload['profile_sha256']=H(dc.canonical(self.prof));self.reject(e=self.sign())
 def test_unknown_profile_field_refused(self):
  self.prof['disable_verification']=False;self.payload['profile_sha256']=H(dc.canonical(self.prof));self.reject(e=self.sign())
 def test_host_ownership_change_refused(self):
  self.prof['host_package_owner']='mission';self.payload['profile_sha256']=H(dc.canonical(self.prof));self.reject(e=self.sign())
 def test_subscription_claim_refused(self):
  self.prof['subscription_required']=True;self.payload['profile_sha256']=H(dc.canonical(self.prof));self.reject(e=self.sign())
 def test_url_credentials(self):self.payload['repositories'][0]['upstream_url']='https://user:password@example.invalid/';self.reject(e=self.sign())
 def test_url_plaintext(self):self.payload['repositories'][0]['upstream_url']='http://example.invalid/';self.reject(e=self.sign())
 def test_package_bytes_change(self):self.put(self.payload['packages'][0]['path'],b'changed');self.reject()
 def test_metadata_mismatch(self):self.catalog(self.primary.replace(b'<name>unit</name>',b'<name>another</name>'));self.reject(e=self.sign())
 def test_metadata_external_path(self):self.catalog(self.primary.replace(b'x86_64/unit-1-1.x86_64.rpm',b'https://example.invalid/evil.rpm'));self.reject(e=self.sign())
 def test_metadata_parent_path(self):self.catalog(self.primary.replace(b'x86_64/unit-1-1.x86_64.rpm',b'../../evil.rpm'));self.reject(e=self.sign())
 def test_metadata_entity(self):
  self.catalog(b'<!DOCTYPE metadata [<!ENTITY x SYSTEM "file:///etc/hostname">]>'+self.primary);self.reject(e=self.sign())
 def test_metadata_count(self):self.catalog(self.primary.replace(b'packages="1"',b'packages="2"'));self.reject(e=self.sign())
 def test_metadata_hash(self):self.put('repos/main/repodata/primary.xml.gz',gzip.compress(self.primary+b' ',mtime=0));self.reject()
 def test_extra_file(self):self.put('unlisted',b'x');self.reject()
 def test_missing_file(self):(self.cache/self.payload['packages'][0]['path']).unlink();self.reject()
 def test_fifo(self):os.mkfifo(self.cache/'fifo');self.reject()
 def test_symlink(self):(self.cache/'link').symlink_to('/etc/hostname');self.reject()
 def test_symlink_directory(self):(self.cache/'linked-dir').symlink_to(self.root,target_is_directory=True);self.reject()
 def test_duplicate_package_path(self):
  x=copy.deepcopy(self.payload['packages'][0]);x['name']='other';self.payload['packages'].append(x);self.reject(e=self.sign())
 def test_duplicate_json(self):
  p=self.root/'bad.json';p.write_text('{"x":1,"x":2}')
  with self.assertRaises(ValueError):dc.read_json(p)
 def test_floats_refused(self):
  p=self.root/'bad.json';p.write_text('{"x":1.5}')
  with self.assertRaises(ValueError):dc.read_json(p)
 def test_nonregular_json_refused(self):
  p=self.root/'fifo';os.mkfifo(p)
  with self.assertRaises(ValueError):dc.read_json(p)
 def test_no_false_boolean_format(self):self.lock['format']=True;self.reject()
 def test_render_no_boot_activation(self):
  self.verify();b=dc.render(self.payload,self.cache);root=ET.fromstring(b)
  typ=root.find('preferences/type');self.assertEqual(typ.get('firmware'),'uefi');self.assertEqual(typ.find('bootloader').get('bls'),'false')
  self.assertEqual(root.find('preferences/rpm-check-signatures').text,'true')
  for r in root.findall('repository'):
   self.assertEqual(r.get('repository_gpgcheck'),'true');self.assertEqual(r.get('package_gpgcheck'),'true');self.assertTrue(r.find('source').get('path').startswith('file:///'))
  self.assertNotIn(b'password',b);self.assertNotIn(b'<scripts',b)
 def test_output_no_overwrite(self):
  p=self.root/'out';dc.write_new(p,b'first')
  with self.assertRaises(FileExistsError):dc.write_new(p,b'second')
  self.assertEqual(p.read_bytes(),b'first')
 def test_only_public_leap_active(self):
  a=dc.profile(D,'leap-16.0');self.assertEqual(a['family'],'opensuse-leap');self.assertFalse(a['subscription_required'])
  with self.assertRaises(ValueError):dc.profile(D,'sles-16.0')
 def test_subscription_repository_even_if_mislabeled(self):
  self.payload['repositories'][0]['upstream_url']='https://updates.suse.com/SUSE/Products/SLE/';self.reject(e=self.sign())
 def test_unadmitted_source_host(self):
  self.payload['repositories'][0]['upstream_url']='https://download.opensuse.org.evil.invalid/repo/';self.reject(e=self.sign())
 def test_historical_profile_cannot_be_readmitted(self):
  old=dc.read_json(D/'docs/historical-profiles/sles-16.0.json')
  with self.assertRaises(ValueError):dc.validate_profile(old)
 def test_unknown_profile(self):
  with self.assertRaises(ValueError):dc.profile(D,'fedora')
if __name__=='__main__':unittest.main()

# SPDX-License-Identifier: MIT
"""Actual native DEB/GPG test fixtures, no installation, no service operations."""
import base64,copy,email.utils,gzip,hashlib,io,json,lzma,os,random,shutil,subprocess,sys,tarfile,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nia_common import Invalid,sha,canonical,parse_json,read_file,write_new
from deb_archive import inspect_bytes,ar_members,tar_inventory,decompress,deb822
from debian_semantics import compare,split_version,relations,check_final,provider_matches,Atom
from debian_archive_auth import verify_snapshot,authenticated_release,verify_source
from reproducibility import check_receipts,check_buildinfo,DOMAIN
from nia_policy import check_profile,readiness
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

class NativeFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not all(shutil.which(x) for x in ('gpg','gpgv','dpkg-deb')):raise unittest.SkipTest('native offline tools unavailable')
        cls.temp=tempfile.TemporaryDirectory(prefix='nia-intake-test-');cls.root=Path(cls.temp.name)
        cls.home=cls.root/'gnupg';cls.home.mkdir(mode=0o700)
        cls.now=int(time.time());cls.snapshot=cls.root/'snapshot';cls.snapshot.mkdir()
        pkg=cls.root/'package';(pkg/'DEBIAN').mkdir(parents=True);(pkg/'etc').mkdir()
        (pkg/'DEBIAN/control').write_text('Package: nia-test\nVersion: 1:2.0~rc1-3\nArchitecture: all\nMaintainer: Nia synthetic fixture\nDescription: not for installation\n')
        (pkg/'DEBIAN/conffiles').write_text('/etc/nia-test.conf\n')
        (pkg/'DEBIAN/postinst').write_text('#!/bin/sh\necho forbidden > '+str(cls.root/'SCRIPT_WAS_EXECUTED')+'\n')
        (pkg/'DEBIAN/postinst').chmod(0o755);(pkg/'etc/nia-test.conf').write_text('mode=safe\n')
        subprocess.run(['dpkg-deb','--build','--root-owner-group','-Zxz',str(pkg),str(cls.root/'test.deb')],check=True,capture_output=True)
        cls.deb=(cls.root/'test.deb').read_bytes();cls.path='pool/main/n/nia-test/nia-test_2.0_all.deb'
        (cls.snapshot/cls.path).parent.mkdir(parents=True);(cls.snapshot/cls.path).write_bytes(cls.deb)
        cls.index='main/binary-amd64/Packages.xz';cls.packages=(f'Package: nia-test\nVersion: 1:2.0~rc1-3\nArchitecture: all\nFilename: {cls.path}\nSize: {len(cls.deb)}\nSHA256: {sha(cls.deb)}\n\n').encode()
        cls.packed=lzma.compress(cls.packages)
        (cls.snapshot/'dists/forky'/cls.index).parent.mkdir(parents=True)
        (cls.snapshot/'dists/forky'/cls.index).write_bytes(cls.packed)
        env=os.environ|{'GNUPGHOME':str(cls.home),'LC_ALL':'C'};cls.env=env
        subprocess.run(['gpg','--batch','--pinentry-mode','loopback','--passphrase','','--quick-generate-key','Nia artificial fixture','ed25519','sign','0'],check=True,capture_output=True,env=env)
        keys=subprocess.check_output(['gpg','--batch','--with-colons','--list-keys'],env=env,stderr=subprocess.DEVNULL).decode()
        cls.fpr=next(l.split(':')[9] for l in keys.splitlines() if l.startswith('fpr:'))
        cls.keyring=subprocess.check_output(['gpg','--batch','--export',cls.fpr],env=env)
        cls.policy={'schema':'org.niaos.debian-trust/v1','keyring_sha256':sha(cls.keyring),'primary_fingerprints':[cls.fpr],
            'minimum_signatures':1,'now':cls.now,'max_age_seconds':86400,'future_skew_seconds':60}
        cls.release=cls.make_release()
        cls.signed=cls.sign(cls.release)
        (cls.snapshot/'dists/forky/InRelease').write_bytes(cls.signed)
    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'home'):
            subprocess.run(['gpgconf','--homedir',str(cls.home),'--kill','gpg-agent'],capture_output=True,check=False)
        if hasattr(cls,'temp'):cls.temp.cleanup()
    @classmethod
    def make_release(cls,**overrides):
        r={'Origin':'Debian','Label':'Debian','Suite':'testing','Codename':'forky','Date':email.utils.formatdate(cls.now-60,usegmt=True),
            'Valid-Until':email.utils.formatdate(cls.now+3600,usegmt=True),'Architectures':'amd64 all','Components':'main'}
        r.update(overrides)
        return ('\n'.join(k+': '+v for k,v in r.items())+f'\nSHA256:\n {sha(cls.packed)} {len(cls.packed)} {cls.index}\n').encode()
    @classmethod
    def sign(cls,data):
        (cls.root/'release-to-sign').write_bytes(data)
        subprocess.run(['gpg','--batch','--yes','--armor','--pinentry-mode','loopback','--passphrase','',
            '--output',str(cls.root/'signed'),'--clearsign',str(cls.root/'release-to-sign')],capture_output=True,check=True,env=cls.env)
        return (cls.root/'signed').read_bytes()
    def setUp(self):
        (self.snapshot/self.path).write_bytes(self.deb)
        (self.snapshot/'dists/forky'/self.index).write_bytes(self.packed)
        (self.snapshot/'dists/forky/InRelease').write_bytes(self.signed)
    def verify(self,policy=None):return verify_snapshot(self.snapshot,self.keyring,policy or self.policy,self.index,self.path)
    def test_authentic_synthetic_chain(self):
        r=self.verify();self.assertTrue(r['observation']['archive_authenticated']);self.assertFalse(r['execution_permit']);self.assertFalse(r['reproduced'])
    def test_hooks_not_run(self):
        r=self.verify()['observation'];self.assertEqual(r['effect_members'][0]['member'],'postinst');self.assertFalse((self.root/'SCRIPT_WAS_EXECUTED').exists())
    def test_metadata_and_conffile(self):
        r=inspect_bytes(self.deb);self.assertEqual(r['conffiles'][0]['path'],'etc/nia-test.conf')
        f=next(x for x in r['file_inventory'] if x['path']=='etc/nia-test.conf');self.assertEqual(f['sha256'],sha(b'mode=safe\n'));self.assertEqual(f['uid'],0)
    def test_deb_mutation(self):
        (self.snapshot/self.path).write_bytes(self.deb[:-1]+bytes([self.deb[-1]^1]));self.assertRaises(Invalid,self.verify)
    def test_index_mutation(self):
        (self.snapshot/'dists/forky'/self.index).write_bytes(self.packed+b'\0');self.assertRaises(Invalid,self.verify)
    def test_signed_release_mutation(self):
        (self.snapshot/'dists/forky/InRelease').write_bytes(self.signed.replace(b'forky',b'trixie'));self.assertRaises(Invalid,self.verify)
    def test_wrong_key(self):
        p=copy.deepcopy(self.policy);p['primary_fingerprints']=['A'*40];self.assertRaises(Invalid,self.verify,p)
    def test_keyring_hash(self):
        p=copy.deepcopy(self.policy);p['keyring_sha256']='0'*64;self.assertRaises(Invalid,self.verify,p)
    def test_expiry(self):
        p=copy.deepcopy(self.policy);p['now']+=4000;self.assertRaises(Invalid,self.verify,p)
    def test_date_future(self):
        (self.snapshot/'dists/forky/InRelease').write_bytes(self.sign(self.make_release(Date=email.utils.formatdate(self.now+500,usegmt=True))))
        self.assertRaises(Invalid,self.verify)
    def test_cross_distribution(self):
        (self.snapshot/'dists/forky/InRelease').write_bytes(self.sign(self.make_release(Origin='openSUSE')));self.assertRaises(Invalid,self.verify)
    def test_rollback_suite(self):
        (self.snapshot/'dists/forky/InRelease').write_bytes(self.sign(self.make_release(Codename='trixie')));self.assertRaises(Invalid,self.verify)
    def test_empty_valid_until(self):
        (self.snapshot/'dists/forky/InRelease').write_bytes(self.sign(self.make_release(**{'Valid-Until':''})));self.assertRaises(Invalid,self.verify)
    def test_no_network_no_index_selection(self):self.assertRaises(Invalid,verify_snapshot,self.snapshot,self.keyring,self.policy,'../Packages',self.path)
    def test_symlinked_package(self):
        (self.snapshot/self.path).unlink();(self.snapshot/self.path).symlink_to(self.root/'test.deb')
        try:self.assertRaises((Invalid,OSError),self.verify)
        finally:(self.snapshot/self.path).unlink()
    def test_zstd_archive(self):
        subprocess.run(['dpkg-deb','--build','--root-owner-group','-Zzstd',str(self.root/'package'),str(self.root/'zstd.deb')],check=True,capture_output=True)
        self.assertEqual(inspect_bytes((self.root/'zstd.deb').read_bytes())['identity']['package'],'nia-test')
    def test_truncated_ar(self):self.assertRaises(Invalid,inspect_bytes,self.deb[:-1])
    def test_extended_ar_rejected(self):self.assertRaises(Invalid,inspect_bytes,self.deb+b'invented extension')

    def prepare_source(self):
        sources_path='main/source/Sources.xz';directory='pool/main/n/nia-test'
        files={'nia-test_2.dsc':b'Format: 3.0 (native)\nSource: nia-test\n', 'nia-test_2.tar.xz':b'SYNTHETIC SOURCE OBJECT NOT A BUILD'}
        for n,b in files.items():(self.snapshot/directory/n).write_bytes(b)
        source=(f'Package: nia-test\nVersion: 1:2.0~rc1-3\nBinary: nia-test\nDirectory: {directory}\nChecksums-Sha256:\n'+''.join(f' {sha(b)} {len(b)} {n}\n' for n,b in files.items())).encode()
        packed=lzma.compress(source);(self.snapshot/'dists/forky'/sources_path).parent.mkdir(parents=True,exist_ok=True)
        (self.snapshot/'dists/forky'/sources_path).write_bytes(packed)
        signed=self.sign(self.release+f' {sha(packed)} {len(packed)} {sources_path}\n'.encode())
        (self.snapshot/'dists/forky/InRelease').write_bytes(signed)
        return sources_path,directory,files
    def test_source_chain(self):
        src,_,_=self.prepare_source();r=verify_source(self.snapshot,self.keyring,self.policy,self.index,self.path,src)
        self.assertTrue(r['source_authenticated']);self.assertFalse(r['reproduced']);self.assertEqual(len(r['source_manifest']['files']),2)
    def test_source_mutation(self):
        src,d,fs=self.prepare_source();(self.snapshot/d/next(iter(fs))).write_bytes(b'tampered')
        self.assertRaises(Invalid,verify_source,self.snapshot,self.keyring,self.policy,self.index,self.path,src)
    def test_source_missing(self):
        src,d,fs=self.prepare_source();(self.snapshot/d/next(iter(fs))).unlink()
        self.assertRaises((Invalid,OSError),verify_source,self.snapshot,self.keyring,self.policy,self.index,self.path,src)
    def test_composition_not_installation(self):
        from nia_catalog import candidate
        result=candidate([self.verify()['observation']],['nia-test'],'a'*64)
        self.assertEqual(result['catalog']['native_database'],'nia-catalog-v1');self.assertFalse(result['execution_permit'])
        self.assertFalse(result['catalog']['effects_closed']);self.assertFalse(result['catalog']['phase_schedule_checked'])
    def test_composition_conflicting_file(self):
        from nia_catalog import candidate
        a=self.verify()['observation'];b=copy.deepcopy(a);b['artifact_sha256']='1'*64;b['identity']['package']='other'
        self.assertRaises(Invalid,candidate,[a,b],['nia-test'],'a'*64)
    def test_composition_root_requirement(self):
        from nia_catalog import candidate
        self.assertRaises(Invalid,candidate,[self.verify()['observation']],['absent'],'a'*64)

class ParserTests(unittest.TestCase):
    def test_duplicate_field(self):self.assertRaises(Invalid,deb822,b'Package: a\npackage: b\n')
    def test_orphan_continuation(self):self.assertRaises(Invalid,deb822,b' orphan\n')
    def test_concatenated_compression(self):self.assertRaises(Invalid,decompress,'control.tar.gz',gzip.compress(b'aaa')+gzip.compress(b'bbb'),100)
    def test_decompress_limit(self):self.assertRaises(Invalid,decompress,'data.tar.xz',lzma.compress(b'x'*10000),100)
    def test_zstd_limit(self):
        raw=subprocess.check_output(['zstd','-q','-c'],input=b'a'*10000)
        self.assertRaises(Invalid,decompress,'data.tar.zst',raw,100)
    def tar(self,name,kind=tarfile.REGTYPE,link=''):
        out=io.BytesIO()
        with tarfile.open(fileobj=out,mode='w',format=tarfile.USTAR_FORMAT) as t:
            i=tarfile.TarInfo(name);i.type=kind;i.linkname=link;i.mode=0o644;i.size=1 if kind==tarfile.REGTYPE else 0;t.addfile(i,io.BytesIO(b'x') if i.size else None)
        return out.getvalue()
    def test_tar_traversal(self):self.assertRaises(Invalid,tar_inventory,self.tar('../escape'))
    def test_tar_device(self):self.assertRaises(Invalid,tar_inventory,self.tar('dev/test',tarfile.CHRTYPE))
    def test_tar_escaped_symlink(self):self.assertRaises(Invalid,tar_inventory,self.tar('file',tarfile.SYMTYPE,'../../etc/passwd'))
    def test_tar_missing_hardlink(self):self.assertRaises(Invalid,tar_inventory,self.tar('file',tarfile.LNKTYPE,'no-file'))
    def test_tar_trailing(self):self.assertRaises(Invalid,tar_inventory,self.tar('ok')+b'X'*512)
    def test_json_duplicate(self):self.assertRaises(Invalid,parse_json,b'{"a":1,"a":2}')
    def test_json_float(self):self.assertRaises(Invalid,parse_json,b'{"a":1.5}')
    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'out';write_new(p,b'a');self.assertRaises(OSError,write_new,p,b'b');self.assertEqual(read_file(p),b'a')
    def test_fifo_read_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fifo';os.mkfifo(p);self.assertRaises((Invalid,OSError),read_file,p)

class SemanticsTests(unittest.TestCase):
    def test_tilde_and_epoch(self):
        for a,b in [('1.0~rc1','1.0'),('1.0','1.0-1'),('1.9','1:0'),('1a','1+'),('1~~','1~')]:self.assertLess(compare(a,b),0)
        self.assertEqual(compare('1.01','1.1-0'),0)
    def test_invalid_versions(self):
        for s in ['','a1','1-','1:','2147483648:1','1\n2','1:1-2_3']:self.assertRaises(Invalid,split_version,s)
    def test_actual_dpkg_differential(self):
        r=random.Random(191);versions=['0','1:0','1.0','1.0-0','1.00','1~~1','2:1.0+git-2','1:2:3-1']
        for _ in range(48):versions.append(f'{r.randrange(3)}:{r.randrange(10)}.{r.randrange(30)}'+r.choice(['','~rc1','+dfsg','a'])+f'-{r.randrange(5)}')
        for _ in range(128):
            a,b=r.choices(versions,k=2);v=compare(a,b);op='lt' if v<0 else 'gt' if v>0 else 'eq'
            status=subprocess.run(['dpkg','--compare-versions',a,op,b],capture_output=True).returncode
            self.assertEqual(status,0,(a,b,v))
    def candidate(self,**changes):
        p={'id':'a','name':'aa','version':'1','architecture':'amd64','multi_arch':'no'};p.update(changes);return p
    def test_versioned_virtual(self):
        a=self.candidate(depends='virtual (>= 2)');b=self.candidate(id='b',name='bb',provides=[('virtual',None)])
        self.assertRaises(Invalid,check_final,[a,b],{'a','b'});b['provides']=[('virtual','2')];check_final([a,b],{'a','b'})
    def test_or_alternative(self):check_final([self.candidate(depends='not-installed | aa')],{'a'})
    def test_self_conflict(self):check_final([self.candidate(conflicts='virtual',provides=[('virtual',None)])],{'a'})
    def test_unselected_requirements(self):check_final([self.candidate(),self.candidate(id='b',name='bb',depends='absent')],{'a'})
    def test_breaks_and_conflicts(self):
        for field in ('breaks','conflicts'):
            self.assertRaises(Invalid,check_final,[self.candidate(**{field:'bb'}),self.candidate(id='b',name='bb')],{'a','b'})
    def test_duplicate_version(self):self.assertRaises(Invalid,check_final,[self.candidate(),self.candidate(id='b',version='2')],{'a','b'})
    def test_multiarch_any(self):
        a=Atom('aa','any');self.assertFalse(provider_matches(self.candidate(multi_arch='foreign'),a));self.assertTrue(provider_matches(self.candidate(multi_arch='allowed'),a))
    def test_build_source_syntax_rejected(self):
        for s in ['aa [amd64]','aa <cross>','aa:arm64']:
            self.assertRaises(Invalid,relations,s)
    def test_replaces_is_not_dependency(self):self.assertRaises(Invalid,check_final,[self.candidate(depends='bb',replaces='bb')],{'a'})

class ReproductionTests(unittest.TestCase):
    def setUp(self):
        self.now=2000000;self.release='b'*64;self.policy='c'*64
        self.subject={'deb_sha256':'d'*64,'source_manifest_sha256':'e'*64,'buildinfo_sha256':'f'*64,'package':'nia-test','version':'1','architecture':'amd64'}
        self.keys={k:Ed25519PrivateKey.generate() for k in ('one','two')}
        self.registry={k:{'public_key':v.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex(),
            'principal':k,'domain':'domain-'+k,'revoked':False,'valid_from':1,'valid_until':3000000} for k,v in self.keys.items()}
        self.receipts=[]
        for k in self.keys:self.receipts.append(self.signed(k))
    def signed(self,k,**changes):
        b={'schema':'org.niaos.reproduction/v1','subject':self.subject,'release_sha256':self.release,'policy_sha256':self.policy,
           'rebuilder':k,'domain':'domain-'+k,'key_id':k,'issued':self.now-20,'expires':self.now+3600,'observed_sha256':'d'*64,'method':'rebuild-official-binary'}
        b.update(changes);return {'body':b,'signature':base64.b64encode(self.keys[k].sign(DOMAIN+canonical(b))).decode()}
    def check(self,r=None):return check_receipts(r or self.receipts,self.subject,self.registry,self.now,self.release,self.policy)
    def test_independent_exact(self):self.assertEqual(self.check()['independent_receipts'],2)
    def test_same_observer(self):self.assertRaises(Invalid,self.check,[self.receipts[0],self.receipts[0]])
    def test_wrong_binary(self):self.assertRaises(Invalid,self.check,[self.signed('one',observed_sha256='1'*64),self.receipts[1]])
    def test_expired(self):self.assertRaises(Invalid,self.check,[self.signed('one',expires=self.now),self.receipts[1]])
    def test_revoked(self):self.registry['one']['revoked']=True;self.assertRaises(Invalid,self.check)
    def test_bad_signature(self):self.receipts[0]['signature']=base64.b64encode(b'\0'*64).decode();self.assertRaises(Invalid,self.check)
    def test_self_asserted_domain(self):self.assertRaises(Invalid,self.check,[self.signed('one',domain='different'),self.receipts[1]])
    def test_two_keys_one_domain(self):self.registry['two']['domain']='domain-one';self.receipts[1]=self.signed('two',domain='domain-one');self.assertRaises(Invalid,self.check)
    def test_missing_witness(self):self.assertRaises(Invalid,self.check,[self.receipts[0]])
    def test_key_valid_from_boolean(self):self.registry['one']['valid_from']=True;self.assertRaises(Invalid,self.check)
    def test_key_valid_until_boolean(self):self.registry['one']['valid_until']=True;self.assertRaises(Invalid,self.check)
    def test_key_domain_control_character(self):self.registry['one']['domain']='bad\n';self.assertRaises(Invalid,self.check)
    def test_buildinfo_binary_checksum(self):
        raw=b'Format: 1.0\nSource: nia-test\nBinary: nia-test\nArchitecture: amd64\nVersion: 1\nInstalled-Build-Depends: libc6 (= 2)\nChecksums-Sha256:\n '+b'd'*64+b' 10 nia-test_1_amd64.deb\n'
        s=self.subject|{'buildinfo_sha256':sha(raw)};self.assertFalse(check_buildinfo(raw,s)['reproduced'])
    def test_buildinfo_no_binary(self):self.assertRaises(Invalid,check_buildinfo,b'Format: 1.0\n',self.subject)

class ProductTests(unittest.TestCase):
    def setUp(self):self.profile=json.loads((Path(__file__).resolve().parents[1]/'profiles/nia-os.json').read_text())
    def test_current(self):self.assertFalse(check_profile(self.profile)['production_qualified'])
    def test_old_supply(self):self.profile['supply']['distribution']='opensuse';self.assertRaises(Invalid,check_profile,self.profile)
    def test_boolean_is_not_integer(self):self.profile['system']['secure_boot_required']=1;self.assertRaises(Invalid,check_profile,self.profile)
    def test_native_writer(self):self.profile['ownership']['native_manager_writers']=['dpkg'];self.assertRaises(Invalid,check_profile,self.profile)
    def test_script_execution(self):self.profile['ownership']['maintainer_scripts']='run-root';self.assertRaises(Invalid,check_profile,self.profile)
    def test_secureboot(self):self.profile['system']['secure_boot_required']=False;self.assertRaises(Invalid,check_profile,self.profile)
    def test_rolling_alias(self):self.profile['supply']['rolling_aliases']=True;self.assertRaises(Invalid,check_profile,self.profile)
    def test_false_production_claim(self):self.profile['product']['production_qualified']=True;self.assertRaises(Invalid,check_profile,self.profile)
    def test_readiness_no_self_attested_pass(self):self.assertRaises(Invalid,readiness,'a'*64,[{'gate':'toolchain-build','state':'pass','scope_sha256':'a'*64,'evidence_ref':'fake'}])
    def test_readiness_defaults(self):self.assertTrue(all(x['state']=='missing' for x in readiness('a'*64,[])['gates']))

if __name__=='__main__':unittest.main(verbosity=2)

class AdditionalProductRegressions(unittest.TestCase):
    def test_same_name_all_native_not_coinstalled(self):
        p={'id':'a','name':'foo','version':'1','architecture':'all'}
        q={'id':'b','name':'foo','version':'2','architecture':'amd64'}
        with self.assertRaises(Invalid):check_final([p,q],{'a','b'})
    def test_single_name_version_replacement_final_allowed(self):
        p={'id':'a','name':'foo','version':'1','architecture':'all'}
        q={'id':'b','name':'foo','version':'2','architecture':'amd64'}
        self.assertFalse(check_final([p,q],{'b'})['execution_permit'])
    def test_relative_surrogate_rejected(self):
        from nia_common import relative
        with self.assertRaises(Invalid):relative('etc/\udcff')

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline SUSE release-input verifier and KIWI descriptor renderer (build tooling).
No package installation, network fetch, private-key signing or production admission.
Two independent, externally provisioned public keys approve exact input bytes.
This checks acceptance signatures/hashes, NOT upstream RPM signatures or bootability.
"""
from __future__ import annotations
import argparse,hashlib,json,os,re,stat,sys,time,xml.etree.ElementTree as ET
from pathlib import Path,PurePosixPath
from urllib.parse import urlsplit
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from repo_metadata import verify_repository
MAX_JSON=8*1024*1024
DOMAIN=b'MissionCore/suse-release-inputs/v1\0'
HEX=re.compile(r'[0-9a-f]{64}\Z');NAME=re.compile(r'[A-Za-z0-9][A-Za-z0-9+_.-]{0,127}\Z')
class Invalid(ValueError):pass
def exact(obj,keys):
 if not isinstance(obj,dict) or set(obj)!=set(keys.split()):raise Invalid('unknown/missing keys')
def integer(v,minimum=0):
 if type(v) is not int or not minimum<=v<2**63:raise Invalid('noncanonical integer')
 return v
def digest(s):
 if not isinstance(s,str) or not HEX.fullmatch(s) or s=='0'*64:raise Invalid('missing/invalid digest')
 return s
def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def pairs(v):
 d={}
 for k,x in v:
  if k in d:raise Invalid('duplicate JSON key')
  d[k]=x
 return d
def bad_number(s):raise Invalid('floating-point/nonfinite JSON number not supported')
def read_json(path):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
 try:
  a=os.fstat(fd)
  if not stat.S_ISREG(a.st_mode) or a.st_size>MAX_JSON:raise Invalid('unsafe input file')
  data=b''
  while True:
   b=os.read(fd,min(65536,MAX_JSON+1-len(data)))
   if not b:break
   data+=b
   if len(data)>MAX_JSON:raise Invalid('input size limit')
  z=os.fstat(fd)
  if (a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns):raise Invalid('input changed')
 finally:os.close(fd)
 return json.loads(data,object_pairs_hook=pairs,parse_float=bad_number,parse_constant=bad_number)
def relative(s):
 if not isinstance(s,str) or not s or len(s)>2048 or '\\' in s or any(ord(c)<32 or ord(c)>126 for c in s):raise Invalid('invalid path')
 p=PurePosixPath(s)
 if p.is_absolute() or any(x in ('','.', '..') for x in s.split('/')):raise Invalid('unsafe relative path')
 return p
def file_hash(root,rel,limit=2**32):
 parts=relative(rel).parts
 d=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
 try:
  for p in parts[:-1]:
   n=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=d);os.close(d);d=n
  f=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=d)
  try:
   a=os.fstat(f)
   if not stat.S_ISREG(a.st_mode) or a.st_size>limit:raise Invalid('non-regular/oversized artifact')
   h=hashlib.sha256();total=0
   while b:=os.read(f,1024*1024):
    total+=len(b)
    if total>limit:raise Invalid('artifact grew past limit')
    h.update(b)
   z=os.fstat(f)
   if (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns):raise Invalid('artifact changed')
   return h.hexdigest()
  finally:os.close(f)
 finally:os.close(d)
def validate_profile(p):
 exact(p,'format release architecture cpu_baseline update_model host_package_owner mission_owned_roots bootloader bls secure_boot_required selinux network_manager vendor_configuration administrator_configuration temporary_storage kernel_track installer image_builder family_mixing production_qualified id family title cuda_table_status subscription_required sources')
 families={'leap-16.0':'opensuse-leap'}
 if type(p['format']) is not int or p['format']!=1 or p['id'] not in families:raise Invalid('unsupported profile schema')
 required={'release':'16.0','architecture':'x86_64','cpu_baseline':'x86-64-v2','update_model':'mutable',
  'host_package_owner':'native-zypper-rpm','mission_owned_roots':'explicit-separated-roots-only',
  'bootloader':'grub2','selinux':'enforcing','network_manager':'NetworkManager','vendor_configuration':'/usr/etc',
  'administrator_configuration':'/etc','temporary_storage':'tmpfs','kernel_track':'vendor-6.12-with-upstream-fix-watch',
  'installer':'Agama','image_builder':'KIWI-NG'}
 if any(p[k]!=v for k,v in required.items()):raise Invalid('unsupported/weakened target')
 if p['family']!=families[p['id']] or p['bls'] is not False or p['family_mixing'] is not False or p['secure_boot_required'] is not True:raise Invalid('profile/family mismatch')
 # This tool does not confer production qualification, even for signed inputs.
 if p['production_qualified'] is not False or p['subscription_required'] is not False:raise Invalid('invalid qualification/subscription claim')
 for key in ('title','cuda_table_status'):
  if not isinstance(p[key],str) or not 1<=len(p[key])<=256 or any(ord(c)<32 for c in p[key]):raise Invalid('invalid descriptive profile field')
 if not isinstance(p['sources'],list) or not 1<=len(p['sources'])<=16:raise Invalid('profile provenance')
 for source in p['sources']:https(source)
 return p

def profile(root,ident):
 if ident != 'leap-16.0':raise Invalid('unsupported target profile')
 p=validate_profile(read_json(root/'profiles'/f'{ident}.json'))
 if p['id']!=ident:raise Invalid('wrong profile file')
 return p
def https(url):
 if not isinstance(url,str) or any(ord(c)<33 or ord(c)>126 for c in url):raise Invalid('invalid URL')
 u=urlsplit(url)
 if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:raise Invalid('HTTPS credential-free URL required')
 return url

def verify(envelope,trust,prof,cache,now,minimum_generation=1,allow_test=False,expected_source=None,expected_contract=None):
 now=integer(now);validate_profile(prof)
 exact(envelope,'format payload signatures');exact(trust,'format test_only not_before expires profile keys')
 if type(envelope['format']) is not int or type(trust['format']) is not int or envelope['format']!=1 or trust['format']!=1 or type(trust['test_only']) is not bool:raise Invalid('format')
 if trust['test_only'] and not allow_test:raise Invalid('test trust forbidden')
 if trust['profile']!=prof['id'] or not integer(trust['not_before'])<=now<integer(trust['expires']):raise Invalid('trust scope/time')
 if not isinstance(trust['keys'],list) or len(trust['keys'])!=2:raise Invalid('two authorities required')
 roles={};keyset=set();domainset=set();identities=set()
 for k in trust['keys']:
  exact(k,'id role domain public_key')
  if k['role'] not in ('build','security') or k['role'] in roles or not NAME.fullmatch(k['id']) or not NAME.fullmatch(k['domain']):raise Invalid('authority identity')
  digest(k['public_key'])
  if k['public_key'] in keyset or k['domain'] in domainset or k['id'] in identities:raise Invalid('non-independent authorities')
  roles[k['role']]=k;keyset.add(k['public_key']);domainset.add(k['domain']);identities.add(k['id'])
 p=envelope['payload'];exact(p,'format profile family architecture generation not_before expires source_set contract_profile profile_sha256 repositories packages input_files obligations')
 if type(p['format']) is not int or p['format']!=1 or (p['profile'],p['family'],p['architecture'])!=(prof['id'],prof['family'],prof['architecture']):raise Invalid('cross-profile inputs')
 if integer(p['generation'],1)<integer(minimum_generation,1) or not integer(p['not_before'])<=now<integer(p['expires']):raise Invalid('stale release')
 if p['expires']-p['not_before']>7*86400:raise Invalid('unbounded release acceptance')
 for n in ('source_set','contract_profile','profile_sha256'):digest(p[n])
 if p['source_set']!=digest(expected_source) or p['contract_profile']!=digest(expected_contract):raise Invalid('source/contract differs from independent build plan')
 if p['profile_sha256']!=hashlib.sha256(canonical(prof)).hexdigest():raise Invalid('profile drift')
 if not isinstance(envelope['signatures'],list) or len(envelope['signatures'])!=2:raise Invalid('two signatures required')
 seen=set();msg=DOMAIN+canonical(p)
 for s in envelope['signatures']:
  exact(s,'role key_id signature');r=s['role']
  if r not in roles or r in seen or s['key_id']!=roles[r]['id']:raise Invalid('signature role')
  if not isinstance(s['signature'],str) or not re.fullmatch('[0-9a-f]{128}',s['signature']):raise Invalid('signature encoding')
  try:Ed25519PublicKey.from_public_bytes(bytes.fromhex(roles[r]['public_key'])).verify(bytes.fromhex(s['signature']),r.encode()+b'\0'+msg)
  except (InvalidSignature,ValueError) as e:raise Invalid('invalid acceptance signature') from e
  seen.add(r)
 if not isinstance(p['repositories'],list) or not 1<=len(p['repositories'])<=16:raise Invalid('repo count')
 repos={};snapshots=set();urls=set();catalogs={}
 for r in p['repositories']:
  exact(r,'id family release upstream_url snapshot_path repomd_sha256 key_path key_sha256')
  if not NAME.fullmatch(r['id']) or r['id'] in repos or r['family']!=prof['family'] or r['release']!='16.0':raise Invalid('mixed/duplicate repository')
  https(r['upstream_url']);relative(r['snapshot_path']);relative(r['key_path'])
  if urlsplit(r['upstream_url']).hostname not in ('download.opensuse.org','downloadcontent.opensuse.org'):raise Invalid('not an admitted public openSUSE source')
  if r['snapshot_path'] in snapshots or r['upstream_url'] in urls:raise Invalid('duplicate snapshot/source')
  snapshots.add(r['snapshot_path']);urls.add(r['upstream_url'])
  digest(r['repomd_sha256']);digest(r['key_sha256'])
  if file_hash(cache,r['snapshot_path']+'/repodata/repomd.xml',MAX_JSON)!=r['repomd_sha256'] or file_hash(cache,r['key_path'],1024*1024)!=r['key_sha256']:raise Invalid('repository/key drift')
  catalogs[r['id']]=verify_repository(r,cache)
  repos[r['id']]=r
 if not isinstance(p['packages'],list) or not 1<=len(p['packages'])<=10000:raise Invalid('package count')
 pkgs=set();package_paths=set()
 for v in p['packages']:
  exact(v,'name epoch version release arch repo path sha256 stage')
  if not NAME.fullmatch(v['name']) or (v['name'],v['arch']) in pkgs or v['repo'] not in repos:raise Invalid('package identity')
  if v['arch'] not in ('x86_64','noarch') or v['stage'] not in ('bootstrap','image'):raise Invalid('package stage/arch')
  integer(v['epoch'])
  for k in ('version','release'):
   if not isinstance(v[k],str) or not re.fullmatch(r'[A-Za-z0-9_.+~^]{1,128}',v[k]):raise Invalid('invalid NEVRA')
  digest(v['sha256']);relative(v['path'])
  if v['path'] in package_paths:raise Invalid('one RPM assigned to multiple package identities')
  package_paths.add(v['path'])
  if not v['path'].startswith(repos[v['repo']]['snapshot_path']+'/') or not v['path'].endswith('.rpm'):raise Invalid('package outside snapshot')
  if file_hash(cache,v['path'])!=v['sha256']:raise Invalid('RPM bytes changed')
  catalog=catalogs[v['repo']].get(v['path'])
  if not catalog or catalog!={k:(str(v[k]) if k=='epoch' else v[k]) for k in ('name','arch','epoch','version','release','sha256')}:raise Invalid('RPM-MD disagrees with accepted NEVRA/hash')
  pkgs.add((v['name'],v['arch']))
 if not any(v['stage']=='bootstrap' for v in p['packages']):raise Invalid('bootstrap empty')
 if not isinstance(p['input_files'],list) or not 1<=len(p['input_files'])<=50000:raise Invalid('input manifest')
 known={}
 for f in p['input_files']:
  exact(f,'path sha256');relative(f['path']);digest(f['sha256'])
  if f['path'] in known or file_hash(cache,f['path'])!=f['sha256']:raise Invalid('duplicate/changed input')
  known[f['path']]=f['sha256']
 # Bound every byte present, not just the expected package names. Reject symlinks
 # and FIFOs before opening them, including unlisted extras.
 actual=set()
 for root,dirs,files in os.walk(cache,followlinks=False):
  for n in dirs:
   if not stat.S_ISDIR(os.lstat(Path(root)/n).st_mode):raise Invalid('linked/special input directory')
  for n in files:
   path=Path(root)/n
   if not stat.S_ISREG(path.lstat().st_mode):raise Invalid('linked/special input')
   actual.add(path.relative_to(cache).as_posix())
 if actual!=set(known):raise Invalid('unlisted or missing cache files')
 for v in p['packages']:
  if known.get(v['path'])!=v['sha256']:raise Invalid('package not in complete cache manifest')
 if not isinstance(p['obligations'],dict) or not p['obligations']:raise Invalid('obligations required')
 if any(v not in ('not-run','pass','fail','not-applicable-reviewed') for v in p['obligations'].values()):raise Invalid('invalid obligation state')
 # These strings alone are not evidence; independently signed report review is
 # still required. This function never returns production_qualified=True.
 return {'result':'verified-inputs','profile':p['profile'],'generation':p['generation'],
         'package_count':len(pkgs),'input_sha256':hashlib.sha256(msg).hexdigest(),
         'production_qualified':False,'upstream_rpm_signatures_verified_by_this_tool':False,
         'unresolved':[k for k,v in p['obligations'].items() if v!='pass']}

def render(payload,cache):
 """KIWI XML for a frozen local repository. Not a native dependency resolver.
 Package versions are fixed by the complete snapshot, not an invented XML
 version attribute. After build compare the full installed NEVRA closure.
 """
 image=ET.Element('image',{'schemaversion':'8.5','name':'mission-core-'+payload['profile']})
 desc=ET.SubElement(image,'description',{'type':'system'})
 ET.SubElement(desc,'author').text='Mission Core project'
 ET.SubElement(desc,'contact').text='site-maintainer-required'
 ET.SubElement(desc,'specification').text='Unqualified locked SUSE assembly; see release gates.'
 pref=ET.SubElement(image,'preferences');ET.SubElement(pref,'version').text='0.1.0'
 ET.SubElement(pref,'packagemanager').text='zypper';ET.SubElement(pref,'rpm-check-signatures').text='true'
 typ=ET.SubElement(pref,'type',{'image':'oem','filesystem':'btrfs','firmware':'uefi','eficsm':'false','format':'qcow2'})
 ET.SubElement(typ,'bootloader',{'name':'grub2','bls':'false'})
 for r in payload['repositories']:
  repo=ET.SubElement(image,'repository',{'type':'rpm-md','alias':r['id'],'repository_gpgcheck':'true','package_gpgcheck':'true'})
  src=ET.SubElement(repo,'source',{'path':(Path(cache)/r['snapshot_path']).absolute().as_uri()})
  ET.SubElement(src,'signing',{'key':(Path(cache)/r['key_path']).absolute().as_uri()})
 for stage in ('bootstrap','image'):
  group=ET.SubElement(image,'packages',{'type':stage})
  for v in sorted(payload['packages'],key=lambda x:(x['name'],x['arch'])):
   if v['stage']==stage:ET.SubElement(group,'package',{'name':v['name'],'arch':v['arch']})
 ET.indent(image);return ET.tostring(image,encoding='utf-8',xml_declaration=True)+b'\n'
def write_new(path,data):
 # Build artifacts only. O_EXCL and no symlink target; never overwrite an image.
 f=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
 with os.fdopen(f,'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['profiles','verify-inputs','render-kiwi'])
 ap.add_argument('--profile',choices=['leap-16.0','sles-16.0']);ap.add_argument('--lock',type=Path);ap.add_argument('--trust',type=Path)
 ap.add_argument('--expected-source-set');ap.add_argument('--expected-contract-profile')
 ap.add_argument('--cache',type=Path);ap.add_argument('--output',type=Path);ap.add_argument('--minimum-generation',type=int,default=1)
 args=ap.parse_args();root=Path(__file__).resolve().parents[1]
 try:
  if args.command=='profiles':
   print(json.dumps([profile(root,n) for n in ('leap-16.0','sles-16.0')],ensure_ascii=False,indent=2));return 0
  if not all([args.profile,args.lock,args.trust,args.cache,args.expected_source_set,args.expected_contract_profile]):ap.error('profile, lock, trust, cache and independently approved source/contract digests required')
  p=profile(root,args.profile);e=read_json(args.lock);t=read_json(args.trust)
  report=verify(e,t,p,args.cache,int(time.time()),args.minimum_generation,expected_source=args.expected_source_set,expected_contract=args.expected_contract_profile)
  if args.command=='render-kiwi':
   if not args.output:ap.error('output required')
   write_new(args.output,render(e['payload'],args.cache))
   report['descriptor']=str(args.output);report['kiwi_schema_validated']=False;report['boot_image_built']=False
  print(json.dumps(report,indent=2));return 0
 except (OSError,ValueError,KeyError,TypeError) as e:
  print('distroctl refused: '+str(e),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Nia OS build-room inspection; never installs, executes hooks, or changes disks."""
import argparse,json,sys,os,resource
from pathlib import Path
from nia_common import Invalid,read_file,parse_json,canonical,write_new
from nia_policy import check_profile,readiness
from nia_catalog import candidate
from nia_layout import check_layout
from nia_xfs import check_policy as check_xfs_policy, assess as assess_xfs, inspect_local
from deb_archive import inspect_file
from debian_archive_auth import verify_snapshot,verify_source
from reproducibility import check_buildinfo,check_receipts

def load(p):return parse_json(read_file(p))
def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('profile');p.add_argument('profile')
    p=sub.add_parser('layout');p.add_argument('layout')
    p=sub.add_parser('storage-policy');p.add_argument('policy')
    p=sub.add_parser('storage-assess');p.add_argument('policy');p.add_argument('observation');p.add_argument('expected');p.add_argument('now_ms',type=int)
    p=sub.add_parser('storage-inspect');p.add_argument('mountpoint')
    p=sub.add_parser('inspect-deb');p.add_argument('deb')
    p=sub.add_parser('verify-deb');p.add_argument('snapshot');p.add_argument('keyring');p.add_argument('trust');p.add_argument('index');p.add_argument('deb')
    p=sub.add_parser('verify-source');p.add_argument('snapshot');p.add_argument('keyring');p.add_argument('trust');p.add_argument('index');p.add_argument('deb');p.add_argument('sources')
    p=sub.add_parser('compose');p.add_argument('snapshot');p.add_argument('keyring');p.add_argument('trust');p.add_argument('request')
    p=sub.add_parser('reproduction');p.add_argument('request')
    p=sub.add_parser('buildinfo');p.add_argument('subject');p.add_argument('buildinfo')
    p=sub.add_parser('readiness');p.add_argument('product_digest');p.add_argument('evidence')
    parser.add_argument('--output',help='new file only; no replacement')
    args=parser.parse_args(argv)
    try:
        if args.cmd in ('inspect-deb','verify-deb','verify-source','compose','reproduction','buildinfo'):
            if os.geteuid()==0:raise Invalid('unprivileged intake process required')
            resource.setrlimit(resource.RLIMIT_CORE,(0,0))
            resource.setrlimit(resource.RLIMIT_CPU,(120,120))
            resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
        if args.cmd=='profile':result=check_profile(load(args.profile))
        elif args.cmd=='layout':result=check_layout(load(args.layout))
        elif args.cmd=='storage-policy':result=check_xfs_policy(load(args.policy))
        elif args.cmd=='storage-assess':result=assess_xfs(load(args.policy),load(args.observation),load(args.expected),args.now_ms)
        elif args.cmd=='storage-inspect':result=inspect_local(args.mountpoint)
        elif args.cmd=='inspect-deb':result=inspect_file(args.deb)
        elif args.cmd=='verify-deb':result=verify_snapshot(Path(args.snapshot),read_file(args.keyring),load(args.trust),args.index,args.deb)
        elif args.cmd=='verify-source':result=verify_source(Path(args.snapshot),read_file(args.keyring),load(args.trust),args.index,args.deb,args.sources)
        elif args.cmd=='compose':
            from nia_common import fields,digest,sha
            r=load(args.request);fields(r,{'profile_sha256','inrelease_sha256','required_packages','inputs'},'composition request')
            digest(r['inrelease_sha256']);digest(r['profile_sha256'])
            product_raw=read_file(Path(__file__).resolve().parents[1]/'profiles/nia-os.json')
            check_profile(parse_json(product_raw))
            if r['profile_sha256']!=sha(product_raw):raise Invalid('composition product profile mismatch')
            if not isinstance(r['inputs'],list) or not 1<=len(r['inputs'])<=4096:raise Invalid('composition input count')
            observations=[];keyring=read_file(args.keyring);trust=load(args.trust)
            for item in r['inputs']:
                fields(item,{'index','deb'},'composition input')
                verified=verify_snapshot(Path(args.snapshot),keyring,trust,item['index'],item['deb'])
                if verified['inrelease_sha256']!=r['inrelease_sha256']:raise Invalid('mixed/unpinned snapshot')
                if verified['component']!='main':raise Invalid('non-main artifact requires separately reviewed product exception')
                observations.append(verified['observation'])
            result=candidate(observations,r['required_packages'],r['profile_sha256'])
        elif args.cmd=='reproduction':
            r=load(args.request);result=check_receipts(r['receipts'],r['subject'],r['registry'],r['now'],r['release_sha256'],r['policy_sha256'],r.get('threshold',2))
        elif args.cmd=='buildinfo':result=check_buildinfo(read_file(args.buildinfo),load(args.subject))
        else:result=readiness(args.product_digest,load(args.evidence))
        output=canonical(result)+b'\n'
        if args.output:write_new(args.output,output)
        else:sys.stdout.buffer.write(output)
        return 0
    except (Invalid,OSError,KeyError,TypeError,ValueError) as exc:
        print(json.dumps({'accepted':False,'execution_permit':False,'error':str(exc)},ensure_ascii=True),file=sys.stderr)
        return 2
if __name__=='__main__':raise SystemExit(main())

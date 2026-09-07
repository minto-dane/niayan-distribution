# SPDX-License-Identifier: MIT
"""Build a content-bound CANDIDATE catalog, never a running host's package DB.

The CLI supplies freshly re-inspected, archive-authenticated observations. This
module does not trust a serialized 'archive_authenticated=true' as evidence and
its output is explicitly not an execution grant. Native phase, effects, source
retention, input closure and installation need separate qualified checkers.
"""
from __future__ import annotations
from nia_common import Invalid,digest,sha,canonical
from debian_semantics import check_final,relations

def candidate(observations:list[dict],required_packages:list[str],profile_sha256:str)->dict:
    digest(profile_sha256)
    if not 1<=len(observations)<=4096:raise Invalid('catalog artifact count')
    packages=[];objects={};files={};conffiles={};unhandled=[]
    for observed in observations:
        if observed.get('schema')!='org.niaos.deb-observation/v1':raise Invalid('unknown observation schema')
        identity=observed['identity'];meta=observed['fields'];artifact=observed['artifact_sha256'];digest(artifact)
        if artifact in objects:raise Invalid('duplicate input artifact')
        objects[artifact]={'identity':identity,'raw_control_sha256':observed['raw_control_sha256'],
            'effects':observed['effect_members'],'unmodeled_fields':observed['unmodeled_fields'],
            'control_inventory':observed['control_inventory'],'unknown_control_members':observed['unknown_control_members']}
        provides=[(a.name,a.version or None) for g in relations(meta.get('provides',''),provides=True) for a in g]
        p={'id':artifact,'name':identity['package'],'version':identity['version'],'architecture':identity['architecture'],
            'multi_arch':meta.get('multi-arch','no'),'provides':provides}
        for k in ('depends','pre-depends','conflicts','breaks','replaces'):p[k.replace('-','_')]=' '.join(meta.get(k,'').splitlines())
        packages.append(p)
        for row in observed['file_inventory']:
            path=row['path']
            if path in files:
                old=files[path]
                keys=('kind','mode','uid','gid','xattrs')
                if row['kind']!='directory' or any(row[k]!=old[k] for k in keys):raise Invalid('ambiguous path ownership: '+path)
                old['owners'].append(artifact)
            else:files[path]=dict(row)|{'owners':[artifact]}
        for c in observed['conffiles']:
            if c['path'] in conffiles:raise Invalid('multiple configuration owners')
            conffiles[c['path']]=dict(c)|{'owner':artifact,'administrator_intent':'unknown','migration_authorized':False}
        if observed['unmodeled_fields'] or observed['unknown_control_members']:unhandled.append(artifact)
    names=[x['name'] for x in packages]
    if len(set(required_packages))!=len(required_packages) or not required_packages:raise Invalid('explicit root requirements missing/duplicated')
    for r in required_packages:
        if r not in names:raise Invalid('missing explicit root requirement: '+r)
    native=check_final(packages,{p['id'] for p in packages})
    body={'schema':'org.niaos.candidate-catalog/v1','profile_sha256':profile_sha256,
        'artifacts':objects,'files':dict(sorted(files.items())),'configuration':dict(sorted(conffiles.items())),
        'required_packages':sorted(required_packages),'native_final_set':native,
        'unhandled_metadata':unhandled,'source_retention_complete':False,'effects_closed':False,
        'phase_schedule_checked':False,'reproduction_checked':False,'trust_approved':False,
        'execution_permit':False,'native_database':'nia-catalog-v1','root_write_performed':False}
    return {'catalog_sha256':sha(canonical(body)),'catalog':body,'execution_permit':False}

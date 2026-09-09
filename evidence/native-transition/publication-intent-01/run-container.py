import os, subprocess, sys
base='/home/nia/devbox/niaos/.work'
repo='/home/nia/devbox/niaos/nia-os-consent'
work=base+'/native-publication-intent-01'
args=['sh',repo+'/dev/run-limited.sh','sudo','-n','podman','--cgroup-manager=cgroupfs','--events-backend=file','--storage-driver=vfs','--root',base+'/podman-root','--runroot',work+'/podman-run','--tmpdir',work+'/podman-tmp','--transient-store','run','--rm','--cgroups=disabled','--network=none','--user',os.environ.get('PROBE_UID','1000:1000'),'-e','HOME=/tmp','-e','TZ='+os.environ.get('PROBE_TZ','UTC'),'-e','SOURCE_DATE_EPOCH=1788739200','-e','LC_ALL=C.UTF-8','-v',work+'/'+os.environ.get('PROBE_COPY','debug')+':'+os.environ.get('PROBE_MOUNT','/workspace'),'-v',work+':/evidence','-v',base+'/native-data-stream-01/original-media:/originals:ro','-w',os.environ.get('PROBE_MOUNT','/workspace'),'0c04329a1343a0f1ae82ab931ffc7a7e5cbfdccbf18948e0576366fbf5bb249a']
raise SystemExit(subprocess.call(args+sys.argv[1:]))

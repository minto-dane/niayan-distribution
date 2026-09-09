import os,subprocess,sys
from pathlib import Path
root='/home/nia/devbox/niaos/nia-os-consent';base='/home/nia/devbox/niaos/.work';work=base+'/native-generation-image-01';image=Path(work+'/image-id').read_text().strip()
args=['sh',root+'/dev/run-limited.sh','sudo','-n','podman','--cgroup-manager=cgroupfs','--events-backend=file','--storage-driver=vfs','--root',base+'/podman-root','--runroot',base+'/podman-generation-reboot-run','--tmpdir',base+'/podman-generation-reboot-tmp','--transient-store','run','--rm','--cgroups=disabled','--network=none','--user','1000:1000','-e','HOME=/tmp','-e','LC_ALL=C.UTF-8','-e','TZ=UTC','-v',work+':/work','-v',root+'/pkgcore/tests/fixtures/deb-payload:/fixtures:ro','-v',base+'/native-data-stream-01/original-media:/originals:ro','-w','/work',image]
raise SystemExit(subprocess.call(args+sys.argv[1:]))

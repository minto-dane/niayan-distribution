# SPDX-License-Identifier: MIT
# Exactly one native child in this fresh process; Linux ru_maxrss is KiB.
import json,resource,subprocess,sys,time
started=time.monotonic()
with open(sys.argv[1],'w') as output:
 run=subprocess.run(sys.argv[2:],stdout=output,stderr=subprocess.STDOUT,timeout=600)
print(json.dumps(dict(returncode=run.returncode,seconds=time.monotonic()-started,peak_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)))
raise SystemExit(run.returncode)

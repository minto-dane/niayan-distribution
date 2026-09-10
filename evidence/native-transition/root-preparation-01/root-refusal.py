from pathlib import Path
import subprocess
base=Path('/evidence/root-refusal');base.mkdir()
for name in ['root','state','store']:(base/name).mkdir(mode=0o700)
subprocess.run(['/workspace/pkgcore/build/test-bin/run_root_archive_tests'],check=True)
subprocess.run(['/workspace/pkgcore/build/test-bin/run_generation_stage_tests',*[str(base/n) for n in ['root','state','store']]],check=True)

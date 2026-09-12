from pathlib import Path
import subprocess
p=Path('/evidence');r=Path('/workspace/pkgcore')
subprocess.run(['python3',str(p/'check-root.py')],check=True,timeout=60)
subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-O2','-D_FORTIFY_SOURCE=3','-fstack-protector-strong','-fPIC','-shared','-Wl,-z,relro,-z,now,-z,noexecstack',str(r/'runtime/root_session.c'),'-o',str(p/'root-session.so')],check=True,timeout=60)
subprocess.run(['python3',str(r/'tests/check_root_session_transport.py'),'--library',str(p/'root-session.so'),'--ada',str(r/'build/test-bin/run_root_session_tests'),'--report',str(p/'root-session-transport.json')],check=True,timeout=60)

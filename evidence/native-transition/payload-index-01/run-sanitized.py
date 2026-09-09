import os,pathlib,subprocess
subprocess.run(['gprbuild','-s','-j1','-p','-P','tests.gpr','run_payload_index_tests.adb','-cargs:C','-fsanitize=address,undefined','-fno-omit-frame-pointer','-largs','-fsanitize=address,undefined'],check=True)
p=pathlib.Path('/evidence/sanitized-cas');p.mkdir(mode=0o700)
subprocess.run(['/workspace/build/test-bin/run_payload_index_tests',str(p),'/workspace/tests/fixtures/deb-payload','/workspace/tests/fixtures/payload-index'],env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'},check=True)

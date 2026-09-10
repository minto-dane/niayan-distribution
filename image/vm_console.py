# SPDX-License-Identifier: BSD-3-Clause
"""Bounded QEMU serial/QMP driver for the image acceptance tests."""
import json
import base64
import hashlib
from pathlib import Path
import socket
import signal
import shutil
import subprocess
import tempfile
import time


def install_interrupt_handler():
    # Python is PID 1 in the test container; explicitly handle its stop signal
    # so the context manager can close QEMU and preserve the incomplete report.
    def interrupted(_signum, _frame):
        raise InterruptedError('VM acceptance interrupted')
    signal.signal(signal.SIGTERM, interrupted)


def tool_hashes():
    root = Path(__file__).resolve().parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ('vm_console.py', 'test-live.py', 'test-install.py', 'test-suite.py',
                         'fixtures/install-vm.cfg', 'fixtures/install-network.cfg')}


def firmware_args(mode, output):
    if mode == 'bios':
        return []
    secure = mode == 'secure-boot'
    suffix = '.ms' if secure else ''
    firmware = Path('/usr/share/OVMF')
    code = firmware / ('OVMF_CODE_4M' + suffix + '.fd')
    variables = Path(output) / 'OVMF_VARS.fd'
    shutil.copy2(firmware / ('OVMF_VARS_4M' + suffix + '.fd'), variables)
    record = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in (code, variables)}
    (Path(output) / 'firmware-inputs.json').write_text(json.dumps(record, indent=2) + '\n')
    args = ['-global', 'driver=cfi.pflash01,property=secure,value=on'] if secure else []
    return args + ['-drive', f'if=pflash,format=raw,unit=0,readonly=on,file={code}',
                   '-drive', f'if=pflash,format=raw,unit=1,file={variables}']


class Guest:
    def __init__(self, command, output, timeout=600):
        self.output = Path(output)
        self.temporary = tempfile.TemporaryDirectory(prefix='nia-qemu-')
        self.serial_path = Path(self.temporary.name) / 'serial'
        self.qmp_path = Path(self.temporary.name) / 'qmp'
        self.command = [*command, '-serial', f'unix:{self.serial_path},server=on,wait=on',
                        '-qmp', f'unix:{self.qmp_path},server=on,wait=off']
        self.timeout = timeout
        self.channel = None
        self.process = None
        self.log = None
        self.error = None
        self.received = bytearray()

    def __enter__(self):
        self.start = time.monotonic()
        self.log = (self.output / 'serial.log').open('wb')
        self.error = (self.output / 'qemu.log').open('wb')
        try:
            self.process = subprocess.Popen(self.command, stdin=subprocess.DEVNULL,
                                            stdout=self.error, stderr=self.error)
            while not self.serial_path.exists():
                if self.process.poll() is not None or time.monotonic() - self.start > 30:
                    raise RuntimeError('QEMU failed before serial startup')
                time.sleep(0.1)
            self.channel = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.channel.connect(str(self.serial_path))
            self.channel.settimeout(1)
            return self
        except BaseException:
            self.close()
            raise

    def send(self, value):
        self.channel.sendall(value.encode() if isinstance(value, str) else value)

    def script(self, source, root=False):
        # Keep every terminal input line below the canonical TTY limit and
        # prevent echoed source text from containing an acceptance marker.
        encoded = base64.b64encode(source.encode())
        body = b'\n'.join(encoded[i:i + 76] for i in range(0, len(encoded), 76))
        shell = b'sudo -n sh' if root else b'sh'
        self.send(b"base64 -d <<'NIA_SCRIPT_END' | " + shell + b'\n'
                  + body + b'\nNIA_SCRIPT_END\n')

    def expect(self, marker, failure=None):
        while True:
            if failure is not None and failure in self.received:
                raise RuntimeError('guest acceptance failed; see serial.log')
            if marker in self.received:
                end = self.received.index(marker) + len(marker)
                del self.received[:end]
                return
            if time.monotonic() - self.start > self.timeout:
                raise TimeoutError('guest did not reach ' + repr(marker))
            try:
                data = self.channel.recv(65536)
            except socket.timeout:
                if self.process.poll() is not None:
                    raise RuntimeError('QEMU exited before guest acceptance completed')
                continue
            if not data:
                raise RuntimeError('serial channel closed')
            self.received.extend(data)
            self.log.write(data)
            self.log.flush()
            if len(self.received) > 4 * 1024**2:
                raise RuntimeError('serial output exceeded expected probe budget')

    def qmp(self, request):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as monitor:
            monitor.connect(str(self.qmp_path))
            monitor.settimeout(10)
            with monitor.makefile('rwb') as protocol:
                json.loads(protocol.readline())
                for command in ({'execute': 'qmp_capabilities'}, request):
                    protocol.write(json.dumps(command).encode() + b'\n')
                    protocol.flush()
                    while True:
                        response = json.loads(protocol.readline())
                        if 'error' in response:
                            raise RuntimeError('QMP command failed: ' + str(response))
                        if 'return' in response:
                            break

    def screenshot(self, name='desktop.png'):
        self.qmp({'execute': 'screendump', 'arguments': {
                  'filename': str((self.output / name).resolve()), 'format': 'png'}})

    def boot_default_entry(self):
        # The standard ISO menu waits for the user's selection. Exercise that
        # menu with a keyboard event, without changing the boot configuration.
        time.sleep(5)
        self.screenshot('boot-menu.png')
        self.key('ret')

    def key(self, *codes):
        self.qmp({'execute': 'send-key', 'arguments': {
                  'keys': [{'type': 'qcode', 'data': code} for code in codes],
                  'hold-time': 60}})
        time.sleep(0.15)

    def wait_shutdown(self, timeout=60):
        deadline = time.monotonic() + timeout
        tail = bytearray()
        while self.process.poll() is None:
            if time.monotonic() >= deadline:
                raise TimeoutError('guest did not power off; see serial.log')
            try:
                data = self.channel.recv(65536)
            except socket.timeout:
                continue
            if not data:
                self.process.wait(timeout=max(0.1, deadline - time.monotonic()))
                break
            self.log.write(data)
            self.log.flush()
            tail.extend(data)
            if b'Please remove' in tail and b'ENTER' in tail:
                # Standard Debian Live media-removal confirmation. Handle the
                # actual prompt; never force a successful QEMU exit.
                # The shutdown script sets terminal attributes after printing
                # the prompt; allow that input flush to complete first.
                time.sleep(1)
                self.send(b'\n')
                self.key('ret')
                tail.clear()
            if len(tail) > 16384:
                del tail[:-8192]
        if self.process.returncode != 0:
            raise RuntimeError('QEMU shutdown failure')

    def close(self):
        if self.channel is not None:
            self.channel.close()
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        for stream in (self.log, self.error):
            if stream is not None:
                stream.close()
        self.temporary.cleanup()

    def __exit__(self, kind, value, traceback):
        if kind is not None and self.process is not None and self.process.poll() is None:
            try:
                self.screenshot('failure.png')
            except (OSError, ValueError, RuntimeError):
                pass
        self.close()

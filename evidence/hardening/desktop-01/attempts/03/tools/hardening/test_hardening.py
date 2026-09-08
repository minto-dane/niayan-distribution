# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import struct
import tempfile
import unittest

from audit import elf_properties, load_policy, render, runtime, HERE


def elf(*, executable_stack=False, now=True, relro=True):
    header = bytearray(64)
    header[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HHIQQQIHHHHHH', header, 16, 3, 62, 1, 0, 64, 0, 0, 64, 56, 5, 0, 0, 0)
    ph = [
        (1, 5, 0, 0, 0, 376, 376, 4096),
        (3, 4, 344, 0, 0, 0, 0, 1),
        (2, 6, 344, 0, 0, 32, 32, 8),
        (0x6474E551, 7 if executable_stack else 6, 0, 0, 0, 0, 0, 16),
        (0x6474E552 if relro else 4, 4, 344, 0, 0, 32, 32, 1),
    ]
    return bytes(header) + b''.join(struct.pack('<IIQQQQQQ', *p) for p in ph) + struct.pack('<qQqQ', 30, 8 if now else 0, 0, 0)


class HardeningTests(unittest.TestCase):
    def test_elf_negative_properties_are_not_pass(self):
        self.assertTrue(all(elf_properties(elf()).values()))
        self.assertFalse(elf_properties(elf(executable_stack=True))['non_executable_stack'])
        self.assertFalse(elf_properties(elf(now=False))['bind_now'])
        self.assertFalse(elf_properties(elf(relro=False))['relro'])

    def test_truncated_program_table_or_dynamic_rejected(self):
        for data in (elf()[:100], elf()[:-1], b'not ELF'):
            with self.assertRaises(ValueError):
                elf_properties(data)

    def test_missing_runtime_evidence_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = runtime(load_policy(HERE / 'baseline.json'), root, root, root, 'test')
            self.assertEqual(report['result'], 'fail')
            self.assertTrue(any(r['result'] == 'unavailable' for r in report['checks']))

    def test_generated_policy_is_exact(self):
        policy = load_policy(HERE / 'baseline.json')
        conf = HERE / 'rootfs/usr/lib/sysctl.d/60-niaos-hardening.conf'
        self.assertEqual(conf.read_text(), render(policy))
        # User namespaces and emergency keys remain available; BPF restriction
        # uses the reversible value 2, not the irreversible boot-lifetime latch.
        self.assertNotIn('kernel.unprivileged_userns_clone', policy['sysctl'])
        self.assertNotIn('kernel.sysrq', policy['sysctl'])
        self.assertEqual(policy['sysctl']['kernel.unprivileged_bpf_disabled']['value'], 2)


if __name__ == '__main__':
    unittest.main()

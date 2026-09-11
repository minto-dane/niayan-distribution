#!/usr/bin/python3 -I
# SPDX-License-Identifier: BSD-3-Clause
"""Private reduced-capability child of the root-session controller."""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from root_bank import Bank, canonical, decode, read_policy, validate_request
from storage_bootstrap import POLICY


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation', choices=('prepare','verify'), required=True)
    parser.add_argument('--archive-fd', type=int, required=True)
    parser.add_argument('--lease-fd', type=int, required=True)
    parser.add_argument('--bank-lock-fd', type=int, required=True)
    parser.add_argument('--worker-sha256', required=True)
    parser.add_argument('--parent', type=int, required=True)
    args = parser.parse_args()
    if os.getuid() or os.geteuid() or os.getppid() != args.parent:
        raise ValueError('private-worker-parent')
    status = dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines())
    mask = sum(1 << n for n in (0,1,3,4,18,27,31))
    if (int(status['CapBnd'],16) != mask or int(status['CapEff'],16) != mask
            or int(status['CapInh'],16) or int(status['CapAmb'],16) or int(status['NoNewPrivs']) != 1):
        raise ValueError('private-worker-capabilities')
    if min(args.archive_fd,args.lease_fd,args.bank_lock_fd) < 3 or len({args.archive_fd,args.lease_fd,args.bank_lock_fd}) != 3:
        raise ValueError('private-worker-descriptors')
    request = decode(sys.stdin.buffer.read(4097)); validate_request(request)
    policy = read_policy(Path(POLICY))
    bank = Bank(policy['bank'], policy['reservation'], policy['worker'], policy['client_uid'], inherited_lock=args.bank_lock_fd)
    try:
        if bank.worker_hash != args.worker_sha256: raise ValueError('private-worker-pin')
        result = getattr(bank,args.operation)(request,args.archive_fd,args.lease_fd)
        result['child_capability_mask'] = mask
        sys.stdout.buffer.write(canonical(result));sys.stdout.buffer.flush()
    finally:
        bank.close()


if __name__ == '__main__':main()

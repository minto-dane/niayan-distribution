#!/bin/sh
# SPDX-License-Identifier: BSD-3-Clause
# Run inside the bounded tool container; SSH listens on host loopback only.
set -eu
cd /vm
test -f base-verification.json
test -f builder.qcow2
exec qemu-system-x86_64 -machine q35 -accel kvm -cpu host -m 2048 -smp 1 \
    -drive file=builder.qcow2,if=virtio,format=qcow2,discard=unmap \
    -drive file=seed.iso,media=cdrom,readonly=on,format=raw \
    -netdev user,id=net0,hostfwd=tcp:127.0.0.1:22222-:22 \
    -device virtio-net-pci,netdev=net0 \
    -display none -serial file:serial.log \
    -monitor unix:monitor.sock,server=on,wait=off

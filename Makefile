# SPDX-License-Identifier: MIT
SHELL := /bin/sh
.PHONY: image-check native-check hardening-check
image-check: native-check hardening-check
	python3 -B -m unittest discover -s image -p test_image_tools.py -v
	python3 -m compileall -q image release
	@set -eu; for script in image/*.sh image/auto/config image/hooks/*.hook.chroot; do sh -n "$$script"; done

native-check:
	python3 -B -m unittest discover -s native -p test_transition.py -v
	python3 -m compileall -q native

hardening-check:
	python3 -B -m unittest discover -s hardening -p test_hardening.py -v
	python3 -m compileall -q hardening

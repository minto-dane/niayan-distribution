# SPDX-License-Identifier: MIT
SHELL := /bin/sh
.PHONY: image-check
image-check:
	python3 -B -m unittest discover -s image -p test_image_tools.py -v
	python3 -m compileall -q image release
	@set -eu; for script in image/*.sh image/auto/config image/hooks/*.hook.chroot; do sh -n "$$script"; done

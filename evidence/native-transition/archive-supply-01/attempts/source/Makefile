# SPDX-License-Identifier: MIT
SHELL := /bin/sh
.PHONY: image-check native-check hardening-check i18n-check i18n-release-check
image-check: native-check hardening-check
	python3 -B -m unittest discover -s image -p test_image_tools.py -v
	python3 -m compileall -q image release
	@set -eu; for script in image/*.sh image/auto/config image/hooks/*.hook.chroot; do sh -n "$$script"; done

native-check: i18n-check
	python3 -B -m unittest discover -s native -p 'test_*.py' -v
	python3 -m compileall -q native

i18n-check:
	python3 -B native/i18n_catalogs.py

i18n-release-check:
	python3 -B native/language_coverage.py --require-all

hardening-check:
	python3 -B -m unittest discover -s hardening -p test_hardening.py -v
	python3 -m compileall -q hardening

# SPDX-License-Identifier: MIT
SHELL := /bin/sh
.PHONY: image-check native-check tool-check hardening-check i18n-check i18n-release-check
image-check: native-check hardening-check
	python3 -B -m unittest discover -s image -p test_image_tools.py -v
	python3 -m compileall -q image release
	@set -eu; for script in image/*.sh image/auto/config image/hooks/*.hook.chroot; do sh -n "$$script"; done

native-check: i18n-check tool-check
	python3 -B -m unittest discover -s native -p 'test_*.py' -v
	python3 -m compileall -q native

tool-check:
	python3 -B -m unittest discover -s tests -p 'test_*.py' -v

i18n-check:
	python3 -B native/i18n_catalogs.py

i18n-release-check:
	python3 -B native/language_coverage.py --require-all

hardening-check:
	python3 -B -m unittest discover -s hardening -p test_hardening.py -v
	python3 -m compileall -q hardening

.PHONY: native-worker native-worker-check
native-worker:
	$(MAKE) -C native/worker

# Run in a disposable VM/container with an explicit nodev/nosuid/noexec mount.
native-worker-check: native-worker
	test -n "$(WORKER_TEST_BASE)"
	python3 -B native/worker/check_root_extract.py --worker "$(CURDIR)/build/native-worker/root-extract" --target-base "$(WORKER_TEST_BASE)" --report "$(CURDIR)/build/native-worker/check.json"

.PHONY: native-bank-check
native-bank-check: native-worker
	test -n "$(WORKER_TEST_BASE)"
	python3 -B native/worker/check_root_bank.py --worker "$(CURDIR)/build/native-worker/root-extract" --base "$(WORKER_TEST_BASE)" --report "$(CURDIR)/build/native-worker/bank-check.json"

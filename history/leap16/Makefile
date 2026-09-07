# SPDX-License-Identifier: MIT
.PHONY: test profiles
test:
	python3 -m unittest discover -s tests -p 'test_*.py' -v
profiles:
	python3 tools/distroctl.py profiles

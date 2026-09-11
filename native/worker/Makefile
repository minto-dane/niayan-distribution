# SPDX-License-Identifier: BSD-3-Clause
CC ?= cc
CPPFLAGS += -D_FORTIFY_SOURCE=3
CFLAGS ?= -O2 -g
CFLAGS += -std=c11 -Wall -Wextra -Werror -fstack-protector-strong -fPIE
LDFLAGS += -pie -Wl,-z,relro,-z,now,-z,noexecstack
LDLIBS += -larchive -lsodium
BUILD ?= ../../build/native-worker
.PHONY: all check clean
all: $(BUILD)/root-extract
$(BUILD)/root-extract: root_extract.c tar_clocks.c tar_clocks.h
	mkdir -p $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(LDFLAGS) root_extract.c tar_clocks.c $(LDLIBS) -o $@
$(BUILD)/check-tar-clocks: check_tar_clocks.c tar_clocks.c tar_clocks.h
	mkdir -p $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(LDFLAGS) check_tar_clocks.c tar_clocks.c -larchive -o $@
check: $(BUILD)/check-tar-clocks
	python3 -B check_tar_clocks.py --driver $(BUILD)/check-tar-clocks
clean:
	rm -f $(BUILD)/root-extract $(BUILD)/check-tar-clocks

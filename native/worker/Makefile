# SPDX-License-Identifier: MIT
CC ?= cc
CPPFLAGS += -D_FORTIFY_SOURCE=3
CFLAGS ?= -O2 -g
CFLAGS += -std=c11 -Wall -Wextra -Werror -fstack-protector-strong -fPIE
LDFLAGS += -pie -Wl,-z,relro,-z,now,-z,noexecstack
LDLIBS += -larchive -lsodium
BUILD ?= ../../build/native-worker
.PHONY: all clean
all: $(BUILD)/root-extract
$(BUILD)/root-extract: root_extract.c
	mkdir -p $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(LDFLAGS) $< $(LDLIBS) -o $@
clean:
	rm -f $(BUILD)/root-extract

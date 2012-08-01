#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Simple Makefile to create shell scripts wrappers for python scripts to
# automatically set PYTHONPATH without needing to install the roibot
# python support module for the touchbot
#
TARGET_FILES := $(patsubst %.py,%,$(wildcard *.py))
ACMESCRIPT=acmescript.sh


all: $(ACMESCRIPT) $(TARGET_FILES)

$(TARGET_FILES):
	@(for i in $(TARGET_FILES) ; do \
		echo "Creating $$i ..."; \
		ln -s $(ACMESCRIPT) $$i; \
	  done)
	  @echo "Done."

clean:
	@(for i in $(TARGET_FILES) ; do \
		echo "Cleaning wrapper script $$i ..."; \
		rm -f $$i; \
	  done)
	  @echo "Done."

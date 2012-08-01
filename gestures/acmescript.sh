#/bin/sh
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# acmescript.sh
#
# This is a script file to hack the PYTHONPATH variable to include the
# roibot module path.  It depends on the binary being executed out of
# the examples directory, but it does not depend on this specifically
# being an absolute or relative path.  It is also insensitive to the
# paths containing spaces, for you Mac users.
#
# This depends on your python being insensitive to trailing :'s in the
# PYTHONPATH, if it has not been previously set (this has been tested
# with all current versions of python in use in Chrome OS).
#
# The name is an omage to "ACME" in Looney Tunes cartoons, which stood
# for "[the] American Company [that] Makes Everthing", which is where
# Wile E. Coyote obtained his devices.
#
BASEDIR=`dirname $0`
BASENAME=`basename $0`
PYTHONNAME="${BASENAME}.py"
PYTHONPATH="${BASEDIR}/../roibot":"${PYTHONPATH}"

python "${PYTHONNAME}"

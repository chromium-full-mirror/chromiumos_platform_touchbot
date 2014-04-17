# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This simple script returns the dimensions of a precalibrated device spec
in millimeters.

Usage: python device_size.py lumpy.p
"""

import sys

from touchbotII import Device

if __name__ == '__main__':
    try:
        device = Device(sys.argv[1])
    except:
        print 'Usage: %s device.p' % __file__
        sys.exit(1)

    print device.DeviceHeight(), device.DeviceWidth()

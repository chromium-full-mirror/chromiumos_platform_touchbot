# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Butterfly

# Device orientation on robot sampling area
#         Y-------->
#     ,-----------------,
#     |     ,-----.     |
#  X  |     |     |     |
#  |  |     `-----'     |
#  |  |,-.-.-.-.-.-.-.-.|
#  |  |`-+-+-+-+-+-+-+-'|
# \|/ |`-+-+-+-+-+-+-+-'|
#     |`-+-+-+-+-+-+-+-'|
#     |`-`-`-`-`-`-`-`-'|
#     `-----------------'

# Place the stops at the following locations:
# 108, 201
# Unfortunately this model is too wide to use the stops on the sides, so
# these measurements were taken with it pressed against with the far right
# edge of the safety cage around the robot.

# Coordinates for touchpad area bounding box:
# Measured with gestures/point_picker.py
KEYPRESS_Z = 84.8
bounds = {
    'minX': 49.7,
    'maxX': 84.7,
    'minY': 154.1,
    'maxY': 235.3,
    'paperZ': 82.1,
    'tapZ': 84.0,
    'clickZ': 82.1,

    'keys': {
        'k': (156.6, 172.2, KEYPRESS_Z),
        'j': (156.6, 192.0, KEYPRESS_Z),
        'f': (156.6, 249.0, KEYPRESS_Z),
        'v': (135.6, 239.0, KEYPRESS_Z)
    }
}

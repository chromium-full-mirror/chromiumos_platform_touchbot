# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Link

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
# 108, 202, 311, 403

# Coordinates for touchpad area bounding box:
# Measured with gestures/point_picker.py
bounds = {
    'minX': 42.5,
    'maxX': 96.5,
    'minY': 117.5,
    'maxY': 207.5,
    'paperZ': 87.2,
    'tapZ': 88.5,
    'clickZ': 89.2
}

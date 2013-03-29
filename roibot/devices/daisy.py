# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Snow

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
# 108, 206, 311, 404

# Coordinates for touchpad area bounding box:
# Measured with gestures/point_picker.py
bounds = {
    'minX': 37.5,
    'maxX': 77.6,
    'minY': 116.3,
    'maxY': 201.3,
    'paperZ': 87.0,
    'tapZ': 88.4,
    'clickZ': 89.5
}

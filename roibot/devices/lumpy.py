# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Lumpy

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
# 108, 203, 311, 404

# Coordinates for touchpad area bounding box:
# Measured with gestures/point_picker.py
bounds = {
    'minX': 35.0,
    'maxX': 90.0,
    'minY': 115.0,
    'maxY': 208.0,
    'paperZ': 81.0,
    'tapZ': 82.4,
    'clickZ': 84.0
}

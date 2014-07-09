# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# MacBook Air 11"
# Apple model 4,1

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
# 108, 207, 311, 403

# Coordinates for touchpad area bounding box:
# Measured with gestures/point_picker.py
bounds = {
    'minX': 34.8,
    'maxX': 86.1,
    'minY': 115.3,
    'maxY': 209.5,
    'paperZ': 94.55,
    'tapZ': 94.55,
    'clickZ': 94.6
}

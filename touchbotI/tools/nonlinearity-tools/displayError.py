# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Generate a visual heatmap of the error for one pressure value

This script allows you to specify several pickled Stroke object and
builds a complete Filter out of them before sampling the X and Y error
and building a heatmap to visualize the error across the pad.

Since the error is measured at points in (x, y, p) space and computer
screens are only 2D it just samples one "slice" at a set value of p.
This is usually enough to get a feel for what the error looks like.

Usage:
    python parse.py my_data/activity_log*.txt
    python displayError.py stroke*.p
"""

import sys

import matplotlib.pyplot as plt
import numpy as np

from lib.progress import ProgressBar
from lib.stroke import Stroke
from lib.filter import Filter


HEATMAP_GRANULARITY = 10
HEATMAP_PRESSURE = 35

strokes = [Stroke.load_from_file(arg) for arg in sys.argv[1:]]
filt = Filter(strokes)

print "Building the heatmap..."
rangex = range(int(filt.min_x), int(filt.max_x), HEATMAP_GRANULARITY)
rangey = range(int(filt.min_y), int(filt.max_y), HEATMAP_GRANULARITY)
errorx = [[0.0] * len(rangex) for y in rangey]
errory = [[0.0] * len(rangex) for y in rangey]

bar = ProgressBar(len(rangex) * len(rangey))
for x in range(len(rangex)):
    for y in range(len(rangey)):
        errors = filt.getError((rangex[x], rangey[y], HEATMAP_PRESSURE))
        errorx[y][x], errory[y][x] =  errors
        bar.progress()

print "Done, displaying the heatmap now."
X, Y = np.meshgrid(rangex, rangey)
plt.subplot(211)
plt.pcolor(X, Y, errorx)
plt.subplot(212)
plt.pcolor(X, Y, errory)

plt.show()

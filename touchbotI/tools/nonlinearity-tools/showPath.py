# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

import matplotlib.pyplot as plt

from lib.progress import ProgressBar
from lib.stroke import Stroke


strokes = [Stroke.load_from_file(arg) for arg in sys.argv[1:]]

print "Adding %d strokes to figure..." % len(strokes)
bar = ProgressBar(len(strokes))

for stroke in strokes:
    s = [(t, x, y, p) for t, x, y, p in stroke]
    i = [(t, x, y, p) for t, x, y, p in stroke.find_ideal()]
    e = stroke.compute_error()

    plt.plot([x for t, x, y, p in stroke], [y for t, x, y, p in stroke])
    plt.plot([x for t, x, y, p in stroke.find_ideal()],
             [y for t, x, y, p in stroke.find_ideal()])

    plt.plot([x for t, x, y, p in s], [e[(x, y, p)][1] for t, x, y, p in s])
    plt.plot([e[(x, y, p)][0] for t, x, y, p in s], [y for t, x, y, p in s])
    bar.progress()

print "Done, displaying the plot now."
plt.show()

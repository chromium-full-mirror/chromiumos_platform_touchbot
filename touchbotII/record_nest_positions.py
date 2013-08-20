# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This script records the robot positions just over the nest

The operator runs the script and manually moves the robot over each
set of fingertips in the nest in turn, pressing 'enter' to record the
locations. These are automatically stored in the nest/ directory
where they are preloaded for future Touchbot objects
"""

import pickle
from touchbot import Touchbot


# Connect to the robot
bot = Touchbot()
bot.CloseNest()

for fingertip_size in range(len(Touchbot.ALL_FINGERS)):
    fingertip_was_calibrated = False

    while not fingertip_was_calibrated:
        print 'Position the fingers over the tips of size %d.' % fingertip_size
        pos = bot.CalibratePosition()

        fingertip_was_calibrated = bool(pos)
        if not fingertip_was_calibrated:
            print 'Error, please try again'

    try:
        with open('nest/size%d.p' % fingertip_size, 'wb') as fo:
            pickle.dump(pos, fo)
    except:
        print 'Error writing to disk for the %s finger' % finger

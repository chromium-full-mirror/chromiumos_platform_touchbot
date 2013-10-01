# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This script records the robot positions over the fingertip detector

The operator runs the script and manually moves the robot so each finger
within range of the fingertip detector, pressing 'enter' to record the
locations. These are automatically stored in the detector/ directory
where they are preloaded for future Touchbot objects
"""

import pickle
from touchbot import Touchbot


# Connect to the robot
bot = Touchbot()

for finger in ['fr', 'fl', 'bl', 'br']:
    fingertip_was_calibrated = False

    while not fingertip_was_calibrated:
        print 'Position the %s finger over the detector.' % finger
        pos = bot.CalibratePosition()
        detector_state = bot.GetGPIO(Touchbot.FINGERTIP_DETECT)

        fingertip_was_calibrated = bool(pos and detector_state)
        if not fingertip_was_calibrated:
            print 'Error, please try again'

    try:
        with open('detector/finger%s.p' % finger, 'wb') as fo:
            pickle.dump(pos, fo)
    except:
        print 'Error writing to disk for the %s finger' % finger

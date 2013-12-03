# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This is a tapping script for Touchbot II

When you run this script, the robot will perform a customizable tap action
on the touchpad.  This essentially consists of tapping repeatedly with a series
of fingers in a certain location on the pad.

The gesture takes in a position to move the hand to, a list of which fingers
to do the tap or drumroll with, and the number of taps to perform.
    x, y coordinates in the range from 0.0->1.0
    angle in degrees
    finger distance in mm that specifies how far apart the hand should open
Which fingers the robot should be used as a list of 4 booleans
    Top right, Top Left, Bottom Left, Bottom Right
    'tap' or 'drumroll'

The robot will move to that position, then tap the fingers as specified.  For
a drumroll it alternates tapping each one in turn, for a regular 'tap' all of
the fingers descend at once.

Example:
    To do a standard 2 finger drumroll in the center of the pad 20mm apart
    Python drumroll.py lumpy.p 0.5 0.5 45 20 0 1 0 1 50 drumroll

    To tap 3 fingers 20 times in the top left corner of the pad 30mm apart
    Python drumroll.py lumpy.p 0.1 0.3 0 30 0 1 1 1 20 tap
"""

import math
import sys
import time

from touchbotII import Touchbot, Device, PositionArg


try:
    # Parse the command line arguments
    device = Device(sys.argv[1])
    pos = PositionArg(*[float(v) for v in sys.argv[2:6]])
    fingers = [int(arg) for arg in sys.argv[6:10]]
    num_taps = int(sys.argv[10])
    is_drumroll = (sys.argv[11] == 'drumroll')
except:
    print ('Usage: python %s device.p position fingers num_taps [tap|drumroll]'
                                                                    % __file__)
    print '     * position is formatted as x y angle finger_distance'
    print '     * finger_states: a list of 4 values (1s and 0s)'
    print '     * the number of individual taps to make'
    print
    print 'For a standard 2 finger drumroll in the center you might do:'
    print 'python %s link.p 0.5 0.5 45 20 0 1 0 1 50 drumroll' % __file__
    sys.exit(1)

print 'Executing the tap gesture defined by:'
print '\tPosition:  %s' % str(pos)
print '\tFingers:   %s' % str(fingers)
print '\tNum taps:  %d' % num_taps
print '\tDrumroll?: %s' % str(is_drumroll)

num_fingers = sum(fingers)
if num_fingers < 1:
    print 'You must specify at least 1 finger to use'
    sys.exit(1)

# Connect to the robot and configure the profile to move slowly
bot = Touchbot()
bot.SetSpeed(Touchbot.SPEED_SLOW)

# Convert the point specifications into something the robot understands
abs_pos = device.RelativePosToAbsolutePos((pos.x, pos.y), angle=pos.angle)

# For one finger taps, compensate to center the finger
abs_pos = bot.CenterIfSingleFinger(fingers, abs_pos, pos.finger_distance)

# Go to the starting point and prepare for the drumroll
bot.SetFingerStates([0, 0, 0, 0])
bot.SetCartesian(abs_pos, pos.finger_distance, blocking=True)

# Commence the tapping
fingers_tapping = [i for i, v in enumerate(fingers) if v]

next_finger = 0
last_state = [0, 0, 0, 0]
for tap_num in range(num_taps):
    if num_fingers > 1 and is_drumroll:
        finger_number = fingers_tapping[next_finger % len(fingers_tapping)]
        next_states = [1 if i == finger_number else 0
                       for i in range(len(Touchbot.ALL_FINGERS))]
        middle_states = [1 if (l or n) else 0
                         for l, n in zip(last_state, next_states)]

        # Start the new finger moving down before lifting up the last one
        bot.SetFingerStates(middle_states)
        time.sleep(Touchbot.MINIMUM_FINGER_EXTENSION_TIME / 2)
        # Now start to lift the finger that was on the pad before
        bot.SetFingerStates(next_states)
        time.sleep(Touchbot.MINIMUM_FINGER_EXTENSION_TIME / 2)

        last_state = next_states
        next_finger += 1
    else:
        bot.SetFingerStates(fingers)
        # The pressure is split across all the fingers, so they are slower to
        # extend if there are multiples being used at once
        time.sleep(Touchbot.MINIMUM_FINGER_EXTENSION_TIME * num_fingers)
        bot.SetFingerStates([0, 0, 0, 0])
        time.sleep(Touchbot.MINIMUM_FINGER_EXTENSION_TIME)

# Make sure all the fingers are lifted up when it's done
bot.SetFingerStates([0, 0, 0, 0])

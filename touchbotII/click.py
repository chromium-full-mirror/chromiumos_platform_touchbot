# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import time

from touchbotII import Touchbot, Device, PositionArg

""" This is a gesture for Touchbot II that does physical clicks

WARNING: The robot needs to already have the correct fingertips installed on
the fingers you plan to click with!  If this is not the case you may cause
permanent damage to the robot!

This gesture tells the robot to do a physical click at the location you
specify with the fingers you choose.  The command line arguments are as follow:

The point/position at which to click in the following format
    x, y coordinates in the range from 0.0->1.0
    angle in degrees
    finger distance in mm that specifies how far apart the hand should open
Which fingers the robot should use to click
    Top right, Top Left, Bottom Left, Bottom Right

Example:
    For a one finger click near the bottom of the pad
    python click.py link.py 0.5 0.9 45 20 0 1 0 0
"""

try:
    # Parse the command line arguments
    device = Device(sys.argv[1])
    pos = PositionArg(*[float(v) for v in sys.argv[2:6]])
    fingers = [int(arg) for arg in sys.argv[6:10]]
except:
    print 'Usage: python %s device.p position finger_states' % __file__
    print 'Example:'
    print '    For a one finger click near the bottom of the pad'
    print '    python click.py link.py 0.5 0.9 45 20 0 1 0 0 0'
    sys.exit(1)

num_fingers = sum(fingers)
if num_fingers < 1:
    print 'You must specify at least 1 finger to use'
    sys.exit(1)

# Connect to the robot and configure the profile to move quickly
bot = Touchbot()
bot.SetSpeed(Touchbot.SPEED_FAST)

# Convert the point specifications into something the robot understands
abs_pos_hover = device.RelativePosToAbsolutePos((pos.x, pos.y),
                        angle=pos.angle, is_click=False)
abs_pos_click = device.RelativePosToAbsolutePos((pos.x, pos.y),
                        angle=pos.angle, is_click=True)
# For one finger clicks, compensate to center the finger
abs_pos_click = bot.CenterIfSingleFinger(fingers, abs_pos_click,
                                         pos.finger_distance)
abs_pos_hover = bot.CenterIfSingleFinger(fingers, abs_pos_hover,
                                         pos.finger_distance)

# Move to a position above the click target and touch down fingers
bot.SetSpeed(Touchbot.SPEED_FAST)
bot.SetCartesian(abs_pos_hover, pos.finger_distance, blocking=True)
bot.SetFingerStates(fingers)
time.sleep(1)

# Slow down and perform the actual click before speeding back up
bot.SetSpeed(Touchbot.SPEED_SLOW)
bot.SetCartesian(abs_pos_click, pos.finger_distance, blocking=True)
bot.SetFingerStates([0, 0, 0, 0])
bot.SetCartesian(abs_pos_hover, pos.finger_distance, blocking=True)

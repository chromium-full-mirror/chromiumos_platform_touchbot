# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

from touchbotII import Touchbot, Device, PositionArg

""" This is a gesture for Touchbot II that does physical clicks

WARNING: the robot must have NO fingertips already in place when running this
script or you may PERMANENTLY DAMAGE the robot.

This gesture tells the robot to do a physical click at the location you
specify with the fingers you choose.  The command line arguments are as follow:

The point/position at which to click in the following format
    x, y coordinates in the range from 0.0->1.0
    angle in degrees
    finger distance in mm that specifies how far apart the hand should open
Which fingers the robot should use to click
    Top right, Top Left, Bottom Left, Bottom Right

The robot will first go and put fingertips on the fingers you want to use, then
perform the click before returning the fingertips back into the nest.  Since
the pneumatic pistons are not strong enough to press some of the physical
buttons, it must be done this way.

WARNING on using --manual-fingertips:
Be careful when running this script with he --manual-fingertips flag. It will
mindlessly skip the fingertip setup and use whatever finger tips are present.

Example:
    For a one finger click near the bottom of the pad with tip size 0
    python click.py link.py 0.5 0.9 45 20 0 1 0 0 0

"""

try:
    # Parse the command line arguments
    device = Device(sys.argv[1])
    pos = PositionArg(*[float(v) for v in sys.argv[2:6]])
    fingers = [int(arg) for arg in sys.argv[6:10]]
    size = int(sys.argv[11])
except:
    print ('Usage: python %s device.p position finger_states' +
           ' [--manual-fingertips]' % __file__)
    print 'Example:'
    print '    For a one finger click near the bottom of the pad'
    print '    python click.py link.py 0.5 0.9 45 20 0 1 0 0 0'
    sys.exit(1)

manual_fingertips = "--manual-fingertips" in sys.argv

num_fingers = sum(fingers)
if num_fingers < 1:
    print 'You must specify at least 1 finger to use'
    sys.exit(1)

if size not in range(len(Touchbot.ALL_FINGERS)):
    print 'Invalid finger tip size';
    sys.exit(1)

# Connect to the robot and configure the profile to move quickly
bot = Touchbot()
bot.SetSpeed(Touchbot.SPEED_FAST)

# Convert the point specifications into something the robot understands
abs_pos = device.RelativePosToAbsolutePos((pos.x, pos.y), angle=pos.angle,
                                          is_click=True)
# For one finger clicks, compensate to center the finger
abs_pos = bot.CenterIfSingleFinger(fingers, abs_pos, pos.finger_distance)

above_pos = bot.AddSafetyClearance(abs_pos)

# Get the fingertips needed for the click
if not manual_fingertips:
    got_fingertips = bot.ManipulateFingertips(fingers, size, True)
    if got_fingertips:
        bot.SetFingerStates([0, 0, 0, 0])
        fingertips_present = bot.DetectFingertips()
        got_fingertips = bool(fingertips_present == fingers)
    if not got_fingertips:
        print 'Error: Failed to get the fingertips required'
        sys.exit(1)

# First get into position above the pad
bot.SetCartesian(above_pos, pos.finger_distance, blocking=True)

# Slow down and perform the actual click before speeding back up
bot.SetSpeed(Touchbot.SPEED_SLOW)
bot.SetCartesian(abs_pos, pos.finger_distance, blocking=True)
bot.SetCartesian(above_pos, pos.finger_distance, blocking=True)
bot.SetSpeed(Touchbot.SPEED_FAST)

# Put the fingers back
if not manual_fingertips:
    returned_fingertips = bot.ManipulateFingertips(fingers, size, False)
    if returned_fingertips:
        fingertips_present = bot.DetectFingertips()
        returned_fingertips = not any(fingertips_present)
    if not returned_fingertips:
        print 'Error:Unable to put fingertips back'
        sys.exit(1)

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This script records the robot positions that represent the corners
of a device and stores them for later use.

The operator runs the script and manually moves the robot to each corner
of the touchpad.  Then the script store a device calibration file.

Usage: python calibrate_new_device.py lumpy
"""
import pickle
import sys

from touchbotII import Touchbot


# Connect to the robot and set its speed to slow
bot = Touchbot()
prof = bot.GetCurrentProfile()
prof.speed = Touchbot.SPEED_SLOW
bot.SetProfileData(prof)

# First make sure there are no fingertips
if any(bot.DetectFingertips()):
    print 'You can not have any fingertips on for this script'
    sys.exit(-1)

# Get the smallest fingertips
if not bot.GetFingertips(0):
    print 'Failed to get the fingertips!'
    sys.exit(-1)

# Bring the fingers all in close together and raise the whole arm up
pos = bot.GetCurrentPosition()
pos.ax_1 += Touchbot.SAFETY_CLEARANCE # Move up in the Z direction
pos.ax_5 = 10.0 # Inter-finger distance in approximately mm
pos = bot.SetAngles(pos)

# Extend the fingers once the user says everything is okay
raw_input('press enter to continue')
bot.SetFingerStates([1, 1, 1, 1])

# Walk the user through calibrating each of the corners
CORNERS = ['top right', 'top left', 'bottom left', 'bottom right']
corners = {}
for corner in CORNERS:
    print 'Position the fingers in the %s corner of the device' % corner
    print 'and keep the hand as aligned with the touchpad as possible'
    corners[corner] = bot.CalibratePosition()

# Calibrate the physical click height
bot.SetFingerStates([0, 0, 0, 0])
print 'Lower the robot down until it has just clicked the pad'
click = bot.CalibratePosition()

# Standardize the angle by averaging all the readings
angle = sum([corners[c].yaw for c in corners]) / 4.0
for c in corners:
    corners[c].yaw = angle

pickle.dump({'corners':corners, 'click_z': click.z},
            open('%s.p' % sys.argv[1], 'wb'))

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This script records the robot positions that represent the corners
of a device and stores them for later use.

The operator runs the script and manually moves the robot to each corner
of the touchpad.  Then the script stores two device calibration files to
the hard drive.  One is the full size touch device and the other is
scaled down (if required) to ensure that the robot can click each corner
at the same time.  This is used for more complicated gestures with
multiple fingers and is suffixed with '_min'

Usage: python calibrate_new_device.py lumpy

produces: lumpy.p and lumpy_min.p
"""
import pickle
import sys

from touchbotII import Touchbot, Device

def dist(p1, p2):
    return ((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2) ** 0.5

manual_fingertips = "--manual-fingertips" in sys.argv

# Connect to the robot and set its speed to slow
bot = Touchbot()
bot.SetSpeed(Touchbot.SPEED_SLOW)

if not manual_fingertips:
    # First make sure there are no fingertips
    if any(bot.DetectFingertips()):
        print 'You can not have any fingertips on for this script'
        sys.exit(1)

    # Get the smallest fingertips
    bot.ManipulateFingertips([1, 1, 1, 1], 0, True)
    fingers_present = bot.DetectFingertips()
    if not all(fingers_present):
        print 'Some finger was not picked up!'
        sys.exit(1)
else:
    print 'skipping fingertip setup are you sure? [y/N]'
    response = sys.stdin.readline()
    if response.strip() not in ('y', 'Y', 'yes', 'Yes'):
        sys.exit(1)

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

device_file = '%s.p' % sys.argv[1]
with open(device_file, 'wb') as fo:
    pickle.dump({'corners': corners, 'click_z': click.z}, fo)

# Now, check if the device is too big, if it is scale it down and save that
# device spec as well.  The diagonal distance can't be greater than the max
# finger spread of the robot
dev = Device(device_file)
tl = dev.RelativePosToAbsolutePos((0, 0))
tr = dev.RelativePosToAbsolutePos((1, 0))
bl = dev.RelativePosToAbsolutePos((0, 1))
br = dev.RelativePosToAbsolutePos((1, 1))

# Computing the ratio to scale the height/width by to maximize the diagonal
# distance of the device spec.
width = max([dist(bl, br), dist(tl, tr)])
height = max([dist(bl, tl), dist(tr, br)])
scaling_factor = bot.MAX_FINGER_DISTANCE / ((width ** 2 + height ** 2) ** 0.5)

if scaling_factor < 1.0:
    offset = (1.0 - scaling_factor) / 2.0
    corners['top right'] = dev.RelativePosToAbsolutePos((1.0 - offset, offset))
    corners['top left'] = dev.RelativePosToAbsolutePos((offset, offset))
    corners['bottom left'] = dev.RelativePosToAbsolutePos(
                                                  (offset, 1.0 - offset))
    corners['bottom right'] = dev.RelativePosToAbsolutePos(
                                                  (1.0 - offset, 1.0 - offset))
min_device_file = '%s_min.p' % sys.argv[1]
with open(min_device_file, 'wb') as fo:
    pickle.dump({'corners':corners, 'click_z': dev.click_z}, fo)

# Return the fingertips to the nest
if not manual_fingertips:
    # Return the fingertips to the nest
    bot.ManipulateFingertips([1, 1, 1, 1], 0, False)
    fingers_present = bot.DetectFingertips()
    if any(fingers_present):
        print 'Some finger was not returned properly!'
        sys.exit(1)
else:
    # Clear from touchpad
    pos = bot.AddSafetyClearance(bot.GetCurrentPosition())
    bot.SetAngles(pos)

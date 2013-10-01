# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This is a line drawing script for Touchbot II

By using its rather long set of parameters, this script can generate
a wide array of different straight-line based gestures on the Touchbot II.

The gestures take in two points (start and end) which consist of:
    x, y coordinates in the range from 0.0->1.0
    angle in degrees
    finger distance in mm that specifies how far apart the hand should open
Which fingers the robot should extend as a list of 4 booleans
    Top right, Top Left, Bottom Left, Bottom Right
And finally a speed in approximately mm/s

The robot will then linearly interpolate between those two points

Examples:
    For a two finger scroll motion you might do something like:
    python line.py link.p 0.5 0.1 0 40 0.5 0.9 0 40 0 1 0 1 100

    For a human-like pinch zoom motion
    python line.py lumpy.p 0.5 0.5 30 45 0.5 0.5 27 20 1 0 1 0 75
"""

import math
import sys

from collections import namedtuple

from touchbotII import Touchbot, Device

Position = namedtuple('Position', ['x', 'y', 'angle', 'finger_distance'])

try:
    # Load the device spec
    device = Device(sys.argv[1])
    start = Position(*[float(v) for v in sys.argv[2:6]])
    end = Position(*[float(v) for v in sys.argv[6:10]])
    fingers = [int(arg) for arg in sys.argv[10:14]]
    speed = float(sys.argv[14])
except:
    print 'Usage: python %s device.p start end finger_states speed' % __file__
    print '     * start and end: formatted as x y angle finger_distance'
    print '     * finger_states: a list of 4 values (1s and 0s)'
    print '     * speed: a decimal value for the speed in mm/s'
    print
    print 'For a two finger scroll motion you might do something like:'
    print 'python %s link.p 0.5 0.1 0 40 0.5 0.9 0 40 0 1 0 1 100' % __file__
    print
    print 'For a human-like pinch zoom motion'
    print 'python %s lumpy.p 0.5 0.5 30 45 0.5 0.5 27 20 1 0 1 0 75' % __file__
    sys.exit(-1)

print 'Executing the line defined by:'
print '\tStart:   %s' % str(start)
print '\tEnd:     %s' % str(end)
print '\tFingers: %s' % str(fingers)
print '\tSpeed:   %f' % speed

# Connect to the robot and configure the profile
bot = Touchbot()
prof = bot.GetCurrentProfile()
prof.speed = speed
prof.straight = Touchbot.STRAIGHT_INTERPOLATION
bot.SetProfileData(prof)

if not (bot.IsLegalRelativeCoordinate((start.x, start.y)) and
        bot.IsLegalRelativeCoordinate((end.x, end.y))):
    print 'All coordinates must fall in the range of 0.0 to 1.0'
    sys.exit(-1)
if not bot.IsLegalFingerList(fingers):
    print 'Your finger list must contain exactly 4 values, each either 1 or 0'
    sys.exit(-1)
if not bot.IsLegalSpeed(speed):
    print 'The speed %f is not acceptable for this robot' % speed
    sys.exit(-1)


# Convert the point specifications into something the robot understands
abs_start = device.RelativePosToAbsolutePos((start.x, start.y),
                                            angle=start.angle)
abs_end = device.RelativePosToAbsolutePos((end.x, end.y),
                                          angle=end.angle)

# Go to the starting point and lower the fingers
bot.SetFingerStates([0, 0, 0, 0])
bot.SetCartesian(abs_start, start.finger_distance, blocking=True)
bot.SetFingerStates(fingers)

# Move to the end point and lift them back up
bot.SetCartesian(abs_end, end.finger_distance, blocking=True)
bot.SetFingerStates([0, 0, 0, 0])

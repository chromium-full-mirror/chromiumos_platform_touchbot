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
A speed in approximately mm/s
Which kind of line to do which should be either "swipe" or "basic"

The robot will then linearly interpolate between those two points

Examples:
    For a two finger scroll motion you might do something like:
    python line.py link.p 0.5 0.1 0 40 0.5 0.9 0 40 0 1 0 1 100 swipe

    For a human-like pinch zoom motion
    python line.py lumpy.p 0.5 0.5 30 45 0.5 0.5 27 20 1 0 1 0 75 basic
"""

import sys
import time
import traceback
from collections import namedtuple

from touchbotII import Touchbot, Device, PositionArg


try:
    # Load the device spec
    device = Device(sys.argv[1])
    start = PositionArg(*[float(v) for v in sys.argv[2:6]])
    end = PositionArg(*[float(v) for v in sys.argv[6:10]])
    fingers = [int(arg) for arg in sys.argv[10:14]]
    speed = float(sys.argv[14])
    is_swipe = bool(sys.argv[15] == 'swipe')
    is_fling = bool(sys.argv[15] == 'fling')
    delay = 0.0
    if len(sys.argv) > 15:
        delay = float(sys.argv[16])
except:
    traceback.print_exc()
    print (('Usage: python %s device.p start end finger_states speed ' +
            '[swipe|basic|fling] [delay]') % __file__)
    print '     * start and end: formatted as x y angle finger_distance'
    print '     * finger_states: a list of 4 values (1s and 0s)'
    print '     * speed: a decimal value for the speed in mm/s'
    print '     * which kind of line to draw: either "swipe" or "basic"'
    print
    print 'For a two finger scroll motion you might do something like:'
    print ('python %s link.p 0.5 0.1 0 40 0.5 0.9 0 40 0 1 0 1 100 swipe' %
           __file__)
    print
    print 'For a human-like pinch zoom motion'
    print ('python %s lumpy.p 0.5 0.5 30 45 0.5 0.5 27 20 1 0 1 0 75 basic' %
          __file__)
    sys.exit(-1)

print 'Executing the line defined by:'
print '\tStart:     %s' % str(start)
print '\tEnd:       %s' % str(end)
print '\tFingers:   %s' % str(fingers)
print '\tSpeed:     %f' % speed
print '\tIs Swipe?: %s' % str(is_swipe)
print '\tIs Fling?: %s' % str(is_fling)
print '\tDelay:     %f' % delay

# Connect to the robot and configure the profile
bot = Touchbot()
prof = bot.GetCurrentProfile()
prof.speed = speed
prof.straight = Touchbot.STRAIGHT_INTERPOLATION
bot.SetProfileData(prof)

if not (bot.IsLegalRelativeCoordinate((start.x, start.y)) and
        bot.IsLegalRelativeCoordinate((end.x, end.y))):
    print ('All coordinates must fall in the range of %s' %
           str(Touchbot.RELATIVE_COORDINATE_RANGE))
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

# Offset the position to center the finger if it's only using one
abs_start = bot.CenterIfSingleFinger(fingers, abs_start, start.finger_distance)
abs_end = bot.CenterIfSingleFinger(fingers, abs_end, end.finger_distance)

# Go to the starting point
bot.SetFingerStates([0, 0, 0, 0])
bot.SetCartesian(abs_start, start.finger_distance, blocking=True)

# Sort out what to do with the fingers as it moves depending on if it is a
# swipe or a regular, basic line.
if is_swipe:
    # start moving to end point
    bot.SetCartesian(abs_end, end.finger_distance, blocking=False)

    distance_to_travel = abs_start.CartesianDistanceFrom(abs_end)
    distance_traveled = 0.0
    # Wait until 1/4 of the distance has been traveled to extend the fingers
    # This allows the hand to get up to speed before touching the pad
    while distance_traveled < 0.25 * distance_to_travel:
        curr_pos = bot.GetCurrentPosition()
        distance_traveled = curr_pos.CartesianDistanceFrom(abs_start)
    bot.SetFingerStates(fingers)

    # Raise the fingers after only 3/4 of the distance has been traveled
    while distance_traveled < 0.75 * distance_to_travel:
        curr_pos = bot.GetCurrentPosition()
        distance_traveled = curr_pos.CartesianDistanceFrom(abs_start)
    bot.SetFingerStates([0, 0, 0, 0])
elif is_fling:
    # put fingers down and wait for delay
    bot.SetFingerStates(fingers)
    time.sleep(delay)
    bot.SetCartesian(abs_end, end.finger_distance, blocking=False)

    # Move to end point
    distance_to_travel = abs_start.CartesianDistanceFrom(abs_end)
    distance_traveled = 0.0
    while distance_traveled < 0.75 * distance_to_travel:
        curr_pos = bot.GetCurrentPosition()
        distance_traveled = curr_pos.CartesianDistanceFrom(abs_start)
    bot.SetFingerStates([0, 0, 0, 0])
else:
    # put fingers down and wait for delay
    bot.SetFingerStates(fingers)
    time.sleep(delay)
    # Move to end point
    bot.SetCartesian(abs_end, end.finger_distance, blocking=True)
    bot.SetFingerStates([0, 0, 0, 0])

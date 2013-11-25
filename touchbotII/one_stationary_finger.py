# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This is a gesture that draws a line with one finger while holding
another steady in a fixed spot.

The script takes in three points in relative coordinates.  The first specifies
where the stationary finger should be placed.  The other two specify the start
and end coordinates for the mobile finger.  Finally it takes a speed paramater
between 0 and 100.

Usage:
    python one_stationary_finger.py device.p stationary_pos start_pos
           end_pos speed

Example:
    # Slowly move one finger from the top left to bottom right corner while
    # keeping a finger stationary in the bottom left
    python one_stationary_finger.py link.p 0.1 0.9 0.1 0.1 0.9 0.9 10
"""

import math
import sys
import time

from collections import namedtuple

from touchbotII import Touchbot, Device, PositionArg

NUM_STEPS = 15

try:
    device = Device(sys.argv[1])
    stationary_x, stationary_y = (float(sys.argv[2]), float(sys.argv[3]))
    start_x, start_y = (float(sys.argv[4]), float(sys.argv[5]))
    end_x, end_y = (float(sys.argv[6]), float(sys.argv[7]))
    speed = float(sys.argv[8])
except:
    print ('Usage: python %s device.p stationary_pos start_pos end_pos speed' %
           __file__)
    print 'Example: python %s link.p 0.1 0.9 0.1 0.1 0.9 0.9 10' % __file__
    sys.exit(-1)

# Connect to the robot and configure the profile
bot = Touchbot()
prof = bot.GetCurrentProfile()
prof.speed = speed
prof.straight = Touchbot.STRAIGHT_INTERPOLATION
prof.inRange = Touchbot.BLEND_MOVEMENTS
bot.SetProfileData(prof)

if not (bot.IsLegalRelativeCoordinate((stationary_x, stationary_y)) and
        bot.IsLegalRelativeCoordinate((start_x, start_y)) and
        bot.IsLegalRelativeCoordinate((end_x, end_y))):
    print ('All coordinates must fall in the range of %s' %
           str(Touchbot.RELATIVE_COORDINATE_RANGE))
    sys.exit(-1)
if not bot.IsLegalSpeed(speed):
    print 'The speed %f is not acceptable for this robot' % speed
    sys.exit(-1)


abs_stationary = device.RelativePosToAbsolutePos((stationary_x, stationary_y))

# Split the movement up into a bunch of small steps to increase precision
# in the middle of the gesture
last_angle = None
for step in range(NUM_STEPS):
    # Compute where the moving finger should be at this point
    percent = float(step) / float(NUM_STEPS - 1)
    moving_finger_x = percent * end_x + (1.0 - percent) * start_x
    moving_finger_y = percent * end_y + (1.0 - percent) * start_y

    # Compute the hand position required to put the fingers on these spots
    mid_x = (stationary_x + moving_finger_x) / 2.0
    mid_y = (stationary_y + moving_finger_y) / 2.0
    abs_mid = device.RelativePosToAbsolutePos((mid_x, mid_y))

    # Compute the angle the hand needs to make
    abs_stationary = device.RelativePosToAbsolutePos(
                                (stationary_x, stationary_y))
    abs_moving = device.RelativePosToAbsolutePos(
                                (moving_finger_x, moving_finger_y))
    angle = math.degrees(math.atan((abs_stationary.y - abs_moving.y) /
                                   (abs_stationary.x - abs_moving.x)))
    # The fingers are offset by 45 degrees
    angle += 45

    # Check to see if the angle aliased onto another configuration
    # This can cause the robot to spontaneously switch the role of the fingers
    # if we don't check for it and compensate.
    if last_angle:
        curr_change = abs(angle - last_angle)
        aliased_change_pos = abs((angle + 180) - last_angle)
        aliased_change_neg = abs((angle - 180) - last_angle)
        min_change = min([curr_change, aliased_change_pos, aliased_change_neg])
        if aliased_change_pos == min_change:
            angle = angle + 180
        elif aliased_change_neg == min_change:
            angle = angle - 180
    last_angle = angle
    abs_mid.yaw = angle

    # Find the distance between the two points to spread the fingers
    dx = abs_stationary.x - abs_moving.x
    dy = abs_stationary.y - abs_moving.y
    dist = (dx ** 2 + dy ** 2) ** 0.5

    # Execute the move
    bot.SetCartesian(abs_mid, finger_distance=dist, blocking=False)

    # If this is the first or last step, block then raise/lower the fingertips
    if step in [0, (NUM_STEPS - 1)]:
        bot.Wait()
        if step == 0:
            bot.SetFingerStates([1, 0, 1, 0])
        else:
            bot.SetFingerStates([0, 0, 0, 0])

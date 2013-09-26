# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Replay a finger recording with the Touchbot II

This script takes in a device spec (for the device the gesture
should be replayed on) and a path file (the list of readings that
were recorded originally) and reproduces that gesture with the
robot.

This only supports nice, clean logs.  If there are stray touches,
palms, more than 2 fingers, etc, in the log is WILL CAUSE PROBLEMS.
Make sure your logs are perfect before trying to replay them or
it may DAMAGE THE ROBOT PERMANENTLY.

Usage:
    python replay.py device_spec.p path_to_follow.py

    ie: python replay.py lumpy.p spiral.p
"""

import math
import pickle
import sys

from device import Device
from touchbot import Touchbot

def distance(p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5

try:
    # Load the device spec
    device = Device(sys.argv[1])
    # Load the path to follow
    path = pickle.load(open(sys.argv[2], 'r'))
except:
    print 'Usage: python %s device_spec.p path_to_follow.p' % __file__
    sys.exit(-1)

# Connect to the robot and configure the profile
bot = Touchbot()
prof = bot.GetCurrentProfile()
prof.speed = Touchbot.SPEED_MEDIUM
prof.inRange = Touchbot.BLEND_MOVEMENTS
bot.SetProfileData(prof)

last_p0 = None
last_p1 = None
last_angle = 0
bot.SetFingerStates([0, 0, 0, 0])
for i, positions in enumerate(path):
    # TODO charliemooney: A better way to do this than just ignoring them
    # There are a lot of reports and can make the movement jerky if you use
    # all of them.  This thins it out.
    if i % 4 != 0:
        continue

    if len(positions) == 0:
        bot.SetFingerStates([0, 0, 0, 0])
        continue
    elif len(positions) == 1:
        p0 = last_p0 if last_p0 else (0.1, 0.1) # Dummy position
        bot.SetFingerStates([0, 1, 0, 0])
    elif len(positions) == 2:
        p0 = positions[1]
        bot.SetFingerStates([0, 1, 0, 1])
    else:
        print 'ERROR, invalid state!'
        print positions
        sys.exit(-1)

    p1 = positions[0]

    # Make sure the fingers don't try to swap order by checking the distances
    if last_p0 and last_p1:
        p0_p0_distance = distance(p0, last_p0)
        p0_p1_distance = distance(p0, last_p1)
        if p0_p0_distance > p0_p1_distance:
            tmp = p0
            p0 = p1
            p1 = tmp
    last_p0 = p0
    last_p1 = p1

    # To compute the position of the hand to put the fingers at the right
    # places, center the hand over the mid-point between the fingers, then
    # compute the distance and angle between them and rotate the wrist to
    # that angle and open the fingers enough to place two of the fingers
    # in the right spots
    #         +
    #         |   p0         p_mid        p1
    #         |    +           +           +
    #         |
    #         |    <-----------+----------->
    #         |              dist
    #         |
    #         +-------------------------------+

    # p1 & p1 are the relative coordinates of the two fingers
    # p_mid is the relative coordinates of the point in between
    p_mid = ((p1[0] + p0[0]) / 2.0, (p1[1] + p0[1]) / 2.0)
    # Convert to the format we can actually send to the robot
    abs_p = device.RelativePosToAbsolutePos(p_mid)

    # Find the angle between the two finger positions (p0 and p1)
    # This must be done using absolute coordinates, because depending on the
    # geometry of the touchpad the angles may be slightly different for
    # different devices.
    abs_p0 = device.RelativePosToAbsolutePos(p0)
    abs_p1 = device.RelativePosToAbsolutePos(p1)
    abs_p.yaw = math.degrees(math.atan((abs_p0.y - abs_p1.y) /
                                       (abs_p0.x - abs_p1.x)))
    # The fingers are offset by 45 degrees
    abs_p.yaw += 45

    # Check that the angle hasn't aliased onto the opposite side
    # and correct it if it has
    ang_change = abs(abs_p.yaw - last_angle)
    alias_ang_change = abs((abs_p.yaw - 180) - last_angle)
    if ang_change > alias_ang_change:
        abs_p.yaw = abs_p.yaw - 180
    last_angle = abs_p.yaw

    # Find the distance between p0 and p1 and spread the fingers
    dist = distance((abs_p0.x, abs_p0.y), (abs_p1.x, abs_p1.y))

    # Execute the move
    bot.SetCartesian(abs_p, finger_distance=dist, blocking=False)

bot.SetFingerStates([0, 0, 0, 0])

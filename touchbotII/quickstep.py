# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This is a gesture for running the Quickstep latency tests

This gesture has the robot run a single finger in a zig-zag over the pad at a
fixed speed.  It is intended to be used with a Quickstep latency measurement
device.  The robot will move its finger back and forth over the laser beam and
then you can collect the Quickstep and touch logs to generate a latency
estimation.

This gesture only takes two arguments: the device spec and the speed

Example:
    python quickstep.py link.p 100
"""

import numpy
import sys

from touchbotII import Touchbot,Device
from collections import namedtuple

NUM_CROSSINGS = 40
EDGE_BUFFER = 0.1
FINGER_SPREAD = 20
FINGERS = [0, 0, 1, 0]
TOP_EDGE = EDGE_BUFFER
BOTTOM_EDGE = 1.0 - EDGE_BUFFER

# The fingers must extend a little further than normal to avoid accidentally
# interrupting the laser beam.
LASER_CLEARANCE_SHIFT = 5

try:
    # Load the device spec
    device = Device(sys.argv[1])
    speed = float(sys.argv[2])
except:
    print 'Usage: python %s device.p speed' % __file__
    print 'Example: python %s link.p 100' % __file__
    sys.exit(-1)

# Connect to the robot and configure the profile to
bot = Touchbot()
prof = bot.GetCurrentProfile()
prof.speed = Touchbot.SPEED_MEDIUM
prof.inRange = Touchbot.BLEND_MOVEMENTS
prof.straight = Touchbot.STRAIGHT_INTERPOLATION
bot.SetProfileData(prof)

# Get the robot in position and ready to run the test
bot.SetFingerStates([0, 0, 0, 0])
start = device.RelativePosToAbsolutePos((EDGE_BUFFER, EDGE_BUFFER))
bot.SetCartesian(start, finger_distance=FINGER_SPREAD, blocking=True)
bot.SetFingerStates(FINGERS)

# Adjust the speed to the selected value before starting the actual test
bot.SetSpeed(speed)

# Compute a number of lines to draw across the pad and move in a zig-zag
step = 1.0 / (NUM_CROSSINGS / 4.0)
xs = [i * step for i in range(int(NUM_CROSSINGS / 4.0))]
xs = xs + [(1.0 - i * step) for i in range(int(NUM_CROSSINGS / 4.0))]
for x in xs:
    abs_start = device.RelativePosToAbsolutePos((x, TOP_EDGE))
    abs_start = bot.CenterIfSingleFinger(FINGERS, abs_start, 20)
    abs_start.z += LASER_CLEARANCE_SHIFT
    bot.SetCartesian(abs_start, finger_distance=FINGER_SPREAD, blocking=True)

    abs_end = device.RelativePosToAbsolutePos((x, BOTTOM_EDGE))
    abs_end = bot.CenterIfSingleFinger(FINGERS, abs_end, 20)
    abs_end.z += LASER_CLEARANCE_SHIFT
    bot.SetCartesian(abs_end, finger_distance=FINGER_SPREAD, blocking=True)

bot.SetFingerStates([0, 0, 0, 0])

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import time

from touchbotII import Touchbot, Device

""" This is a gesture that places one finger in a fixed point on the pad
and then taps a number of times around it with a second finger.

This gesture only takes a location for the stationary finger and a device
description.

Arguments: device.p stationary_x stationary_y
Example:
    To tap in the center of the pad
    python sationary_finger_with_taps_around_it.py link.py 0.5 0.5

"""

NUM_TAPS = 50
FINGER_DISTANCE = 20
YAW_SAFETY_BUFFER = 10

try:
    device = Device(sys.argv[1])
    stationary_x, stationary_y = (float(sys.argv[2]), float(sys.argv[3]))
except:
    print ('Usage: python %s device.p stationary_x stationary_y' %
           __file__)
    print 'Example: python %s link.p 0.5 0.5' % __file__
    sys.exit(-1)

bot = Touchbot()
bot.SetSpeed(bot.SPEED_MEDIUM)
bot.SetFingerStates([0, 0, 0, 0])

if not bot.IsLegalRelativeCoordinate((stationary_x, stationary_y)):
    print ('Coordinates must fall in the range of %s' %
           str(Touchbot.RELATIVE_COORDINATE_RANGE))
    sys.exit(-1)

# Compute the extreme wrist angles that the robot can do at this position
start_pos = device.RelativePosToAbsolutePos((stationary_x, stationary_y))
bot.SetCartesian(start_pos, blocking=True)
min_yaw, max_yaw = bot.NonBindingYawRange(safety_buffer=YAW_SAFETY_BUFFER)

# Nudge the wrist into position to make sure it's on the right side
pos = bot.GetCurrentPosition()
pos.ax_4 = bot.AX_4_MAX
bot.SetAngles(pos, blocking=True)

# Calculate the positions, and move to them
for i in range(NUM_TAPS):
    abs_pos = device.RelativePosToAbsolutePos((stationary_x, stationary_y))
    abs_pos.yaw = (float(NUM_TAPS - i) / float(NUM_TAPS) * (max_yaw - min_yaw)
                   + min_yaw)
    abs_pos = bot.CenterIfSingleFinger([1, 0, 0, 0], abs_pos, FINGER_DISTANCE)

    # Move into position and tap the second finger
    bot.SetCartesian(abs_pos, FINGER_DISTANCE, blocking=True)
    bot.SetFingerStates([1, 1, 0, 0])
    time.sleep(bot.MINIMUM_FINGER_EXTENSION_TIME)
    bot.SetFingerStates([1, 0, 0, 0])

#Lift all fingers before finishing
bot.SetFingerStates([0, 0, 0, 0])

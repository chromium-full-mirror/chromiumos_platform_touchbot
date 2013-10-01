# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" This script tests the various functionalities of the Touchbot II

By running this script you can exercise all the features, moving the
robot, manipulating the fingers, etc.  This is useful for debugging and
development prior to more sophisticated uses of the robot being implemented.
"""

import time
from touchbotII import Touchbot


# Connect to the robot
bot = Touchbot()

# Have the user specify two positions by manually adjusting the robot
pos1 = bot.CalibratePosition()
pos2 = bot.CalibratePosition()

# Load the current profile and set the speed much slower to prevent damage
prof = bot.GetCurrentProfile()
prof.speed = Touchbot.SPEED_SLOW
bot.SetProfileData(prof)
prof = bot.GetCurrentProfile()

# Move between the two positions measured earlier
bot.SetAngles(pos1)
bot.SetAngles(pos2)
bot.SetCartesian(pos1)
bot.SetCartesian(pos2)

# Extend, then retract each finger in turn
for f in Touchbot.ALL_FINGERS:
    bot.SetGPIO(f, 1)
    time.sleep(1)
    bot.SetGPIO(f, 0)

# Prime the nest, open and then close it
bot.SetGPIO(Touchbot.NEST_OPEN_VALVE, 1)
bot.SetGPIO(Touchbot.NEST_CLOSE_VALVE, 0)
bot.SetGPIO(Touchbot.NEST_OPEN_VALVE, 0)
bot.SetGPIO(Touchbot.NEST_CLOSE_VALVE, 1)
time.sleep(2)
bot.SetGPIO(Touchbot.NEST_OPEN_VALVE, 1)
bot.SetGPIO(Touchbot.NEST_CLOSE_VALVE, 0)

# Display several readings from the fingertip sensor
for i in range(10):
    bot.GetGPIO(Touchbot.FINGERTIP_DETECT)
    time.sleep(1)

# Test the robot's ability to change its fingertips
for size in range(len(Touchbot.NEST_POSITION_FILES)):
    bot.GetFingertips(size)
    bot.DropFingertips()

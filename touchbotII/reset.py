# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

from touchbotII import Touchbot, Device, PositionArg

""" This is a gesture for Touchbot II moves the hand above the touchpad

When you run this gesture the robot will lift up clear of where is is,
move to to a position over the center of the touchpad and then slowly
lower down until it is hovering just over the pad.  This is used to get
the robot hand into a safe place to run other gestures from.

Example:
    python click.py link.p 20

"""

try:
    # Parse the command line arguments
    device = Device(sys.argv[1])
    speed = int(sys.argv[2])
except:
    print 'Usage: python %s device.p speed' % __file__
    print 'Example:'
    print '    python reset.py link.p 5'
    sys.exit(1)

# Connect to the robot and configure the profile to use the speed
bot = Touchbot()

if not bot.IsLegalSpeed(speed):
    print 'Error %d is not a legal speed value' % speed
    sys.exit(1)
bot.SetSpeed(speed)
bot.SetFingerStates([0, 0, 0, 0])

# Find the waypoints that we will be using
cur_pos = bot.GetCurrentPosition()
above_cur_pos = bot.AddSafetyClearance(cur_pos)
center = device.RelativePosToAbsolutePos((0.5, 0.5))
above_center = bot.AddSafetyClearance(center)

# Lift up, before moving over the center of the pad and slowly
# lowering down
bot.SetCartesian(above_cur_pos)
bot.SetCartesian(above_center)

bot.SetSpeed(Touchbot.SPEED_SLOW)
bot.SetCartesian(center, blocking=True)

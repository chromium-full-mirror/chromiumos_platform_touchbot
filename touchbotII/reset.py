# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

from touchbotII import Touchbot, Device, PositionArg

""" This is a gesture for Touchbot II moves the hand above the touchpad

When you run this gesture the robot will lift up clear of where is is,
move to to a position over the center of the touchpad or the fingertip
nest and then slowly lower down until it is hovering just over it.
This is used to get the robot hand into a safe place to run other
gestures from.

Usage:
    python reset.py device.p (pad|nest) speed

Example:
    python reset.py link.p pad 20
    python reset.py lumpy.p nest 10

"""

try:
    # Parse the command line arguments
    device = Device(sys.argv[1])
    destination = sys.argv[2].lower()
    speed = int(sys.argv[3])
except:
    print 'Usage: python %s device.p (pad|nest) speed' % __file__
    print 'Example:'
    print '    python reset.py link.p pad 5'
    sys.exit(1)

# Connect to the robot and configure the profile to use the speed
bot = Touchbot()
if not bot.IsLegalSpeed(speed):
    print 'Error %d is not a legal speed value (1-100)' % speed
    sys.exit(1)
if destination not in ['pad', 'nest']:
    print 'Error "%s" is not a legal destination' % destination
    sys.exit(1)
bot.SetSpeed(speed)
bot.SetFingerStates([0, 0, 0, 0])

# Find the waypoints that we will be using
cur_pos = bot.GetCurrentPosition()
above_cur_pos = bot.AddSafetyClearance(cur_pos)
if destination == 'pad':
    dest = device.RelativePosToAbsolutePos((0.5, 0.5))
else:
    dest = bot.nest_positions[0]
above_dest = bot.AddSafetyClearance(dest)

# Lift up, before moving over the destination and slowly lowering down
bot.SetCartesian(above_cur_pos)
bot.SetCartesian(above_dest)

bot.SetSpeed(Touchbot.SPEED_SLOW)
bot.SetCartesian(dest, blocking=True)

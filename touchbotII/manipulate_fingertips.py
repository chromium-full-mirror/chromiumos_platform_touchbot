# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

from touchbotII import Touchbot

""" This is a gesture for Touchbot II to programmatically control which
fingertips the robot has.

This script will mainly be used by the automated firmware test.  In general,
if you want to change the fingertips it will be easier and safer to manipulate
them by hand.  If this is an option, please do it.  Running this script can
cause PERMANENT DAMAGE to the robot if you are not careful, please make sure
you know the state of the robot and exactly what you are doing before
running this script.

Specifically, you need to make sure that you do not tell the robot to put large
fingertips back into a small nest position, or try to pick up new fingertips
when you already have some.  Other problems can arise if this is used when the
robot's hand is behind another object (such as the nest itself) and does not
have a clear line of travel.  Always make sure you know which fingertips are
where and that the robot can move freely before running this gesture!

This script takes in which fingers it should be changing the tips of, the size
of the tips and if it should be picking up tips or leaving them behind.

Usage:
    manipulate_fingertips fingers size should_keep_fingertips

Examples:
    To return all four size 0 fingertips to the nest'
        python manipulate_fingertips.py 1 1 1 1 0 False'
    To pick up two size 3 fingertips'
        python manipulate_fingertips.py 0 1 0 1 3 True'
"""
NUM_RETRIES = 3

try:
    fingers = [int(arg) for arg in sys.argv[1:5]]
    size = int(sys.argv[5])
    should_keep_fingertips = bool(sys.argv[6] == 'True')
except:
    print 'Usage: python %s fingers size should_keep_fingertips' % __file__
    print 'Example:'
    print '    To return all four size 0 fingertips to the nest'
    print '    python %s 1 1 1 1 0 False' % __file__
    print '    To pick up two size 3 fingertips'
    print '    python %s.py 0 1 0 1 3 True' % __file__
    sys.exit(1)

num_fingers = sum(fingers)
if num_fingers < 1:
    print 'You must specify at least 1 finger to use'
    sys.exit(1)

# Connect to the robot and configure the profile to move quickly
bot = Touchbot()
bot.SetSpeed(Touchbot.SPEED_FAST)

# Lift the hand up to get clear of anything it may be near before moving
pos = bot.GetCurrentPosition()
pos = bot.AddSafetyClearance(pos)
error_code, _ = bot.SetCartesian(pos)
if error_code:
    print 'Error: Could not move clear of starting posisiton!'
    sys.exit(1)

# Check what we can to make sure there will not be a collision
success = False
if should_keep_fingertips:
    for i in range(NUM_RETRIES):
        fingertips_present = bot.DetectFingertips()
        if not any([want and have for want, have
                    in zip(fingers, fingertips_present)]):
            success = True
            break

    if not success:
        print 'Error: there are already fingertips there!'
        sys.exit(1)
else:
    for i in range(NUM_RETRIES):
        fingertips_present = bot.DetectFingertips()
        if all([not should_drop or have for should_drop, have
                    in zip(fingers, fingertips_present)]):
            success = True
            break
    if not success:
        print 'Error: Can not return fingertips that are not attached!'
        sys.exit(1)

# Execute the swap
success = bot.ManipulateFingertips(fingers, size, should_keep_fingertips)
if not success:
    print 'Error: Error interacting with the fingertip nest'
    sys.exit(1)

# Check what we can to make sure it worked correctly
success = False
if should_keep_fingertips:
    for i in range(NUM_RETRIES):
        fingertips_present = bot.DetectFingertips()
        if all([not want or have for want, have
                in zip(fingers, fingertips_present)]):
            success = True
            break
    if not success:
        print 'Error: Not all the fingertips were picked up!'
        sys.exit(1)
else:
    for i in range(NUM_RETRIES):
        fingertips_present = bot.DetectFingertips()
        if not any([should_drop and have for should_drop, have
                    in zip(fingers, fingertips_present)]):
            success = True
            break
    if not success:
        print 'Error: Not all the fingertips were dropped!'
        sys.exit(1)

# Lift the hand up so that it gets clear of the nest to prevent accidents
pos = bot.GetCurrentPosition()
pos = bot.AddSafetyClearance(pos)
error_code, _ = bot.SetCartesian(pos)
if error_code:
    print 'Error: Could not move clear of the nest!'
    sys.exit(1)

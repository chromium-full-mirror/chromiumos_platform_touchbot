#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
import sys

import roibot

# Open the robot interface.
robot = roibot.ROIbot(sys.argv[1])

# If the robot doesn't respond in 2 seconds to a command, then something
# is wrong.
robot.timeout = 2

#
# Perform an operation on the robot
#
try:
    print roibot.error.statusReport(robot)
    line = robot.sendCommand("SYSP")
    print line

    if not robot.modeHostON():
        print "Failed to set host mode"
    else:
        print "Host mode enabled"
except roibot.roibot.ROIbotTimeoutException:
    print "timed out!"

robot.timeout = None
robot.close()

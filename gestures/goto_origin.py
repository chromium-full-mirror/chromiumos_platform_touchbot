#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Reset the robot and return the finger to the origin
#
import sys
import time

import roibot

# Open the robot interface.
# robot = roibot.ROIbot(sys.argv[1])
robot = roibot.ROIbot(port='/dev/ttyUSB0',
                      baudrate=9600,
                      bytesize=8,
                      parity='E',
                      stopbits=1,
                      rtscts=0)

# If the robot doesn't respond in 2 seconds to a command, then something
# is wrong.
robot.timeout = 2

#
# Perform an operation on the robot
#
try:
    # Clear outstanding error conditions (if any).
    #
    # This will clean up any bad outstanding state that exists from:
    #
    #   o   line noise from a previous connection
    #   o   resulting from the robot responding to flow control events
    #       occuring during initialization of the serial port:
    #       o   DTR off->on
    #       o   CTS/RTS
    #       o   etc.
    #
    print "COMMAND: Clear error status"
    robot.assertCancelError()
    print "COMMAND: Current status..."
    for statusElement in roibot.error.statusReport(robot):
        print "    ", statusElement
    print "COMMAND: Reset"
    robot.assertReset()

    print "COMMAND: Enable host mode"
    if robot.modeHostON():
        print "Host mode enabled"
    else:
        print "Failed to set host mode"

    print "COMMAND: Servo ON"
    if not robot.execServoON():
        print "Servo failed"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    print "COMMAND: Reset"
    if robot.execReset():
        print "Robot reset."
    else:
        print "Reset failed, retrying..."
        if robot.execReset():
            print "Robot reset."
        else:
            print "Fatal: Reset failed."
            exit(1)

    print "EXPECTED"
    print "['Return to origin complete', 'Positioning complete']"
    print "['Sequential mode', 'Automatic mode', 'Host computer ON']"
    print "['Servo ON', 'Reserved SNO=3 bit 0x02', 'Slave not ready']"
    print "[]"


    #
    # A simple motion program...
    #
    print "COMMAND: Return to origin"
    if not robot.execReturnToOrigin():
        print "origin reset failed"

    # Wait for completion
    roibot.motion.waitForExecution(robot)

    print "Return to origin complete."

    print "COMMAND: Current status..."
    for statusElement in roibot.error.statusReport(robot):
        print "    ", statusElement


except roibot.roibot.ROIbotTimeoutException:
    # timeouts - usually communications or stuck servo related
    print "timed out!"
except:
    # all other errors
    for statusElement in roibot.error.statusReport(robot):
        print "    ", statusElement

robot.timeout = None
robot.close()

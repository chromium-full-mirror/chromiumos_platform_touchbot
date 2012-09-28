#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
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
    # The operation is performed twice in case the output buffer is not
    # clear; technically, we should be able to just send a CR/Lf then the
    # command (TODO: Test this theory)
    #
    print "COMMAND: Clear error status"
    if robot.execCancelError():
        print "clean state"
    else:
        print "failed to clear state"
        if robot.execCancelError():
            print "clean state"
        else:
            sys.exit("failed to clear state")

    print "COMMAND: Current status..."
    for statusElement in roibot.error.statusReport(robot):
        print "    ", statusElement

    # print roibot.error.statusReport(robot)
    # line = robot.sendCommand("SYSP")
    # print line

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


    #
    # A simple motion program...
    #
    print "COMMAND: Return to origin"
    if not robot.execReturnToOrigin():
        sys.exit("origin reset failed")

    # Wait for completion
    roibot.motion.waitForExecution(robot)

    # Show inaccuracy in settle at origin... :(
    print "This is not precise unless we wait for it to settle..."
    print robot.sendCommand("STAS", "SNO=0")
    print robot.monRequestPresentPosition()

    print robot.sendCommand("STAS", "SNO=0")
    print robot.monRequestPresentPosition()

    print robot.sendCommand("STAS", "SNO=0")
    print robot.monRequestPresentPosition()

    # move at high speed to X=+0200.00
    roibot.motion.moveOneAxis(robot, "+0200.00", "SP", "SP", "SP")
    # back up to X=+0150.00
    roibot.motion.moveOneAxis(robot, "+0150.00", "SP", "SP", "SP")
    # continue at low speed to X=+243.46
    # TODO: There is no in-band parameter support for selection of low
    #       speed at this time, so this operation actually occurs at
    #       normal (high) speed.
    roibot.motion.moveOneAxis(robot, "+0243.46", "SP", "SP", "SP")
    # continue at high speed to Y=+0050.00
    roibot.motion.moveOneAxis(robot, "SP", "+0050.00", "SP", "SP")

    # announce our arrival at our destination
    print robot.monRequestPresentPosition()

except roibot.roibot.ROIbotTimeoutException:
    # timeouts - usually communications or stuck servo related
    print "timed out!"
except:
    # all other errors
    for statusElement in roibot.error.statusReport(robot):
        print "    ", statusElement

robot.timeout = None
robot.close()

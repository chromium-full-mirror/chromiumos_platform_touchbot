#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Variable speed flick or scroll for multiple touch devices.
#
import sys
import time
import pickle

import roibot

#
# Configuration parameters below.
#
# The 'device' can be one of:   macbook_air_11    11" MacBook Air
#                               lumpy             The lumpy Chromebook
#
# The 'flick_speed' can be an integer number between 1 and 10.  I recommend
# against picking 10.
#
# The 'scroll' can be one of:   "POST"            This is a scroll
#                               "PASS"            This is a flick
#
# A 'flick' picks up the robot finger(s) toward the end of a horizontal
# motion while the motion is still in progress in order to test coasting
# or momentum.
#
# A 'scroll' does not pick up the finger(s) until horizontal motion has
# been completed, and picks them up solely in the Z axis.
#
# A scroll assumes a two finger robot configuration for most devices.
#
device = "macbook_air_11"
flick_speed = 5
scroll="PASS"


#
# Open the bounding volume pickle file and read the bounding volume out;
# We manually collected this information using the 'point_picker.py'
# program and then pickled them by hand.
#
# [0][0]  Minimum X for touch area
# [0][1]  Maximum X for touch area
# [1][0]  Minimum Y for touch area
# [1][1]  Maximum Y for touch area
# [2][0]  Paper touch for Z (paper won't fit between device and finger)
# [2][1]  Explicit click for Z (button depressed by finger)
#
def get_bounding_volume(name):
    bv_path = "../devices/" + name + ".pp"
    bv_file = open(bv_path, "r")
    bv = pickle.load(bv_file)
    bv_file.close()
    return bv


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

trackpad = get_bounding_volume(device)


#
# Program the robot and run the program; the program consists of two flicks
# with lift-off at the bottom of the flick.
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

    print "COMMAND: Sequential mode"
    if not robot.modeSequential():
        print "Sequential mode failed"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    print "COMMAND: Program mode"
    if not robot.modeProgram():
        print "Program mode failed"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    if not robot.textWriteSequential("0001", "SPD",
                                     "V=%02d" % int(flick_speed)):
        print "Failed step 1"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    if not robot.textWriteSequential("0002", "MOVP", "a", "PT=001",
                                     "CN=00", "S", "V=00", "POST"):
        print "Failed step 2"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    if not robot.textWriteSequential("0003", "MOVP", "a", "PT=002",
                                     "CN=00", "S", "V=00", "POST"):
        print "Failed step 3"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    if not robot.textWriteSequential("0004", "MOVP", "a", "PT=003",
                                     "CN=00", "S", "V=00", scroll):
        print "Failed step 4"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    if not robot.textWriteSequential("0005", "MOVP", "a", "PT=004",
                                     "CN=00", "S", "V=00", "POST"):
        print "Failed step 5"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    if not robot.textWriteSequential("0006", "MOVP", "a PT=002",
                                     "CN=00", "S", "V=00", "POST"):
        print "Failed step 6"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    if not robot.textWriteSequential("0007", "MOVP", "a", "PT=003",
                                     "CN=00", "S", "V=00", scroll):
        print "Failed step 7"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    if not robot.textWriteSequential("0008", "MOVP", "a", "PT=004",
                                     "CN=00", "S", "V=00", "POST"):
        print "Failed step 8"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    if not robot.textWriteSequential("0009", "END"):
        print "Failed step 9"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    # Calculate parameters relative to the bounding region
    trackpad_half_width = (trackpad[1][1] - trackpad[1][0]) / 2
    trackpad_center_y = trackpad[1][0] + trackpad_half_width
    trackpad_bottom_x = trackpad[0][0]
    trackpad_top_x = trackpad[0][1]
    trackpad_touch_z = trackpad[2][0]
    trackpad_raised_z = trackpad_touch_z - 5

    if not robot.parameterWrite("T1", "PT=001",
                                "X=+%07.02f" % trackpad_top_x,
                                "Y=+%07.02f" % trackpad_center_y,
                                "Z=+%07.02f" % trackpad_raised_z,
                                "R=+0000.00"):
        print "Failed point 1"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    if not robot.parameterWrite("T1", "PT=002",
                                "X=+%07.02f" % trackpad_top_x,
                                "Y=+%07.02f" % trackpad_center_y,
                                "Z=+%07.02f" % trackpad_touch_z,
                                "R=+0000.00"):
        print "Failed point 2"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    if not robot.parameterWrite("T1", "PT=003",
                                "X=+%07.02f" % trackpad_bottom_x,
                                "Y=+%07.02f" % trackpad_center_y,
                                "Z=+%07.02f" % trackpad_touch_z,
                                "R=+0000.00"):
        print "Failed point 3"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    if not robot.parameterWrite("T1", "PT=004",
                                "X=+%07.02f" % trackpad_bottom_x,
                                "Y=+%07.02f" % trackpad_center_y,
                                "Z=+%07.02f" % (trackpad_touch_z - 10),
                                "R=+0000.00"):
        print "Failed point 3"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    if not robot.modeAutomatic():
        print "Failed Automatic"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    if not robot.modeAutomatic():
        print "Failed Automatic"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    print "COMMAND: Return to origin"
    if not robot.execReturnToOrigin():
        print "origin reset failed"

    # Wait for completion
    roibot.motion.waitForExecution(robot)

    if not robot.execStartSequential(1):
        print "Failed Sequential"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement

    time.sleep(1)

    # announce our arrival at our destination
    print robot.monRequestPresentPosition()

except roibot.roibot.ROIbotTimeoutException:
    # timeouts - usually communications or stuck servo related
    print "timed out!"
#except:
    # all other errors
    for statusElement in roibot.error.statusReport(robot):
        print "    ", statusElement

robot.timeout = None
robot.close()

#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# EEPROM programming wrapper.  The run_prog() function can be used externally
# to load a program into eeprom or this script can be run on its own to run
# whatever program is currently stored there.  This allows us to cut down on
# the number of read/write cycles to the eeprom as well as makes the code for
# gestures much nicer.
#
import roibot


def run_program(program=None, *args, **kwargs):
    # Open the robot interface.
    robot = roibot.ROIbot(port='/dev/ttyUSB0',
                          baudrate=9600,
                          bytesize=8,
                          parity='E',
                          stopbits=1,
                          rtscts=0)
    robot.timeout = 2

    try:
        # Clear any pending errors and reset the robot
        robot.tryOrFail(robot.execCancelError)
        robot.tryOrFail(robot.execReset)

        # Switch to sequential programming mode (load a program to eeprom)
        robot.tryOrFail(robot.modeHostON)
        robot.tryOrFail(robot.execServoON)
        robot.tryOrFail(robot.modeSequential)
        robot.tryOrFail(robot.modeProgram)

        # If we have a new program to load onto the robot
        if program != None:
            program(robot, *args, **kwargs)

        # Switch the program mode to auto (run the program in eeprom)
        robot.tryOrFail(robot.modeAutomatic)

        # Go back to the origin so it starts from a known location
        robot.tryOrFail(robot.execReturnToOrigin)
        roibot.motion.waitForExecution(robot)

        # Start eeprom program 1
        robot.tryOrFail(robot.execStartSequential, 1)
        print "Execution started."

    except Exception as e:
        print "Exception Caught"
        print "Error(" + str(e) + ")"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement
        raise
    finally:
        robot.timeout = None
        robot.close()

if __name__=="__main__":
    run_program()

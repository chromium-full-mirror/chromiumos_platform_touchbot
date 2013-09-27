# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""EEPROM programming wrapper.  The run_prog() function can be used externally
to load a program into eeprom or this script can be run on its own to run
whatever program is currently stored there.  This allows us to cut down on
the number of read/write cycles to the eeprom as well as makes the code for
gestures much nicer.
"""

import glob
import time

import roibot


MAX_TRIES = 3
RETRY_DELAY_S = 5

def scan_serial_ports():
    ports = glob.glob('/dev/ttyUSB*')

    for port in ports:
        print 'Trying port: %s' % port
        try:
            robot = roibot.ROIbot(port=port,
                                  baudrate=9600,
                                  bytesize=8,
                                  parity='E',
                                  stopbits=1,
                                  rtscts=0)
            robot.timeout = 2
            robot.tryOrFail(robot.modeRequestRobotType)
            print '\tRobot detected'
            return port
        except:
            print '\tNo robot found'

    return None

def run_program(program=None, device=None, *args, **kwargs):
    tries = 0
    while tries < MAX_TRIES:
        if attempt_to_run_program(program, device, *args, **kwargs):
            return True
        tries += 1
        time.sleep(RETRY_DELAY_S)

    return False

def attempt_to_run_program(program=None, device=None, *args, **kwargs):
    # Detect which serial port the robot is listening on
    robot_port = scan_serial_ports()
    if robot_port is None:
       print 'No robot found, please ensure that it is connected'
       return False

    # Open the robot interface.
    robot = roibot.ROIbot(port=robot_port,
                          baudrate=9600,
                          bytesize=8,
                          parity='E',
                          stopbits=1,
                          rtscts=0)
    robot.timeout = 2

    ret_val = False
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
            if device == None:
                print 'You must specify a device to load a new program'
                return
            bounds = roibot.BoundingVolume(device)
            program(robot, bounds, *args, **kwargs)
            robot.addCmd('END')

        # Switch the program mode to auto (run the program in eeprom)
        robot.tryOrFail(robot.modeAutomatic)

        # Go back to the origin so it starts from a known location
        robot.tryOrFail(robot.execReturnToOrigin)
        roibot.motion.waitForExecution(robot)

        # Start eeprom program 1
        robot.tryOrFail(robot.execStartSequential, 1)
        print 'Execution started'

        # Block until the program has finished
        roibot.motion.waitForExecution(robot)
        print 'Execution completed'
        ret_val = True
    except Exception as e:
        print 'Exception Caught'
        print 'Error(' + str(e) + ')'
        print
        print 'Current robot status:'
        for statusElement in roibot.error.statusReport(robot):
            print statusElement
    finally:
        robot.timeout = None
        robot.close()
        return ret_val

if __name__== '__main__':
    run_program()

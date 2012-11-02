# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Press a key on the laptop.
If that key is not defined in the device spec, then nothing will happen.

Usage: ./press_key device KEY_TO_PRESS
   eg: ./press_key butterfly k
"""

import sys

import roibot
import run_program


def program(robot, bounds, *args, **kwargs):
    """Upload a new program to the robot.  This program moves the finger
    to a key somewhere on the DUT and presses it.

    Arguments:
    args[0] = The key to press
    """

    PRESS_SPEED = 200
    CLEARANCE_Z = 20

    # Find the coordinates of the key (if it exists)
    key = args[0]
    key_coordinates = bounds.keyCoordinates(key)
    if not key_coordinates:
        print 'ERROR: key "%s" not defined for this device!' % args[0]
        robot.addCmd("END")
        return
    key_x, key_y, key_z = key_coordinates

    # Get into position
    robot.addMoveCommand(key_x, key_y, key_z - CLEARANCE_Z, PRESS_SPEED)
    robot.addMoveCommand(key_x, key_y, key_z, PRESS_SPEED, accuracy="PASS")
    robot.addMoveCommand(key_x, key_y, key_z - CLEARANCE_Z, PRESS_SPEED)

    # End the program nicely
    robot.addCmd("END")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print "Usage: ./press_key device_name key_name"
    else:
        device = sys.argv[1]
        key_name = sys.argv[2]
        run_program.run_program(program, device, key_name)

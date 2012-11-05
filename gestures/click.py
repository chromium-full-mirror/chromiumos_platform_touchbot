# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Perform a click or tap action at the specified location.

Usage: ./click device TARGET_X TARGET_Y [tap|click]
   eg: ./click snow 0.5 0.5 tap
"""

import sys

import roibot
import run_program


def program(robot, bounds, *args, **kwargs):
    """Upload a new program to the robot.  This program moves the finger
    to a specified point then either clicks or taps there.
    """

    # Setup speed book-keeping for the robot
    TAP_SPEED = 600
    TAP_TABLE = 1
    CLICK_SPEED = 100
    CLICK_TABLE = 2
    SETUP_SPEED = 60
    SETUP_TABLE = 3

    # Convert the coordinates into the robot's view.
    target_x, target_y = bounds.convert(float(args[0]), float(args[1]))

    # Set up the speed tables
    robot.setParam("T2 V%02d=%06.01f" % (TAP_TABLE, TAP_SPEED))
    robot.setParam("T2 V%02d=%06.01f" % (CLICK_TABLE, CLICK_SPEED))
    robot.setParam("T2 V%02d=%06.01f" % (SETUP_TABLE, SETUP_SPEED))

    # Get into position
    robot.addCmd("SPD V=%02d" % SETUP_TABLE)

    pt = robot.addPoint(target_x, target_y, bounds.upZ())
    robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

    # Perform the click action
    if args[2].lower() == "tap":
        robot.addCmd("SPD V=%02d" % TAP_TABLE)
        # To achieve a fluid "tap" set the movement as PASS and overshoot
        pt = robot.addPoint(target_x, target_y, bounds.tapZ())
        robot.addCmd("MOVP a PT=%03d CN=00 S V=00 PASS" % pt)
    else:
        robot.addCmd("SPD V=%02d" % CLICK_TABLE)
        # To achieve a deliberate "click" set movement to POST and move slowly
        pt = robot.addPoint(target_x, target_y, bounds.clickZ())
        robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

    pt = robot.addPoint(target_x, target_y, bounds.upZ())
    robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print "Usage: ./click device_name target_x target_y [tap|click]"
    else:
        device = sys.argv[1]
        target_x = float(sys.argv[2])
        target_y = float(sys.argv[3])
        click_type = sys.argv[4].lower()
        if click_type != "click" and click_type != "tap":
            print 'Illegal click type: "%s".' % click_type
            print 'Options are: "tap" and "click"'
        else:
            run_program.run_program(program, device, target_x, target_y,
                                    click_type)

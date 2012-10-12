# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Move the finger in a straight line between two points at a specified
speed in mm/s.  The point coordinates are given in the range of 0.0
through 1.0 indicating a percentage of the way long that axis, so the
gesture can be generalized across multiple devices.

The line is specified from the touchpad's point of view.
Refer to the diagram of the touchpad below to specify your lines.
     ____________
    |1          2|
    |  touchpad  |
    |            |
    |3__________4|

    1: (0.0, 0.0)
    2: (1.0, 0.0)
    3: (0.0, 1.0)
    4: (1.0, 1.0)

Usage: ./line START_X START_Y END_X END_Y SPEED_IN_MM_PER_S
   eg: ./line 0.1 0.1 0.9 0.9 15.0
"""

import sys

import roibot
import run_program


def program(robot, bounds, *args, **kwargs):
    """Upload a new program to the robot.  This program moves the finger
    in a given straight line as a specified speed in mm/s.
    """

    # Setup speed book-keeping for the robot
    STROKE_TABLE = 1
    SETUP_SPEED = 60
    SETUP_TABLE = 2

    # Compute the endpoints of the stroke from the robots point of view
    # noting that the robot is rotated 90 degrees from the touchpad.
    range_y = bounds.maxY() - bounds.minY()
    range_x = bounds.maxX() - bounds.minX()
    start_x = bounds.maxX() - float(args[1]) * range_x
    start_y = bounds.maxY() - float(args[0]) * range_y
    end_x = bounds.maxX() - float(args[3]) * range_x
    end_y = bounds.maxY() - float(args[2]) * range_y
    speed = float(args[4])

    # Set up the speed tables
    robot.setParam("T2 V%02d=%06.01f" % (STROKE_TABLE, speed))
    robot.setParam("T2 V%02d=%06.01f" % (SETUP_TABLE, SETUP_SPEED))

    # Get into position
    robot.addCmd("SPD V=%02d" % SETUP_TABLE)

    pt = robot.addPoint(start_x, start_y, bounds.upZ())
    robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

    pt = robot.addPoint(start_x, start_y, bounds.paperZ())
    robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

    # Preform the stroke
    robot.addCmd("SPD V=%02d" % STROKE_TABLE)

    pt = robot.addPoint(end_x, end_y, bounds.paperZ())
    robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

    # Lift up to get the laptop out
    robot.addCmd("SPD V=%02d" % SETUP_TABLE)

    pt = robot.addPoint(end_x, end_y, bounds.upZ())
    robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

    # End the program nicely
    robot.addCmd("END")


if __name__=="__main__":
    if len(sys.argv) != 7:
        print "Usage: ./line device_name start_x start_y end_x end_y speed_mm/s"
    else:
        device = sys.argv[1]
        start_x = float(sys.argv[2])
        start_y = float(sys.argv[3])
        end_x = float(sys.argv[4])
        end_y = float(sys.argv[5])
        speed = float(sys.argv[6])
        run_program.run_program(program, device, start_x, start_y, end_x,
                                end_y, speed)

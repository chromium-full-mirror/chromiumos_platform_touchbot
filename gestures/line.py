# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Move the finger in a straight line between two points at a specified
speed in mm/s.  Optionally preform a "swipe" along this line where it lifts
up fluidly at the end instead of just stopping.

Usage: ./line DEVICE START_X START_Y END_X END_Y SPEED_IN_MM_PER_S [swipe|basic]
   eg: ./line snow 0.1 0.1 0.9 0.9 15.0 basic
   eg: ./line snow 0.5 0.0 0.5 0.9 15.0 swipe
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
    start_x, start_y = bounds.convert(float(args[0]), float(args[1]))
    end_x, end_y = bounds.convert(float(args[2]), float(args[3]))
    speed = float(args[4])
    line_type = args[5].lower()

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
    if line_type  == "basic":
        # Stay on the touchpad for the duration of the line
        pt = robot.addPoint(end_x, end_y, bounds.paperZ())
        robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

        # Lift up only once the whole line is done
        pt = robot.addPoint(end_x, end_y, bounds.upZ())
        robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)
    else:
        # Gradually lower onto the surface over the first 1/4 of the line
        touchdown_x = (3.0 * start_x + end_x) / 4.0
        touchdown_y = (3.0 * start_y + end_y) / 4.0
        pt = robot.addPoint(touchdown_x, touchdown_y, bounds.paperZ())
        robot.addCmd("MOVP a PT=%03d CN=00 S V=00 PASS" % pt)

        # Stay on the touchpad for 3/4 of the distance
        mid_x = (start_x + 3.0 * end_x) / 4.0
        mid_y = (start_y + 3.0 * end_y) / 4.0
        pt = robot.addPoint(mid_x, mid_y, bounds.paperZ())
        robot.addCmd("MOVP a PT=%03d CN=00 S V=00 PASS" % pt)

        # Then lift up gradually for the remaining 1/4
        pt = robot.addPoint(end_x, end_y, bounds.upZ())
        robot.addCmd("MOVP a PT=%03d CN=00 S V=00 PASS" % pt)

    # End the program nicely
    robot.addCmd("END")


if __name__=="__main__":
    if len(sys.argv) != 8:
        print "Usage: ./line device_name " \
              "start_x start_y end_x end_y speed_mm/s [swipe|basic]"
    else:
        device = sys.argv[1]
        start_x = float(sys.argv[2])
        start_y = float(sys.argv[3])
        end_x = float(sys.argv[4])
        end_y = float(sys.argv[5])
        speed = float(sys.argv[6])
        line_type = sys.argv[7].lower()

        run_program.run_program(program, device, start_x, start_y, end_x,
                                end_y, speed, line_type)

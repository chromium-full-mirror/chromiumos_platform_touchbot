# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Move the finger in a straight line between two points at a specified
speed in mm/s.  Optionally preform a "swipe" along this line where it lowers
down up gradually instead of tracing the points, or do a "fling" where the
robot begins normally but quickly jerks up at the end to simulate a user
flinging a web page.

Usage: ./line DEVICE START_X START_Y END_X END_Y
              SPEED_IN_MM_PER_S [basic|swipe|fling]
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

    # Compute the endpoints of the stroke from the robots point of view
    start_x, start_y = bounds.convert(float(args[0]), float(args[1]))
    end_x, end_y = bounds.convert(float(args[2]), float(args[3]))
    line_speed = float(args[4])
    line_type = args[5].lower()

    # Get into position
    SETUP_SPEED = 60
    robot.addMoveCommand(start_x, start_y, bounds.upZ(), SETUP_SPEED)

    # Preform the stroke
    if line_type  == "basic":
        # Touch down and stay on the touchpad for the duration of the line
        robot.addMoveCommand(start_x, start_y, bounds.paperZ(), SETUP_SPEED)
        robot.addMoveCommand(end_x, end_y, bounds.paperZ(), line_speed)

        # Lift up only once the whole line is done
        robot.addMoveCommand(end_x, end_y, bounds.upZ(), SETUP_SPEED)
    elif line_type = "swipe":
        # Gradually lower onto the surface over the first 1/4 of the line
        touchdown_x = (3.0 * start_x + end_x) / 4.0
        touchdown_y = (3.0 * start_y + end_y) / 4.0
        robot.addMoveCommand(touchdown_x, touchdown_y, bounds.paperZ(),
                             line_speed, accuracy="PASS")

        # Stay on the touchpad for 3/4 of the distance
        liftup_x = (start_x + 3.0 * end_x) / 4.0
        liftup_y = (start_y + 3.0 * end_y) / 4.0
        robot.addMoveCommand(liftup_x, liftup_y, bounds.paperZ(), line_speed,
                             accuracy="PASS")

        # Then lift up gradually for the remaining 1/4
        robot.addMoveCommand(end_x, end_y, bounds.upZ(), line_speed)
    elif line_type = "fling":
        # Touch down and stay on the touchpad for most of the line
        robot.addMoveCommand(start_x, start_y, bounds.paperZ(), SETUP_SPEED)

        # Stay on the touchpad for 5/6 of the distance
        liftup_x = (start_x + 5.0 * end_x) / 6.0
        liftup_y = (start_y + 5.0 * end_y) / 6.0
        robot.addMoveCommand(
            liftup_x, liftup_y, bounds.paperZ(), line_speed, accuracy="PASS")

        # Then lift up gradually for the remaining 1/6
        robot.addMoveCommand(end_x, end_y, bounds.upZ(), line_speed)


if __name__=="__main__":
    if len(sys.argv) != 8:
        print "Usage: ./line device_name " \
              "start_x start_y end_x end_y speed_mm/s [basic|swipe|fling]"
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

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Traverse the boundary of a touchpad.  Useful for determining if the values
are good/safe and tweaking them or simply as a basic example to start with.
"""

import sys

import roibot
import run_program


def program(robot, bounds):
    """Upload a new program to the robot.  This program moves the finger along
    the border of the touchpad.
    """

    SPEED_SLOW = 30
    SPEED_TABLE_SLOW = 1
    SPEED_FAST = 60
    SPEED_TABLE_FAST = 2
    STEPS = 10
    TOUCH_Z = bounds.paperZ()
    UP_Z = TOUCH_Z - 15

    # Set up the speed tables
    robot.setParam("T2 V%02d=%06.01f" % (SPEED_TABLE_SLOW, SPEED_SLOW))
    robot.setParam("T2 V%02d=%06.01f" % (SPEED_TABLE_FAST, SPEED_FAST))

    # Get into position
    robot.addCmd("SPD V=%02d" % SPEED_TABLE_FAST)

    pt = robot.addPoint(bounds.minX(), bounds.minY(), bounds.upZ())
    robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

    pt1 = robot.addPoint(bounds.minX(), bounds.minY(), bounds.paperZ())
    robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt1)

    # Go around the border
    robot.addCmd("SPD V=%02d" % SPEED_TABLE_SLOW)

    pt = robot.addPoint(bounds.maxX(), bounds.minY(), bounds.paperZ())
    robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

    pt = robot.addPoint(bounds.maxX(), bounds.maxY(), bounds.paperZ())
    robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

    pt = robot.addPoint(bounds.minX(), bounds.maxY(), bounds.paperZ())
    robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

    robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt1)

    # Lift up, now that it's done
    pt = robot.addPoint(bounds.minX(), bounds.minY(), bounds.upZ())
    robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

    # End the program nicely
    robot.addCmd("END")

if __name__=="__main__":
    if len(sys.argv) != 2:
        print "Usage: ./basic device_name"
    else:
        device = sys.argv[1]
        run_program.run_program(program, device)

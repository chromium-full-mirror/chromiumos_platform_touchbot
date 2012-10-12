# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script makes the robot do a "scroll" function on the touchpad
by placing two fingers near the top of the touchpad, moving down at a
specified speed, and optionally lifting off smoothly to create a "fling"
on stopping to leave it as a scroll.

Usage:
    ./scroll device          Does a "scroll" gesture
    ./scroll device fling    Does a "fling" gesture

This requires the second finger to be in the down position to work!
"""


import sys

import roibot
import run_program


def program(robot, bounds, *arg, **kwargs):
    """Upload a new program to the robot.
    This program does a single scroll action (Possibly with fling)
    """

    # Define the parameters of the gesture (speeds are in mm/s)
    SCROLL_SPEED = 30
    SCROLL_SPEED_TABLE = 1
    SETUP_SPEED = 60
    SETUP_SPEED_TABLE = 2
    BUFFER_PERC = 0.10      # Percent of touchpad near the edge to avoid
    PAUSE_TIME = 1.5        # How long to pause before lifting (seconds)

    # Compute where the finger should be for this device
    # Note: The touchpad has to sit sideways on the robot, so y->x
    scrollY = ((bounds.maxY() - bounds.minY()) / 2.0) + bounds.minY()
    bufferX = (bounds.maxX() - bounds.minX()) * BUFFER_PERC
    startX = bounds.maxX() - bufferX
    endX = bounds.minX() + bufferX
    midX = (startX + endX) / 2.0

    print "Begin Programming"
    # Set up the speed tables
    robot.setParam("T2 V%02d=%06.01f" % (SCROLL_SPEED_TABLE, SCROLL_SPEED))
    robot.setParam("T2 V%02d=%06.01f" % (SETUP_SPEED_TABLE, SETUP_SPEED))

    # Get into position
    robot.addCmd("SPD V=%02d" % SETUP_SPEED_TABLE)

    pt = robot.addPoint(startX, scrollY, bounds.upZ())
    robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

    pt = robot.addPoint(startX, scrollY, bounds.paperZ())
    robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

    # Change speeds and do the scroll action
    robot.addCmd("SPD V=%02d" % SCROLL_SPEED_TABLE)

    if kwargs['fling'] == True:
        pt = robot.addPoint(midX, scrollY, bounds.paperZ())
        robot.addCmd("MOVP a PT=%03d CN=00 S V=00 PASS" % pt)

        # Start to lift up off (to make it fling)
        pt = robot.addPoint(endX, scrollY, bounds.paperZ() - 1)
        robot.addCmd("MOVP a PT=%03d CN=00 S V=00 PASS" % pt)

        pt = robot.addPoint(endX, scrollY, bounds.upZ())
        robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)
    else:
        pt = robot.addPoint(endX, scrollY, bounds.paperZ())
        robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

        # Pause after completing the scroll
        robot.addCmd("TIM TM=%05.1f" % PAUSE_TIME)

        # Lift up
        pt = robot.addPoint(endX, scrollY, bounds.upZ())
        robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)

    # End the program nicely
    robot.addCmd("END")

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[2].lower() == "fling":
        run_program.run_program(program, sys.argv[1], fling=True)
    elif len(sys.argv) == 2:
        run_program.run_program(program, sys.argv[1], fling=False)
    else:
        print "Usage: ./scroll device_name [fling]"

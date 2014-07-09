# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Upload a program to the robot that moves the finger to a series of
points forming a grid over the touch surface.  At each point on the grid
it places the finger down, holds it still for a specified amount of time,
then lifts off before moving to the next point.

This can be used to map the signal-to-noise ration of a touch sensor since
each of the points should theoretically be a constant x and y value.

There are two parameters you can specify.  How many divisions it makes when
picking points, and how many seconds to hold its finger still at each point.

Usage: ./snr_sampler.py device x_divisions y_divisions hold_time
   eg: To run on link, doing a 6x4 grid and holding for 15 seconds
       ./snr_sampler.py link 6 4 15
"""


import numpy as np
import itertools
import sys

import roibot
import run_program


def program(robot, bounds, *args, **kwargs):

    # Setup speed book-keeping for the robot
    TOUCH_SPEED = 50
    SETUP_SPEED = 200

    # Load the customized arguments
    x_divisions = args[0]
    y_divisions = args[1]
    hold_time = args[2]

    # Convert the coordinates into the robot's view.
    check_points = itertools.product(np.linspace(0, 1, num=x_divisions),
                                     np.linspace(0, 1, num=y_divisions))
    targets = [bounds.convert(x, y) for x, y in check_points]

    for target_x, target_y in targets:
        # Get into position
        robot.addMoveCommand(target_x, target_y, bounds.upZ(), SETUP_SPEED)

        # Touch down
        robot.addMoveCommand(target_x, target_y, bounds.clickZ(), TOUCH_SPEED)

        # Wait, but don't move the finger, to allow noise to happen
        robot.addCmd(roibot.program.sleepInterval(hold_time))

        # Lift up
        robot.addMoveCommand(target_x, target_y, bounds.upZ(), TOUCH_SPEED)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print ("Usage: ./snr_sampler device_name x_divisions "
               "y_divisions hold_time")
    else:
        device = sys.argv[1]
        x_divisions = int(sys.argv[2])
        y_divisions = int(sys.argv[3])
        hold_time = int(sys.argv[4])

        run_program.run_program(program, device, x_divisions,
                                y_divisions, hold_time)

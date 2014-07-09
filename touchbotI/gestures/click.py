# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Perform a click or tap action at the specified location.

Usage: ./click device TARGET_X TARGET_Y [TARGET2_X TARGET2_Y ...] [tap|click]
   eg: ./click snow 0.5 0.5 tap
   eg: ./click snow 0.5 0.5 0.1 0.9 0.2 0.44 click
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
    CLICK_SPEED = 100
    SETUP_SPEED = 60

    # Convert the coordinates into the robot's view.
    targets = [bounds.convert(x, y) for x, y in args[0]]
    click_type = args[1].lower()

    for target_x, target_y in targets:
        # Get into position
        robot.addMoveCommand(target_x, target_y, bounds.upZ(), SETUP_SPEED)

        # Perform the click action
        if click_type == "tap":
            # To achieve a fluid "tap" set the movement as PASS and overshoot
            robot.addMoveCommand(target_x, target_y, bounds.tapZ(), TAP_SPEED,
                                 accuracy="PASS")
            robot.addMoveCommand(target_x, target_y, bounds.upZ(), TAP_SPEED)
        else:
            robot.addMoveCommand(target_x, target_y, bounds.clickZ(),
                                 CLICK_SPEED)
            robot.addMoveCommand(target_x, target_y, bounds.upZ(), CLICK_SPEED)


if __name__ == "__main__":
    if len(sys.argv) < 5 or len(sys.argv) % 2 == 0:
        print "Usage: ./click device_name target_x target_y " \
              "[target2_x target2_y ...] [tap|click]"
    else:
        device = sys.argv[1]
        targets = []
        for i in range(2, len(sys.argv) - 1, 2):
            target_x = float(sys.argv[i])
            target_y = float(sys.argv[i + 1])
            targets.append((target_x, target_y))
        click_type = sys.argv[-1].lower()
        if click_type != "click" and click_type != "tap":
            print 'Illegal click type: "%s".' % click_type
            print 'Options are: "tap" and "click"'
        else:
            run_program.run_program(program, device, targets, click_type)

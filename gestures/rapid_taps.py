# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Perform a series of rapid-fire taps in one place

Usage: ./rapid_taps.py device TARGET_X TARGET_Y NUMBER_OF_TAPS
   eg: ./rapid_taps.py snow 0.5 0.5 20
"""

import sys

import roibot
import run_program


def program(robot, bounds, *args, **kwargs):
    """Upload a new program to the robot.  This program moves the finger
    to a specified point then taps repeatedly in quick succession.
    """

    # Setup speed book-keeping for the robot
    TAP_SPEED = 600
    SETUP_SPEED = 60
    TAP_LOOP_COUNTER = 1
    TAP_LOOP_START = 2
    TAP_LOOP_END = 3

    # Get the user's commands
    x, y = bounds.convert(args[0], args[1])
    num_taps = args[2]

    # Get into position
    robot.addMoveCommand(x, y, bounds.upZ(), SETUP_SPEED)

    # Start a loop to click num_taps times
    robot.addCmd(roibot.program.setCounter(TAP_LOOP_COUNTER, 0))
    robot.addCmd(roibot.program.setTag(TAP_LOOP_START))

    # Perform the click action
    # To achieve a fluid "tap" set the movement as PASS and overshoot
    robot.addMoveCommand(x, y, bounds.tapZ(), TAP_SPEED, accuracy="PASS")
    robot.addMoveCommand(x, y, bounds.upZ(), TAP_SPEED, accuracy="PASS")

    # Increment counter, if it's num_taps then you jump out of the loop
    robot.addCmd(roibot.program.incrementCounter(TAP_LOOP_COUNTER, 1))
    jmp_cmd = roibot.program.jumpCounterConditional(
                                 TAP_LOOP_END, TAP_LOOP_COUNTER, '=', num_taps)
    robot.addCmd(jmp_cmd)

    # Otherwise jump back to the start
    robot.addCmd(roibot.program.jump(TAP_LOOP_START))

    robot.addCmd(roibot.program.setTag(TAP_LOOP_END))


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print "Usage: " + sys.argv[0] + " device_name tap_x tap_y num_taps"
    else:
        device = sys.argv[1]
        x = float(sys.argv[2])
        y = float(sys.argv[3])
        num_taps = int(sys.argv[4])
        run_program.run_program(program, device, x, y, num_taps)

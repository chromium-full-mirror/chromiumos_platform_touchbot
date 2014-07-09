# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Go and poke at the board to a constant pressure in an even grid
covering the surface.  It picks a point and descends until the limit switch
is triggered, resulting in consistent pressure across the samples.

To setup, make sure the limit switch is connected to the brown/white wire
pair, as that is the switch that is polled.
"""

import sys

import roibot
import run_program

# Book keeping for the robots internal registers
GPIO_COUNTER = 1
DESCEND_LOOP_START = 1
DESCEND_LOOP_END = 2

ROW_LOOP_COUNTER = 2
ROW_LOOP_START = 3
ROW_LOOP_END = 4

COL_LOOP_COUNTER = 3
COL_LOOP_START = 5
COL_LOOP_END = 6

RETURN_LOOP_COUNTER = 4
RETURN_LOOP_START = 7
RETURN_LOOP_END = 8

# Configuration parameters for the grid
DESCEND_STEP_SIZE = 0.1
SPEED = 60
STEP_SIZE = 4
BACKOFF_AMOUNT = -4


def descend(robot):
    """ Inch down tiny amounts until the limit switch is triggered """
    robot.addCmd(roibot.program.setTag(DESCEND_LOOP_START))

    # Move down a tiny bit
    mov_cmd = roibot.program.moveCoordinates(
                       False, 0, 0, DESCEND_STEP_SIZE, 0, True, 0, False)
    robot.addCmd(mov_cmd)

    # Copy the value of the GPIOs to the GPIO counter
    robot.addCmd(roibot.program.copyInputToCounter(0, 1, GPIO_COUNTER))

    # If the button was pressed, jump out of the loop
    jmp_cmd = roibot.program.jumpCounterConditional(
                                DESCEND_LOOP_END, GPIO_COUNTER, '=', 0b00001000)
    robot.addCmd(jmp_cmd)

    # Otherwise jump back to the start
    robot.addCmd(roibot.program.jump(DESCEND_LOOP_START))

    robot.addCmd(roibot.program.setTag(DESCEND_LOOP_END))


def probe_row(robot, bounds):
    """ probe a lot of points along a y-row of the surface """
    num_steps = int((bounds.maxY() - bounds.minY()) / STEP_SIZE)

    # Initialize loop and counter
    robot.addCmd(roibot.program.setCounter(ROW_LOOP_COUNTER, 0))
    robot.addCmd(roibot.program.setTag(ROW_LOOP_START))

    # Drop down and take a reading
    descend(robot)

    # Lift back up
    raise_cmd = roibot.program.moveCoordinates(
                         False, 0, 0, BACKOFF_AMOUNT, 0, True, 0, True)
    robot.addCmd(raise_cmd)

    # Move one step along
    mov_cmd = roibot.program.moveCoordinates(
                                    False, 0, STEP_SIZE, 0, 0, True, 0, True)
    robot.addCmd(mov_cmd)

    # Decrement counter, if it's num_steps then you jump out of the loop
    robot.addCmd(roibot.program.incrementCounter(ROW_LOOP_COUNTER, 1))

    # Otherwise jump back to the start
    jmp_cmd = roibot.program.jumpCounterConditional(
                                 ROW_LOOP_END, ROW_LOOP_COUNTER, '=', num_steps)
    robot.addCmd(jmp_cmd)
    robot.addCmd(roibot.program.jump(ROW_LOOP_START))

    robot.addCmd(roibot.program.setTag(ROW_LOOP_END))

    # Go back to the start before returning, by moving the same number of
    # steps backwards
    robot.addCmd(roibot.program.setTag(RETURN_LOOP_START))

    # Take one step backwards
    mov_cmd = roibot.program.moveCoordinates(
                       False, 0, -STEP_SIZE, 0, 0, True, 0, True)
    robot.addCmd(mov_cmd)

    # Count how many steps you have left to take.  If it's done, leave the loop
    robot.addCmd(roibot.program.decrementCounter(ROW_LOOP_COUNTER, 1))
    jmp_cmd = roibot.program.jumpCounterConditional(
                                     RETURN_LOOP_END, ROW_LOOP_COUNTER, '=', 0)
    robot.addCmd(jmp_cmd)

    # Otherwise, take another step
    robot.addCmd(roibot.program.jump(RETURN_LOOP_START))

    robot.addCmd(roibot.program.setTag(RETURN_LOOP_END))


def write_program(robot, bounds, *args, **kwargs):
    robot.addMoveCommand(bounds.minX(), bounds.minY(), bounds.upZ(), SPEED)

    num_steps = int((bounds.maxX() - bounds.minX()) / STEP_SIZE)

    # Initialize loop and counter
    robot.addCmd(roibot.program.setCounter(COL_LOOP_COUNTER, num_steps))
    robot.addCmd(roibot.program.setTag(COL_LOOP_START))

    probe_row(robot, bounds)

    # Move one step along to the next row
    mov_cmd = roibot.program.moveCoordinates(
                       False, STEP_SIZE, 0, 0, 0, True, 0, True)
    robot.addCmd(mov_cmd)

    # Decrement counter, if it's 0 then you jump out of the loop
    robot.addCmd(roibot.program.decrementCounter(COL_LOOP_COUNTER, 1))
    jmp_cmd = roibot.program.jumpCounterConditional(
                                     COL_LOOP_END, COL_LOOP_COUNTER, '=', 0)
    robot.addCmd(jmp_cmd)

    # Otherwise, go back to the beginning
    robot.addCmd(roibot.program.jump(COL_LOOP_START))

    robot.addCmd(roibot.program.setTag(COL_LOOP_END))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print 'Usage: ./pressure_map.py device_name'
    else:
        device = sys.argv[1]
        run_program.run_program(write_program, device)

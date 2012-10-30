# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Run in a diagonal criss-cross pattern over the whole touchpad to try and
expose non-linearities in the touchpad sensor
"""

import sys

import roibot
import run_program


class StrokeController:
    def __init__(self, robot, bounds, down, up, slow_table, fast_table):
        self.down = down
        self.up = up
        self.slow = slow_table
        self.fast = fast_table
        self.robot = robot
        self.midX = (bounds.minX() + bounds.maxX()) / 2.0
    def mirrorX(self, pt):
        x, y = pt
        offset = x - self.midX
        return (self.midX - offset, y)
    def set_speed(self, table):
        self.robot.addCmd("SPD V=%02d" % table)
    def add_destination(self, pt):
        self.robot.addCmd("MOVP a PT=%03d CN=00 S V=00 POST" % pt)
    def add_single_line(self, start, end):
        x1, y1 = start
        pt1_up = self.robot.addPoint(x1, y1, self.up)
        pt1_down = self.robot.addPoint(x1, y1, self.down)
        x2, y2 = end
        pt2_up = self.robot.addPoint(x2, y2, self.up)
        pt2_down = self.robot.addPoint(x2, y2, self.down)

        self.add_destination(pt1_up)
        self.add_destination(pt1_down)
        self.set_speed(self.slow)
        self.add_destination(pt2_down)
        self.set_speed(self.fast)
        self.add_destination(pt2_up)
    def add_line(self, start, end):
        """Upload a program that goes quickly to the point start, then
        slowly moves to "end" and additionally add it's mirror image
        """
        self.add_single_line(start, end)
        self.add_single_line(self.mirrorX(start), self.mirrorX(end))

def program(robot, bounds):
    """Upload a new program to the robot.
    This program moves the finger in a tight diagonal criss-cross covering
    the whole pad as thoroughly as possible to try and measure linearity
    errors in the sensor.
    """
    STROKE_SPEED = 5
    STROKE_SPEED_TABLE = 1
    SETUP_SPEED = 200
    SETUP_SPEED_TABLE = 2
    GRID_STEP_MM = 10
    TOUCH_Z = bounds.paperZ()
    UP_Z = bounds.upZ()

    # Set up the speed table
    robot.setParam("T2 V%02d=%06.01f" % (SETUP_SPEED_TABLE, SETUP_SPEED)),
    robot.setParam("T2 V%02d=%06.01f" % (STROKE_SPEED_TABLE, STROKE_SPEED)),
    robot.addCmd("SPD V=%02d" % SETUP_SPEED_TABLE)

    strokes = StrokeController(robot, bounds, TOUCH_Z, UP_Z,
                   STROKE_SPEED_TABLE, SETUP_SPEED_TABLE)

    # Compute the lines from the starting edge
    ptsX = []
    x = bounds.minX()
    while x < bounds.maxX():
        # Find the intercept for a 45 degree line
        x_offset = x - bounds.minX()
        if x_offset < bounds.maxY() - bounds.minY():
            y_int = bounds.minY() + x_offset
            x_int = bounds.minX()
        else:
            y_int = bounds.maxY()
            x_int = x + x_offset

        # Program the stroke (and it's mirror) into the robot
        strokes.add_line((x, bounds.minY()), (x_int, y_int))
        x += GRID_STEP_MM

    # Do the same for the lines that don't intersect the starting edge
    y = bounds.minY()
    while y < bounds.maxY():
        if y + (bounds.maxX() - bounds.minX()) <= bounds.maxY():
            x_int = bounds.minX()
            y_int = y + (bounds.maxX() - bounds.minX())
        else:
            x_int = bounds.maxX() - (bounds.maxY() - y)
            y_int = bounds.maxY()

        strokes.add_line((bounds.maxX(), y), (x_int, y_int))
        y += GRID_STEP_MM

    # End the program nicely
    robot.addCmd("END")

if __name__=="__main__":
    if len(sys.argv) != 2:
        print "Usage: ./diagonals device_name"
    else:
        device = sys.argv[1]
        run_program.run_program(program, device)

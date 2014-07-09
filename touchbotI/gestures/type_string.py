# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Type a given string on the laptop.
This will write a program to the robot that will press each key corresponding
to the characters in the given string in turn.  If any of these characters are
not defined in the device spec, it will skip them and print out a warning.

Usage: ./type_string device STRING_TO_TYPE
   eg: ./type_string butterfly kjfjv
"""

import sys

import press_key
import roibot
import run_program


def program(robot, bounds, *args, **kwargs):
    """Upload a new program to the robot.  This program types out a string
    on the keyboard.
    """

    for c in args[0]:
        # For each character in the string, add a press_key gesture
        press_key.program(robot, bounds, c)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print "Usage: ./press_key device_name string_to_type"
    else:
        device = sys.argv[1]
        string_to_type = sys.argv[2]
        run_program.run_program(program, device, string_to_type)

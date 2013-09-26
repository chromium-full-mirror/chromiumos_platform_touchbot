# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Lower the finger until the limit switch is triggered to calibrate the
Z height for further testing.  Since this program halts as soon as the
finger is at the desired height, you can read out the Z position over the
serial connection and calibrate future gestures that way.
"""

import sys

import roibot
import run_program


def write_calibration_program(robot, bounds, *args, **kwargs):
    # Book keeping for the robots internal registers
    GPIO_COUNTER = 1
    DESCEND_LOOP_START = 1
    DESCEND_LOOP_END = 2
    DESCEND_STEP_SIZE = 0.1
    SPEED = 200

    # Move to above the center of the area you are calibrating z for
    robot.addMoveCommand((bounds.minX() + bounds.maxX()) / 2.0,
                         (bounds.minY() + bounds.maxY()) / 2.0,
                         0, SPEED)

    robot.addCmd(roibot.program.setTag(DESCEND_LOOP_START))

    # Move down a tiny bit
    mov_cmd = roibot.program.moveCoordinates(
                       False, 0, 0, DESCEND_STEP_SIZE, 0, True, 0, False)
    robot.addCmd(mov_cmd)

    # Copy the value of the GPIOs to the GPIO counter
    robot.addCmd(roibot.program.copyInputToCounter(0, 1, GPIO_COUNTER))

    # If the limit switch was triggered, jump out of the loop
    jmp_cmd = roibot.program.jumpCounterConditional(
                                DESCEND_LOOP_END, GPIO_COUNTER, '=', 0b00001000)
    robot.addCmd(jmp_cmd)

    # Otherwise jump back to the start
    robot.addCmd(roibot.program.jump(DESCEND_LOOP_START))

    robot.addCmd(roibot.program.setTag(DESCEND_LOOP_END))

def write_lift_finger_program(robot, bounds, *args, **kwargs):
    # Move to above the pad so that the finger is guaranteed not
    # to be in contact with the pad after calibration.
    SPEED = 200
    robot.addMoveCommand((bounds.minX() + bounds.maxX()) / 2.0,
                         (bounds.minY() + bounds.maxY()) / 2.0,
                         0, SPEED)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print 'Usage: ./' + sys.argv[0] + ' device_name'
    else:
        device = sys.argv[1]
        # Descend the finger onto the pad until it touches it
        run_program.run_program(write_calibration_program, device)

        # Reconnect to the robot and query the current Z position
        robot_port = run_program.scan_serial_ports();
        robot = roibot.ROIbot(port=robot_port,
                              baudrate=9600,
                              bytesize=8,
                              parity='E',
                              stopbits=1,
                              rtscts=0)
        robot.timeout = 2

        x, y, z = robot.getCurrentPosition()
        with open('calibrated_dimensions.py', 'w') as fo:
            fo.write('calibrated_device = "%s"\n' % device)
            fo.write('z = %f\n' % z)

        # Pick the finger up off the touchpad
        run_program.run_program(write_lift_finger_program, device)

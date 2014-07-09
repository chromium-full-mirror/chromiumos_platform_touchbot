#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# A graphical point picker that gives visual feedback on the screen for the
# current robot finger location and displays coordinates, allowing fine
# positioning under manual control.  Useful for registration of new device
# touch regions for use in other scripts.  See the README for details on
# how it works, but most controls are visible at the top of the screen.
#
# Note: This program uses curses, and generally perfers a taller, 80 column
# terminal window in which to to run.
#
import sys
import time

import curses
import curses.textpad

import roibot
import run_program

# Open the robot interface.
robot_port = run_program.scan_serial_ports()
robot = roibot.ROIbot(port=robot_port,
                      baudrate=9600,
                      bytesize=8,
                      parity='E',
                      stopbits=1,
                      rtscts=0)

# If the robot doesn't respond in 2 seconds to a command, then something
# is wrong.
robot.timeout = 2

#
# Perform an operation on the robot
#
try:
    # Clear outstanding error conditions (if any).
    #
    # This will clean up any bad outstanding state that exists from:
    #
    #   o   line noise from a previous connection
    #   o   resulting from the robot responding to flow control events
    #       occuring during initialization of the serial port:
    #       o   DTR off->on
    #       o   CTS/RTS
    #       o   etc.
    #
    print "COMMAND: Clear error status"
    robot.assertCancelError()
    print "COMMAND: Current status..."
    for statusElement in roibot.error.statusReport(robot):
        print "    ", statusElement
    print "COMMAND: Reset"
    robot.assertReset()

    print "COMMAND: Enable host mode"
    if robot.modeHostON():
        print "Host mode enabled"
    else:
        print "Failed to set host mode"

    print "COMMAND: Servo ON"
    if not robot.execServoON():
        print "Servo failed"
        for statusElement in roibot.error.statusReport(robot):
            print "    ", statusElement


#    print "COMMAND: Return to origin"
#    if not robot.execReturnToOrigin():
#        print "origin reset failed"
#
#    # Wait for completion
#    roibot.motion.waitForExecution(robot)

    # Show inaccuracy in settle at origin... :(
    print "This is not precise unless we wait for it to settle..."
    print robot.sendCommand("STAS", "SNO=0")
    print robot.monRequestPresentPosition()

    print robot.sendCommand("STAS", "SNO=0")
    print robot.monRequestPresentPosition()

    print robot.sendCommand("STAS", "SNO=0")
    print robot.monRequestPresentPosition()

    print robot.sendCommand("STAS", "SNO=0")
    print robot.monRequestPresentPosition()

    print robot.sendCommand("STAS", "SNO=0")
    print robot.monRequestPresentPosition()

    print robot.sendCommand("STAS", "SNO=0")
    print robot.monRequestPresentPosition()

    print "Starting..."

    def showSpeed(stdscr, speed):
        stdscr.move(0, 0)
        stdscr.addstr("Speed: " + str(speed))
        stdscr.move(0, 20)
        stdscr.addstr("[1] = 10.00, [2] = 01.00, [3] = 00.10, [4] = 00.01")

    def showAxis(stdscr, axis):
        stdscr.move(1, 0)
        stdscr.addstr("Axis: " + axis)
        stdscr.move(1, 20)
        stdscr.addstr("[<=] change axis down,    [=>] change axis up")

    def showKey(stdscr, key):
        stdscr.move(2, 0)
        if curses.ascii.isprint(key):
            key = "'" + chr(key) + "'"
        stdscr.addstr("Key : " + str(key) + "  ")
        stdscr.move(2, 20)
        stdscr.addstr("[^] move toward origin,   [v] move away from origin")

    def showPosition(stdscr, position):
        stdscr.move(3, 0)
        stdscr.addstr("Loc: " + str(position))

    #
    # Display the current probe (finger) location as an x,y location with a
    # pin altitude representing the z height as a negative offzet from max_z.
    #
    # A typical plot will look like:
    #
    # ,---------------,
    # |               |
    # |               |
    # |               |
    # |          o    | --.
    # |          |    |   | z
    # |          |    |x -'
    # |               |
    # `---------------'
    #            y
    #
    def showSampleArea(stdscr, x, y, z):
        # These numbers are based on screen coordinates
        base_x = 10
        base_y = 6
        dim_x = 20
        dim_y = 40
        dim_z = 5
        # These numbers reflect hardware limits of the robot itself
        max_x = 400.00
        max_y = 250.00
        max_z = 100.00
        inc_z = max_z / dim_z
        # Sample area rectangle - not entirely within the motion rectangle!
        #
        # These numbers are selected relative to the area in which the
        # cursor will move in order to describe the actual sample area;
        # the negative and positive offsets are used to move the box
        # outside.
        #
        # Moving the cursor outside the bounding rectange means that the
        # robot is no longer over the sample area, and therefor no longer
        # over the sample.
        curses.textpad.rectangle(stdscr,
                                 base_x - 1 - 2,
                                 base_y - 1,
                                 base_x + dim_x + 1 - 5,
                                 base_y + dim_y + 1 + 20)
        stdscr.move(base_x - 1 - 2, base_y + 10)
        stdscr.addstr("Sample Area Rectangle")
        # Motion rectangle; this is wehere the robot can reach.  Unfortunately
        # it does not precisely match the sample area rectangle, so there are
        # portions of the sample area not reachable by the robot, and there
        # are portions outside of the sample area that are reachable.
        #
        # Asserrtion: this is a hardware design bug.
        #
        # Like the above, there numbers are selected so that the cursor will
        # not leave the motion area.
        curses.textpad.rectangle(stdscr,
                                 base_x - 1, base_y - 1,
                                 base_x + dim_x + 1, base_y + dim_y + 1)
        stdscr.move(base_x - 1, base_y + 10)
        stdscr.addstr("Motion Rectangle")
        point_x = int(base_x + ((x * dim_x) / max_x))
        point_y = int(base_y + ((y * dim_y) / max_y))
        lim_z = base_y + int(y)
        stdscr.move(point_x, point_y)
        if (z < max_z):
            adj_z = int(max_z - z);
            while (adj_z > 0):
                stdscr.addstr("|")
                point_x = point_x - 1
                adj_z = adj_z - inc_z
                stdscr.move(point_x, point_y)
        stdscr.addstr("o")

    def main(stdscr):
        speed = "10.00"
        axis = "X"
        xjog = "+C"
        yjog = "SP"
        zjog = "SP"
        wjog = "SP"
        position = robot.monRequestPresentPosition()[1]
        x = float(position[0].split("=")[1])
        y = float(position[1].split("=")[1])
        z = float(position[2].split("=")[1])
        stdscr.clear()
        showPosition(stdscr, position)
        showSampleArea(stdscr, x, y, z)
        showSpeed(stdscr, speed)
        showAxis(stdscr, axis)
        showKey(stdscr, 0)
        stdscr.move(0, 0)
        stdscr.refresh()

        while True:
            c = stdscr.getch()
            if c != -1:

                if c == ord('q'): # quit
                    break;

                if c == ord('o'): # origin
                    robot.execReturnToOrigin()
                    roibot.motion.waitForExecution(robot)

                elif c == ord('1'):  # inching distance large
                    speed = "10.00"
                    stdscr.move(0, 0)
                    stdscr.addstr("Speed: " + str(speed))
                    robot.sendCommand("WPAR", "P12", "AX1=" + speed,
                                                     "AX2=" + speed,
                                                     "AX3=" + speed,
                                                     "AX4=" + speed)

                elif c == ord('2'):  # inching distance medium
                    speed = "01.00"
                    stdscr.move(0, 0)
                    stdscr.addstr("Speed: " + str(speed))
                    robot.sendCommand("WPAR", "P12", "AX1=" + speed,
                                                     "AX2=" + speed,
                                                     "AX3=" + speed,
                                                     "AX4=" + speed)

                elif c == ord('3'):  # inching distance small
                    speed = "00.10"
                    stdscr.move(0, 0)
                    stdscr.addstr("Speed: " + str(speed))
                    robot.sendCommand("WPAR", "P12", "AX1=" + speed,
                                                     "AX2=" + speed,
                                                     "AX3=" + speed,
                                                     "AX4=" + speed)

                elif c == ord('4'):  # inching distance tiny
                    speed = "00.01"
                    stdscr.move(0, 0)
                    stdscr.addstr("Speed: " + str(speed))
                    robot.sendCommand("WPAR", "P12", "AX1=" + speed,
                                                     "AX2=" + speed,
                                                     "AX3=" + speed,
                                                     "AX4=" + speed)

                elif c == curses.KEY_UP:  # Move probe negative on axis
                    robot.execJog(**{axis:"-C"})
                    roibot.motion.waitForExecution(robot)

                elif c == curses.KEY_DOWN:  # Move probe positive on axis
                    robot.execJog(**{axis:"+C"})
                    roibot.motion.waitForExecution(robot)

                elif c == curses.KEY_LEFT:
                    if axis == 'X':
                        axis = 'Z'
                    elif axis == 'Z':
                        axis = 'Y'
                    elif axis == 'Y':
                        axis = 'X'

                elif c == curses.KEY_RIGHT:
                    if axis == 'X':
                        axis = 'Y'
                    elif axis == 'Y':
                        axis = 'Z'
                    elif axis == 'Z':
                        axis = 'X'

                position = robot.monRequestPresentPosition()[1]
                x = float(position[0].split("=")[1])
                y = float(position[1].split("=")[1])
                z = float(position[2].split("=")[1])
                stdscr.clear()
                showPosition(stdscr, position)
                showSampleArea(stdscr, x, y, z)
                showSpeed(stdscr, speed)
                showAxis(stdscr, axis)
                showKey(stdscr, c)
                stdscr.move(0,0)
                stdscr.refresh()

    if __name__ == '__main__':
        curses.wrapper(main)

    print "done"

except roibot.roibot.ROIbotTimeoutException:
    # timeouts - usually communications or stuck servo related
    print "timed out!"
#except:
    # all other errors
    print "Exception!"
    for statusElement in roibot.error.statusReport(robot):
        print "    ", statusElement

robot.timeout = None

robot.close()

#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Reset all the robot parameters.  This is generally useful if you send
# the MINT PR=0 command, and clear the entire memory contents, since this
# also destroys all the axis, speed, and other default settings.
#
import sys
import time

import roibot

# Open the robot interface.
# robot = roibot.ROIbot(sys.argv[1])
robot = roibot.ROIbot(port='/dev/ttyUSB0',
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


    #
    # Reinitialize necessary parameters
    #
    print robot.enableWriteEEPROM()

    #robot.writeParameter("P01", "AX1=+0400.00", "AX2=+0250.00", "AX3=+0100.00",
    #                     "AX4=+0000.00")
    print robot.sendCommand("RPAR P01")
    print robot.sendCommand("RSTX 0003")

    print robot.sendCommand("WPAR E01 AX1=X AX2=Y AX3=Z AX4=?")

    print robot.sendCommand("RPAR M01")
    print robot.sendCommand("RPAR M02")
    print robot.sendCommand("RPAR M03")
    print robot.sendCommand("RPAR M04")
    print robot.sendCommand("RPAR M05")
    print robot.sendCommand("RPAR M06")
    print robot.sendCommand("RPAR M07")
    print robot.sendCommand("RPAR M08")
    print robot.sendCommand("RPAR M09")
    print robot.sendCommand("RPAR M10")
    print robot.sendCommand("RPAR M11")
    print robot.sendCommand("RPAR M12")
    print robot.sendCommand("RPAR M13")
    print robot.sendCommand("RPAR M14")
    print robot.sendCommand("RPAR M15")

    print robot.sendCommand("TYPE AX1 RTYP=510000")
    print robot.sendCommand("STAS SNO=0")
    print robot.sendCommand("STAS SNO=1")
    print robot.sendCommand("TYPE AX2 RTYP=510000")
    print robot.sendCommand("TYPE AX3 RTYP=520180")
    print robot.sendCommand("TYPE AX4 RTYP=510100")
    print robot.sendCommand("SYSP")
    print robot.sendCommand("RPAR M16")
    print robot.sendCommand("RPAR M17")
    print robot.sendCommand("RPAR M18")
    print robot.sendCommand("RPAR M19")
    print robot.sendCommand("RPAR M20")
    print robot.sendCommand("RPAR M21")
    print robot.sendCommand("RPAR P01")
    print robot.sendCommand("RPAR P02")
    print robot.sendCommand("RPAR P03")
    print robot.sendCommand("RPAR P04")
    print robot.sendCommand("RPAR P05")
    print robot.sendCommand("RPAR P06")
    print robot.sendCommand("RPAR P07")
    print robot.sendCommand("RPAR P08")
    print robot.sendCommand("RPAR P09")
    print robot.sendCommand("RPAR P10")
    print robot.sendCommand("RPAR P11")
    print robot.sendCommand("RPAR P12")
    print robot.sendCommand("RPAR P13")
    print robot.sendCommand("RPAR P14")
    print robot.sendCommand("RPAR P15")
    print robot.sendCommand("RPAR P16")
    print robot.sendCommand("RPAR P17")
    print robot.sendCommand("RPAR P18")
    robot.parameterWrite("E01", "AX1=X", "AX2=Y", "AX3=Z", "AX4=?")
    robot.parameterWrite("E02", "AX1=00.05", "AX2=00.05", "AX3=00.05",
                         "AX4=00.05")
    robot.parameterWrite("E03", "AX1=20000", "AX2=20000", "AX3=20000",
                         "AX4=20000")
    robot.parameterWrite("E04", "AX1=02000", "AX2=02000", "AX3=02000",
                         "AX4=02000")
    robot.parameterWrite("E05", "AX1=0", "AX2=0", "AX3=1", "AX4=1")
    robot.parameterWrite("E06", "AX1=1200", "AX2=1200", "AX3=0800", "AX4=1200")
    robot.parameterWrite("E07", "L=002.0", "M=020.0 H=100.0")
    robot.parameterWrite("E08", "L=002.0", "M=020.0 H=100.0")
    robot.parameterWrite("E09", "L=002.0", "M=020.0 H=100.0")
    robot.parameterWrite("E10", "L=002.0", "M=020.0 H=100.0")
    robot.parameterWrite("E11", "AX1=0", "AX2=0", "AX3=2", "AX4=0")
    robot.parameterWrite("E12", "AX1=1", "AX2=1", "AX3=0", "AX4=1")
    robot.parameterWrite("E13", "AX1=+0020.00", "AX2=+0020.00", "AX3=+0020.00",
                         "AX4=+0020.00")
    robot.parameterWrite("E14", "AX1=20.000", "AX2=20.000", "AX3=12.000",
                         "AX4=20.000")
    robot.parameterWrite("E15", "AX1=2000", "AX2=2000", "AX3=2000", "AX4=2000")
    robot.parameterWrite("E16", "AX1=4", "AX2=4", "AX3=4", "AX4=4")
    robot.parameterWrite("E17", "E=a")
    robot.parameterWrite("E18", "TW=060")
    robot.parameterWrite("E19", "4000")
    robot.parameterWrite("E20", "TASK01=1", "TASK02=1", "TASK03=1",
                         "TASK04=1")
    robot.parameterWrite("E21", "TASK01=999", "TASK02=999", "TASK03=999",
                         "TASK04=999")
    robot.parameterWrite("E22", "TASK01=2000", "TASK02=0000", "TASK03=0000",
                         "TASK04=0000")
    robot.parameterWrite("E23", "I")

    print robot.monRequestPresentPosition()

except roibot.roibot.ROIbotTimeoutException:
    # timeouts - usually communications or stuck servo related
    print "timed out!"
except:
    # all other errors
    for statusElement in roibot.error.statusReport(robot):
        print "    ", statusElement

robot.timeout = None
robot.close()

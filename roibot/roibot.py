#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
#
# Toshiba Machine Co, LTD.
# ROIBOT
# BA Series
# CA10-M00
#
# Industrial robot interface mode control module
#

import serial

#
# Exceptions
#
class ROIbotException(Exception):
    """Base class for robot related exception."""

class ROIbotParameterException(ROIbotException):
    """Parameter exception."""

class ROIbotTimeoutException(ROIbotException):
    """Timeout exception."""

class ROIbotModeException(ROIbotException):
    """"Operation not permitted in this mode."""

class ROIbotUnrecoverableErrorException(ROIbotException):
    """"Software could not clear an error."""

readTimeoutError = ROIbotTimeoutException("Read timeout")
hostModeError = ROIbotModeException("Command invalid outside host mode")
writeProtectError = ROIbotModeException("EEPROM is write protected")
unrecoverableError = ROIbotUnrecoverableErrorException("Unrecoverable")


#
# Implementation class
#
# Exceptions:   ROIbotModeException     Thrown when a requested operation is
#                                       not permitted in the current mode.
#
#               ROIbotTimeoutException  A read attempt had timed out; if this
#                                       was a long duration operation,
#                                       consider subclassing and adding a
#                                       utility function to set a higher
#                                       timeout for the operation.
#
#               ROIbotReadOnlyException We maintain a synthetic EEPROM protect
#                                       flag to prevent unintentional calls to
#                                       modify the EEPROM content.
#
class ROIbot(serial.Serial):

    _AdhocTestON = True
    _writeEEPROM = False
    _hostModeON = False
    _line_number = 1
    _point_number = 1

    #
    # Utility functions
    #
    def enableWriteEEPROM(self):
        """Enable writing the EEPROM by setting the soft write protect to
           True.  The default is that the soft write protect is enabled,
           and commands which would result in the EEPROM being written will
           throw the exception ROIbotReadOnlyException."""
        self._writeEEPROM = True

    def disableWriteEEPROM(self):
        """Disable writing the EEPROM by setting the soft write protect to
           False.
        """
        self._writeEEPROM = False

    def assertCancelError(self):
        """Attempts to clear the error status, if any, twice.  If an error
           exists after that, it raises an unrecoverableError exception.
        """
        if not self.execCancelError():
            if not self.execCancelError():
                raise unrecoverableError

    def assertReset(self):
        """Resets the robot.  On failure raises an unrecoverableError
           exception.
        """
        if not self.execReset():
            if not self.execReset():
                raise unrecoverableError

    def sendCommand(self, *args):
        """Send a command to the robot and wait for a response; a command
           is of the form:

                @<four character command>[<space><data>...]<cr><lf>

           All commands Receive responses in the form of a command, with the
           canonical response being a success or failure indicator:

               @OK<cr><lf>
               @NG<cr><lf>

           The function returns a list consisting of a result string followed
           by a (potentially empty) list of additional data items.
        """
        cmdlist = [str(arg) for arg in args]
        cmd = ' '.join(args)
        self.write("@" + cmd + "\r\n")
        response = self.readline().lstrip("@").rstrip("\r\n").split(" ")
        code = response.pop(0)
        if (code == ''):
            raise readTimeoutError
        result = [code, response]
        return result

    # Returns True on success; test for failure with "if not <command>:"
    def TFResult(self, tuple):
        if (tuple[0] == 'OK'):
            return True
        return False

    #
    # Assertion convenience functions for software enforced state flags
    #
    def assertHostModeON(self):
        if (self._hostModeON == False and self._AdhocTestON == False):
            raise hostModeError

    def assertWritableEEPROM(self):
        if (self._writeEEPROM == False and self._AdhocTestON == False):
            raise writeProtectError

    #
    # Mode commands
    #
    # Note: These include status requests, most likely because they had no
    # other reasonable place to group them.
    #
    # As a general rule, all mode commands other than host mode control or
    # status requests require the robot to be in host mode.
    #
    def modeRequestSystemParameter(self):
        """Request system parameter.  This returns the robot type information,
           the controller version, the language used by the teaching pad
           (generally irrelevant), and information about up to 4 Axis of
           motion.
        """
        return self.sendCommand("SYSP")

    def modeRequestControllerVersion(self, station=0):
        """Request controller version information from up to five stations
           in the range 0..4; if no station number is specified, the
           version information for station 0 will be reported by default.

           The result is a tuple of the form:

               ["NO=<station number>", "VER=<2 digits>.<2 digits>"]

           returned.
        """
        return self.sendCommand("CVER", "NO=" + str(station))

    def modeRequestRobotType(self, axis=1, robotType=0):
        """Request robot type information from up to four axis in the
           range 1..4, and a asserted robotType in the range of 0-99999.
           If no axis is specified, the type information for axis 1 will be
           reported by default.  If no robotType is specifidm the type will
           be tested vs. a default type of 0.

           The result is a tuple of the form:

            ["AX<axis>", "RTYP=<6 digits>"]

           returned.
        """
        return self.sendCommand("TYPE", "AX" + str(axis),
                                "RTYP=%06d" % robotType)

    def modeRequestStatus(self, statusNumber=0):
        """Request controller status information one of five status registers
           in the range 0..4; if no statusNumber is specified, the default
           is to return stutus "0".

           The result is a tuple of the form:

                ["SNO=<statusNumber>", "ST1=<%02x>", "ST2=<%02x>"]

           returned.
        """
        return self.sendCommand("STAS", "SNO=" + str(statusNumber))

    def modeHostON(self):
        """Enter host mode.  This mode is required to use most commands."""
        result = self.TFResult(self.sendCommand("HSON"))
        if (result):
            self._hostModeON = True
        return result

    def modeHostOFF(self):
        """Exit host mode.  Most commands will be unavailable when not in
           host mode.
        """
        result = self.TFResult(self.sendCommand("HSOF"))
        if (result):
            self._hostModeON = False
        return result

    def modeProgram(self):
        """Enter program mode.  Program mode may be cancelled via modeHostON.

           You must be in in Host mode to enter program mode.
        """
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("MPRO"))

    def modeStep(self):
        """Enter step mode."""
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("MSTP"))

    def modeAutomatic(self):
        """Enter Automatic mode."""
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("MAUT"))

    def modeSequential(self):
        """Enter sequential mode.  Sequential mode may be cancelled via
           modeHostON.

           You must be in in Host mode to enter sequential mode.
        """
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("MSEQ"))

    def modePalletizing(self):
        """Enter palletizing mode.  Palletizing mode may be cancelled via
           modeHostON.

           You must be in in Host mode to enter palletizing mode.
        """
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("MPLE"))

    #
    # Parameter commands
    #
    # Read and write parameters.
    #
    # Writing is restricted to writeEEPROM mode being enabled.
    #
    def parameterRead(self, parameter):
        """Read parameters.  Parameters are described in section 2-4 of the
           COMPO ARM RS232C Communications Specifications manual.  There are
           a significant number of them, and they may only be changed in
           EEPROM write enabled mode, so they are not specifically documented
           here at this time.  It's possible that at some future point that
           parameter decoding functions will be made available using an
           auxillary class.
        """
        return self.sendCommand("RPAR " + str(parameter))

    def parameterWrite(self, parameter, *args):
        """Write parameters.  Parameters are described in section 2-4 of the
           COMPO ARM RS232C Communications Specifications manual.  There are
           a significant number of them, and they may only be changed in
           EEPROM write enabled mode, so they are not specifically documented
           here at this time.  It's possible that at some future point that
           parameter encoding functions will be made available using an
           auxillary class.
        """
        self.assertHostModeON()
        self.assertWritableEEPROM()
        return self.TFResult(self.sendCommand("WPAR", str(parameter), *args))


    #
    # Text editing commands
    #
    # These commands deal predominantly with reading and writing of the
    # EEPROM and memory card contents.  Use of memory card commands
    # requires installation of the optional memory card module.
    #
    # EEPROM write operations are restricted to writeEEPROM mode being
    # enabled.
    #
    def textInitializeMemory(self, regionCode):
        """Initialize memory.  The parameter is a region code in the range
           0..6, with the values having the following meanings:

               0    Memory clear
               1    Sequential clear
               2    Palletizing clear
               3    Sequential/Palletizing clear
               4    Easy/Point table clear
               5    Reserved (do not send this to avoid future issues)
               6    Point table clear

           Note that Sequential and Point table only apply to the currently
           set tasks, rather than all tasks.
        """
        self.assertHostModeON()
        self.assertWritableEEPROM()
        return self.TFResult(self.sendCommand("MINT", "PR=" + str(regionCode)))

    def textCopySequentialStep(self, sourceTask, startStep, endStep,
                       targetTask, targetStep):
        """Copy a set of steps from one task to another."""
        self.assertHostModeON()
        self.assertWritableEEPROM()
        return self.TFResult(self.sendCommand("CPSS",
                                              "TASK=%02d" % sourceTask,
                                              "STA=%04d" % startStep,
                                              "END=%04d" % endStep,
                                              "TEASK=%02d" % targetTask,
                                              "TOP=%04d" % targetStep))

    def textInsertSequentialLine(self, insertionStep):
        """Insert a step at the designated step."""
        self.assertHostModeON()
        self.assertWritableEEPROM()
        return self.TFResult(self.sendCommand("ISTX", "%04d" % insertionStep))

    def textDeleteSequentialLine(self,deletionStep):
        """Delete the designated step"""
        self.assertHostModeON()
        self.assertWritableEEPROM()
        return self.TFResult(self.sendCommand("DSTX", "%04d" % deletionStep))

    def textSearchSequentialTag(self, searchTag):
        """Search for the specified text tag; tags are "goto" labels."""
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("SSTG", "TAG=%03d" % searchTag))

    def textDeleteSequentialBlock(self, startStep, endStep):
        """Delete a sequential block of steps."""
        self.assertHostModeON()
        self.assertWritableEEPROM()
        return self.TFResult(self.sendCommand("DSTL",
                                              "STA=%04d" % startStep,
                                              "END=%04d" % endStep))

    def textCopyPalletizingProgram(self, sourceProgram, destinationProgram):
        """Copy one palletizing program to another."""
        self.assertHostModeON()
        self.assertWritableEEPROM()
        return self.TFResult(self.sendCommand("CPPL",
                                              "STA=%02d" % sourceProgram,
                                              "TOP=%02d" % destinationProgram))

    def textCopyEasyProgram(self, sourceProgram, destinationProgram):
        """Copy one easy program to another."""
        self.assertWritableEEPROM()
        return self.TFResult(self.sendCommand("CESY",
                                              "STA=%02d" % sourceProgram,
                                              "TOP=%02d" % destinationProgram))

    def textWriteEasy(self, program, startTag, loopCount, endTag):
        """Write easy text."""
        self.assertWritableEEPROM()
        return self.TFResult(self.sendCommand("WESY",
                                              "PNO=%02d" % program,
                                              "ST=000",
                                              "START=%03d" % startTag,
                                              "LOOP=%04d" % loopCount,
                                              "END=%03d" % endTag))

    def textReadEasy(self):
        """Read easy text."""
        return self.sendCommand("RESY", "PNO=%02d" % program, "ST=000")

    def textWriteSequential(self, *args):
        """Enter sequential text entry mode.  It's strongly suggested in
           the documentation that this mode completes when automatic mode
           is entered.  While in this mode, additional sequential writes
           result in program storage of the arguments.

           TODO(tlambert): textWriteSequentialStep()
                           textWriteSequentialEnd()
           """
        self.assertHostModeON()
        self.assertWritableEEPROM()
        return self.TFResult(self.sendCommand("WSTX", *args))

    def textReadSequential(self):
        """Read sequential text.  Start reading back sequential program steps.

           TODO(tlambert): textReadSequentialStep()
           """
        return self.sendCommand("RSTX", "0001")

    def textWritePalletizing(self):
        """Enter palletizating text entry mode.

           TODO(tlambert): textWritePalletizingStep()_
                           textWritePalletizingEnd()
           """
        self.assertHostModeON()
        self.assertWritableEEPROM()
        return self.TFResult(self.sendCommand("WPLT",
                                              "99",
                                              "SNO=01",
                                              "TAG=001",
                                              "MOD=M-M"))


    def textReadPalletizing(self):
        """Read [alletizing text.  Start reading program steps.

           TODO: textReadPalletizingStep()
           """
        return self.sendCommand("RPLT", "99", "SNO=01", "TAG=001", "MOD=M-M")

    #
    # Memory card specific commands
    #
    # This sections is offset separately due to the optional nature of
    # the memory card module.
    #
    def textWriteMemoryCard(self):
        """Write to memory card."""
        return self.TFResult(self.sendCommand("WMCA"))

    def textReadMemoryCard(self):
        """Read from memory card."""
        return self.TFResult(self.sendCommand("RMCA"))


    #
    # Execution control
    #
    # These operations are immediately carried out by the robot.  Not all
    # of them require host mode.  Of all of them, execWriteOverride()
    # also requires write enabling the EEPROM.
    #
    # In general, it's possible to call into other modes and perform port
    # output, or potentially even damage the robot using these commands,
    # so caution should be exercised in their use.
    #
    def execReturnToOrigin(self):
        """Return all positioning servos to their origin (power on) state."""
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("HOME"))

    def execStartSequential(self, step):
        """Start sequential beginning at the specified step."""
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("SPST", "%04d" % step))

    def execSetPalletizingProgram(self, progran):
        """Set the current palletizing program.  Palletizing programs
           are in the range 01..16 and must be pre-programmed into the
           EEPROM.
           """
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("SPLN", "PR=%02d" % progran))

    def execStartPalletizing(self):
        """Start the currently selected palletizing program."""
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("PPST"))

    def execSetEasyProgram(self, program):
        """Set the current easy program.  Easy programs are in the range
           01..08 and must be pre-programmed into the EEPROM.
           """
        return self.TFResult(self.sendCommand("EXTP", "PT=%03d" % point))

    def execStartEasy(self):
        """Start the currently selected easy program."""
        return self.TFResult(self.sendCommand("SESY"))

    def execRequestPalletizingData(self):
        """Read out the palletising data; this data is set using text
           commands.
           """
        return self.TFResult(self.sendCommand("RPLD"))

    def execStop(self):
        """Stop sequential, palletizing, easy, or external point designation
           operations in progress.
           """
        return self.TFResult(self.sendCommand("STOP"))

    def execJog(self, X="SP", Y="SP", Z="SP", R="SP"):
        """Move the robot in up to four axes. Motion will occur one axis
           at a time.  Multiple axes can not be moved at the same time.
           """
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("JGST",
                                              "X=" + str(X),
                                              "Y=" + str(Y),
                                              "Z=" + str(Z),
                                              "R=" + str(R)))

    def execDirectPortOutput(self, station, portNumber, outputDesignation):
        """Direct port output."""
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("DOUT",
                                              "STN=" + str(station),
                                              "PN%02d=" % portNumber,
                                              "STR=" + str(outputDesignation)))

    def execWriteOverride(self, override):
        """Write override.  Only valid when the program is stopped."""
        self.assertWritableEEPROM()
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("WOVR", "OV=%03d" % override))

    def execReadOverride(self):
        """Read override."""
        return self.sendCommand("ROVR")

    def execReset(self):
        """Reset."""
        return self.TFResult(self.sendCommand("REST"))

    def execCancelError(self):
        """Cancel an outstanding error condition."""
        return self.TFResult(self.sendCommand("CERR"))

    def execStartExternalPointDesignation(self, point):
        """Start external point designation given a coordinate table entry
           number in the range 001..999.
           """
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("EXTP", "PT=%03d" % point))

    def execServoON(self):
        """Servo on."""
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("SVON"))

    def execServoOFF(self):
        """Servo off."""
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("SVOF"))

    def execRequestEasyExecutionData(self):
        """Read out easy execution status."""
        return self.sendCommand("RESD")

    def execChangeTaskNumber(self, task):
        """Change the task number to the specified value.  Task values are
           in the range 01..04.
           """
        return self.TFResult(self.sendCommand("CTSK", "PR=%02d" % task))

    def execSynchronizedOriginSearch(self, axis):
        """Synchronized origin search.  This command is only valid when
           communicating with a CA20-M00/M01 robot.
           """
        self.assertHostModeON()
        return self.TFResult(self.sendCommand("SORG", str(axis)))


    #
    # Monitor commands
    #
    def monRequestInputData(self, station, screen):
        """Request input data.  Reads input from a station in the range 0..4
           from a screen in the range 1..7 (stations in the range 1..4 are
           fixed at screen 1).  Port data is returned in the response.
           """
        return self.sendCommand("MINP",
                                "SNO=" + str(station),
                                "GN=" + str(screen))

    def monRequestOutputData(self, station, screen):
        """Request ouput data from a station in the range 0..4 from a screen
           in the range 1..5 (stations in the range 1..4 are fixed at screen
           1).  Port data is returned in the response.
           """
        return self.sendCommand("MOUT",
                                "SNO=" + str(station),
                                "GN=" + str(screen))

    def monInternalPortData(self, station, screen):
        """Internal port data request from a station (must be 0) screen
           (must be 1).  Port information for up to 4 ports is returned.
           """
        # TODO(tlambert): assert the requirements.
        return self.sendCommand("MNIN",
                                "SNO=" + str(station),
                                "GN=" + str(screen))

    def monRequestPresentPosition(self):
        """Request present position.  Returns the current X, Y, Z, and
           rotational coordinates.  Not all robots support all coordinates.
           """
        return self.sendCommand("MPST")

    def monRequestPresentOffsetValue(self):
        """Request present offset value.  Returns the current X, Y, Zm and
           rotational offsets.  Not all robots support all coordinates.
           """
        return self.sendCommand("MOFF")

    def monRS232CCoordinateDataSettings(self, task, x, y, z, rotation,
                                        velocity):
        """Set the current X, Y, Z, and rotation at the velocity specified
           in the speed table entry requested.  Coordinates are in the range
           -8000.00..+8000.00; the speed table entry is in the range 00..10.
           """
        return self.TFResult(self.sendCommand("MRSS",
                                              "TASK=%02d" % task,
                                              "X=%07.02f" % x,
                                              "X=%07.02f" % y,
                                              "X=%07.02f" % z,
                                              "X=%07.02f" % rotation,
                                              "X=%02" % velocity))

    def monRequestCounterValue(self, counter):
        """Request the current value of the specified counter in the range
           01..99.
           """
        return self.sendCommand("MCNT", "CN=%02d" % counter)

    def monRequestTimerValue(self, timer):
        """Request the current value of the specified timer in the range
           1..9.
           """
        return self.sendCommand("MTMR", "TN=" + str(timer))

    def monCounterDirectSet(self, counter, value):
        """Set the specified counter in the range 01..99 to the specified
           value in the range 0000..9999.
           """
        return self.TFResult(self.sendCommand("MCST",
                                              "CN%02d=%03d" % (counter, value)))

    def monRequestErrorPointNumber(self):
        """Request the error point number."""
        return self.sendCommand("MERP")

    def monReadTaskNumberReadCurrentStep(self):
        """Read the current task number; results are in the range 01..04."""
        return self.sendCommand("MTSK")

    def monReadCurrentStep(self):
        """Read the current step number; results are in the range
           0001..2500.
           """
        return self.sendCommand("RSTX", "0000")

    def monReadCCLinkStatus(self, index):
        """Read CC-Link status.  This command is only valid when
           communicating with a CA20-M00/M01 robot.
           """
        return self.sendCommand("MBUS", "C" + str(step))

    def monErrorHistoryRequest(self):
        """Request error history."""
        return self.sendCommand("EHTR", "NO=01")

    # High level EEPROM programming instructions
    #
    # The follow functions wrap the commands for writing a program to the
    # EEPROM of the robot.  They all will make multiple attempts to issue
    # their command, and raise an exception if they are unsuccessful.
    def addCmd(self, cmd):
        """Upload a new command into the next spot in the eeprom.  This adds a
        new instruction to the program in the robots memory.
        """
        print "ADDING:  %04d %s" % (self._line_number, cmd)
        self.tryOrFail(self.textWriteSequential,
                       "%04d" % self._line_number, cmd)
        self._line_number += 1

    def setParam(self, cmd):
        """Set a parameter's value.  This can be any "parameter" in the robot,
        such as altering speed profiles or point tables, etc.
        """
        print "SETTING: %s" % cmd
        self.tryOrFail(self.parameterWrite, cmd)

    def addPoint(self, x, y, z):
        """Add a new point to the point table (returns the point number)."""
        self.setParam("T1 PT=%03d " % self._point_number +
                      "X=+%07.02f " % x +
                      "Y=+%07.02f " % y +
                      "Z=+%07.02f " % z +
                      "R=+0000.00")
        self._point_number += 1
        return self._point_number - 1

    def tryOrFail(self, fn, *args, **kwargs):
        """Make multiple attempts to call a function fn().  The function should
        return True or False.  If after NUM_RETRIES attempts, there still
        hasn't been a success, raise an exception.
        """
        NUM_RETRIES = 2
        for i in range(NUM_RETRIES):
            result = fn(*args, **kwargs)
            if result:
                return result
        raise unrecoverableError
# End

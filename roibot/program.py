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
"""Industrial robot interface programming control module

This module defines EEPROM programming capabilities for sequentially
for iteratively setting program steps starting at a given step, and
then writing a subsequent set of steps to the program store.  A set
of utility functions which permit creation of command tuple sets for
passing in to the textWriteSequential()/textReadSequential().
"""

import time

import roibot

#
# Globals for this module
#

# Where a moveAbsolute is specified, translate the parameter expected.
moveAbsoluteTable = {
    True : "a",
    False : "i",
}

# Where a constantSpeed is specified, translate the parameter expected.
axisConstantSpeedTable = {
    True : "S",
    False : "T",
}

# Where a point may be either positional or passed, translate the parameter
# expected.
postPassTable = {
    True : "POST",
    False : "PASS",
}


# Explicitly signed strings of specific length are frequently required.
signTable = {
    1 : "-",
    0 : "+",
}

#
# Utility functions.
#
def _signSplit(value):
    """Utility function to translate a speed into a sign and value tuple."""
    return (signTable[int(value < 0.0)], abs(value))

#
# Programming commands.
#
# All programming commands return a tuple of parameter strings which can
# then be used as arguments to aggregate a stepwise write into EEPROM
# memory.  Since these commands are not usable directly, it's more correct
# to deal with them as artial argument list tuple sets this way.
#
def acceleration(acc):
    """Selects an acceleration table entry for use in subsequent operations.
       The acceleration table entry is in the range 01..20 and is assumed
       to have been pre-programmed, and not changed often.
    """
    return ("ACC", "A=%02d" % acc)

def counterJump(counterNumber, tagNumber):
    """Branch to a program tag number plus counter value.  The counter must
       be in the range 01..99, and the taag number in the range 000..999.

       The result of adding the value of the counter to the tag must be in
       the range 000..999, or it's an error.
    """
    return ("BRAC", "CN=%02d" % counterNumber, "OFS=%03d" % tagNumber)

def callUnconditional(tagNumber):
    """Call a subroutine at a step designated by a tag number.  The
       subroutine must end in a subReturn() to return control back
       to the step following the calling site.

       Subroutines may be nested no more than 10 levels deep.
    """
    return ("CAL", "TAG=%03d" % tagNumber)

def callCounterConditional(tagNumber, counterNumber, operator, value):
    """Call a subroutine at a step designated by a tag number when the
       specified counter contents satisfy the comparison operator when
       compared to the value.  The following limitations apply:

           The tag must be in the range 001..999
           The counter number must be in the range 01..99
           The count value must be in the range 0000..9999

       The following operators are supported, and should be passed as string
       values:

           =    Compare for equality
           <    Compare for counter less than the value
           >    Compare for the counter greater than the value
           <=   Compare for the counter less than or equal to the value
           >=   Compare for the counter greater than or equal to the value

       There is no operator available for cmparison for inequality; instead,
       a compination of two comparisons is required.
    """
    return ("CALC",
            "TAG=%03d" % tagNumber,
            "CN%02d%s" % (counterNumber, operator),
            "%04d" % value)

def callInputConditional(tagNumber, stationNumber, portNumber, pattern):
    """Call a subroutine at a step designated by a tag number when the
       specified input port contents match the comparison tag bits.  The
       following limitations apply:

           The tag must be in the range 001..999
           The station must be in the range 0..4
           The port number must be in the range 00..99

       Bits are specified as an 8 byte string value and have the following
       meanings:

           .    Don't care
           1    Bit must be high
           0    Bit must be low

       So as an example, the string "110.0011" would match the values
       0x0c03 or 0x0d03.
    """
    return ("CALI",
            "TAG=%03d" % tagNumber,
            "STN=%1d" % stationNumber,
            "PN%02d=%s" % (portNumber, pattern))

def callTimerConditional(tagNumber, timerNumber, operator, value):
    """Call a subroutine at a step designated by a tag number when the
       specified timer contents satisfy the comparison operator when
       compared to the value.  The following limitations apply:

           The tag must be in the range 001..999
           The timer number must be in the range 0..9
           The comparison value must be in the range 000.0..999.9

       The following operators are supported, and should be passed as string
       values:

           =    Compare for equality
           <    Compare for counter less than the value
           >    Compare for the counter greater than the value
           <=   Compare for the counter less than or equal to the value
           >=   Compare for the counter greater than or equal to the value

       There is no operator available for cmparison for inequality; instead,
       a compination of two comparisons is required.
    """
    return ("CALT",
            "TAG=%03d" % tagNumber,
            "TN%1d%s" % (timerNumber, operator),
            "%05.01f" % value)

def setCounter(counterNumber, value):
    """Set the specified counter to the specified value.  Counters must be
       in the range 01..99 and values must be in the range 0000..9999.
    """
    return ("CNT", "CN%02d=%04d" % (counterNumber, value))

def incrementCounter(counterNumber, value):
    """Increment the specified counter by the specified value.  Counters
       must be in the range 01..99 and values must be in the range
       0000..9999.  If a counter reaches the value 9999, it does not
       return an error, nor does it increment further.
    """
    return ("CNT+", "CN%02d=%04d" % (counterNumber, value))

def decrementCounter(counterNumber, value):
    """Decrement the specified counter by the specified value.  Counters
       must be in the range 01..99 and values must be in the range
       0000..9999.  If a counter reaches the value 0000, it does not
       return an error, nor does it decrement further.
    """
    return ("CNT-", "CN%02d=%04d" % (counterNumber, value))

def clearAllCounters():
    """Set all counters to 0000."""
    return ("CNTC")

def counterConditionWait(counterNumber, operator, value):
    """Wait until the specified counter contents satisfy the comparison
       operator when compared to the value.  The following limitations
       apply:

           The counter number must be in the range 01..99
           The count value must be in the range 0000..9999

       The following operators are supported, and should be passed as string
       values:

           =    Compare for equality
           <    Compare for counter less than the value
           >    Compare for the counter greater than the value
           <=   Compare for the counter less than or equal to the value
           >=   Compare for the counter greater than or equal to the value

       There is no operator available for cmparison for inequality; instead,
       a compination of two comparisons is required.

       Note: This operation is typically used to synchronize tasks then
             performing multiple tasks, either simultaneously or
             sequentially.
    """
    return ("CWIT", "CN%02d%s" % (counterNumber, operator), "%04d" % value)

def end():
    """Return the program step counter to step 0001 and wait for another
       START input.  When multitasking, and the end occurs in tasks 2
       through 4, the task returns to step 0001 and waits for another
       taskStart().
    """
    return ("END")

def home():
    """Return to origin at high homing speed.  The axis are move in the
       order previously specified by preprogrammed parameters.  Because
       the robot is mechanically an interference model device, it's
       possible for the robot to damage itself or the work item when
       executing this command, and therefore care must be taken in the
       parameter programming.

       Note: If multitasking is enabled, only the task executing the
             Home operation returns to its home position.
    """
    return ("HOME")

def waitInput(stationNumber, portNumber, pattern, logic):
    """Wait for the specified input port contents to match the comparison
       tag bits with the specified logic.  The following limitations apply:

           The station must be in the range 0..4
           The port number must be in the range 01..99

       Bits are specified as an 8 byte string value and have the following
       meanings:

           .    Don't care
           1    Bit must be high
           0    Bit must be low

       So as an example, the string "110.0011" would match the values
       0x0c03 or 0x0d03.

       The logic values must be one of:

           AND  All non-"Don't care" must match
           OR   One or more non-"Don't care" bits must match

       When a match occurs, execution resumes at the next program step.
       This is generally used for part positioning using input sensors.
    """
    return ("IN",
            "STN=%1d" % stationNumber,
            "PN%02d=%s" % (portNumber, pattern),
            logic)

def copyInputToCounter(stationNumber, portNumber, counterNumber):
    """From the station designated by the station number, read the input
       value from the specified port number, and store it into the specified
       counter.  The following limitations apply:

           The station must be in the range 0..4
           The port number must be in the range 01..99
           The counter number must be in the range 01..99
    """
    return ("INPC",
            "STN=%1d" % stationNumber,
            "PN=%02d" % portNumber,
            "CN=%02d" % counterNumber)

def internalPortOutput(internalPortNumber, pattern):
    """For the designated internal port, set, clear, or leave unchanged the
       latched data pattern.  The following limitations apply:

           The internal port number must be in the range 1..9

       The bit values being latched are an 8 bit value; because it is
       possible to leave a bit unchanged, this command differs in
       semantics from other commands which use bit strings.

       Bits are specified as an 8 byte string value and have the following
       meanings:

           .    Leave the bit in the current state
           1    Bit is to be set high
           0    Bit is to be set low

       So for example, the bit string "1......0" means set bit 8 high,
       set bit 1 low, and leave bits 2..7 unchanged.

       Note: This command is normally used in conjunction with the
             internalPortInputWait() command in order to implement
             synchrnization between tasks, or to move a small amount of
             mailbox data between tasks.
    """
    return ("IOUT", "PN%1d=%s" % (internalPortNumber, pattern))

def internalPortInputWait(internalPortNumber, pattern, logic):
    """Wait for the specified internal port contents to match the comparison
       tag bits with the specified logic.  The following limitations apply:

           The station must be in the range 0..4
           The port number must be in the range 01..99

       Bits are specified as an 8 byte string value and have the following
       meanings:

           .    Don't care
           1    Bit must be high
           0    Bit must be low

       So as an example, the string "110.0011" would match the values
       0x0c03 or 0x0d03.

       The logic values must be one of:

           AND  All non-"Don't care" must match
           OR   One or more non-"Don't care" bits must match

       When a match occurs, execution resumes at the next program step.
       This is generally used for part positioning using input sensors.

       Note: This command is normally used in conjunction with the
             internalPortOutput() command in order to implement
             synchrnization between tasks, or to move a small amount of
             mailbox data between tasks.
    """
    return ("INSP", "PN%1d=%s" % (internalPortNumber, pattern), logic)

def jump(tagNumber):
    """Jump onconditionally to the specified tag."""
    return ("JMP", "TAG=%03d", tagNumber)

def jumpCounterConditional(tagNumber, counterNumber, operator, value):
    """Jump to the specified tag when the specified counter contents satisfy
       the comparison operator when compared to the value.  The following
       limitations apply:

           The tag must be in the range 001..999
           The counter number must be in the range 01..99
           The count value must be in the range 0000..9999

       The following operators are supported, and should be passed as string
       values:

           =    Compare for equality
           <    Compare for counter less than the value
           >    Compare for the counter greater than the value
           <=   Compare for the counter less than or equal to the value
           >=   Compare for the counter greater than or equal to the value

       There is no operator available for cmparison for inequality; instead,
       a compination of two comparisons is required.

       Note: This operation is normally used for loop control, but can also
             be used to synchronize tasks then performing multiple tasks,
             either simultaneously or sequentially.
    """
    return ("JMPC",
            "TAG=%03d" % tagNumber,
            "CN%02d%s" % (counterNumber, operator),
            "%04d" % value)

def jumpInputConditional(tagNumber, stationNumber, portNumber, pattern):
    """Jump to a tag number when the specified input port contents match
       the comparison tag bits.  The following limitations apply:

           The tag must be in the range 001..999
           The station must be in the range 0..4
           The port number must be in the range 00..99

       Bits are specified as an 8 byte string value and have the following
       meanings:

           .    Don't care
           1    Bit must be high
           0    Bit must be low

       So as an example, the string "110.0011" would match the values
       0x0c03 or 0x0d03.
    """
    return ("JMPI",
            "TAG=%03d" % tagNumber,
            "STN=%1d" % stationNumber,
            "PN%02d=%s" % (portNumber, pattern))

def jumpTimerConditional(gNumber, timerNumber, operator, value):
    """Jump to a tag number if the specified timer contents satisfy the
       comparison operator when compared to the value.  The following
       limitations apply:

           The tag must be in the range 001..999
           The timer number must be in the range 0..9
           The comparison value must be in the range 000.0..999.9

       The following operators are supported, and should be passed as string
       values:

           =    Compare for equality
           <    Compare for counter less than the value
           >    Compare for the counter greater than the value
           <=   Compare for the counter less than or equal to the value
           >=   Compare for the counter greater than or equal to the value

       There is no operator available for cmparison for inequality; instead,
       a compination of two comparisons is required.
    """
    return ("JMPT",
            "TAG=%03d" % tagNumber,
            "TN%1d%s" % (timerNumber, operator),
            "%05.01f" % value)

def moveCoordinates(moveAbsolute, x, y, z, rotation, constantSpeed,
                    velocityNumber, positionPoint):
    """Move the current robot position either relative to the home position
       to relative to the current position, on the x, y, z, and rotation
       axis, at either a constant axial speed or a constant linear speed,
       as determined by the velocity table entry, in order to either
       position it at a specific point or to pass it.  The following
       limitations apply:

           The moveAbsolue value must be True or False.

           The X, Y, Z, and rotational coordinates must be in the range
           -8000.00..+8000.00; in prace, this is limited further by
           servo limits.

           The constantSpeed parameter must be True or False.

           The velocityNumber must be in the range 00..10.

           The positionPoint value must be True or False.

       In practice, moveAbsolue and constantSpeed will typically be True.
    """
    return ("MOV",
            moveAbsoluteTable[moveAbsolute],
            "X=%s%07.02f" % _signSplit(x),
            "Y=%s%07.02f" % _signSplit(y),
            "Z=%s%07.02f" % _signSplit(z),
            "R=%s%07.02f" % _signSplit(rotation),
            axisConstantSpeedTable[constantSpeed],
            "V=%02d" % velocityNumber,
            postPassTable[positionPoint])

def movePoint(moveAbsolute, pointNumber, counterNumber, constantSpeed,
              velocityNumber, positionPoint):
    """Axis move to a point in the coordinate table.  Movement is either
       relative to the home position or relative to the current position.
       The position is relative to the contents of the counter number
       specified.  Motion is either a constant axial speed or a constant
       linear speed at a speed determined by the velocity table entry. The
       motion ends by passing or positioning to a specific point.  The
       following limitations apply:

           The moveAbsolue value must be True or False.

           The pointNumber must be in the range 000..999.

           The counterNumber must be in the range 00..99.

           The constantSpeed parameter must be True or False.

           The velocityNumber must be in the range 00..10.

           The positionPoint value must be True or False.
    """
    return ("MOVP",
            moveAbsoluteTable[moveAbsolute],
            "PT=%03d" % pointNumber,
            "CN=%02d" % counterNumber,
            axisConstantSpeedTable[constantSpeed],
            "V=%02d" % velocityNumber,
            postPassTable[positionPoint])

def moveBack(constantSpeed, velocityNumber, positionPoint):
    """Return to a previous point; the previous point can be an absolute
       or a relative move.  The move is carrierd out that the velocity
       specified by the velocity table number with the previous point
       being an absolute position or a pass point.  The following limitations
       apply:

           The constantSpeed value must be True or False.

           The velocityNumber must be in the range 00..10.

           The positionPoint value must be True or False.
    """
    return ("MVB",
            axisConstantSpeedTable[constantSpeed],
            "V=%02d" % velocityNumber,
            postPassTable[positionPoint])

def moveCircular(moveAbsolute, x, y, z, rotation, velocityNumber,
                 positionPoint):
    """A circular interpolation move through an absolute or relative
       coordinate point.  The positionPoint should be false when performing
       multiple operations consecutively to avoid a delay at the center
       point.  THe following limitations apply:

           The moveAbsolue value must be True or False.

           The velocityNumber must be in the range 00..10.

           The positionPoint value must be True or False.
    """
    return ("MVC",
            moveAbsoluteTable[moveAbsolute],
            "X=%s%07.02f" % _signSplit(x),
            "Y=%s%07.02f" % _signSplit(y),
            "Z=%s%07.02f" % _signSplit(z),
            "R=%s%07.02f" % _signSplit(rotation),
            "V=%02d" % velocityNumber,
            postPassTable[positionPoint])

def moveCircularPoint(moveAbsolute, pointNumber, counterNumber, velocityNumber,
                      positionPoint):
    """A circular interpolation move through an absolute or relative
       coordinate point.  The positionPoint should be false when performing
       multiple operations consecutively to avoid a delay at the center
       point.  THe following limitations apply:

           The moveAbsolue value must be True or False.

           The pointNumber must be in the range 000..999.

           The velocityNumber must be in the range 00..10.

           The positionPoint value must be True or False.
    """
    return ("MVCP",
            moveAbsoluteTable[moveAbsolute],
            "PT=%03d" % pointNumber,
            "CN=%02d" % counterNumber,
            "V=%02d" % velocityNumber,
            postPassTable[positionPoint])

def moveEscape(moveAbsolute, pointNumber, counterNumber, constantSpeed,
               velocityNumber):
    """When the escape move input signal is set following this instruction,
       the current motion is treated as completed.  iIn the absence of an
       escape signal, this is equivalent to movePoint().  The following
       limitations apply:

           The moveAbsolue value must be True or False.

           The pointNumber must be in the range 000..999.

           The counterNumber must be in the range 00..99.

           The constantSpeed parameter must be True or False.

           The velocityNumber must be in the range 00..10.
    """
    return ("MVE",
            moveAbsoluteTable[moveAbsolute],
            "PT=%03d" % pointNumber,
            "CN=%02d" % counterNumber,
            axisConstantSpeedTable[constantSpeed],
            "V=%02d" % velocityNumber)

def NOP():
    """No Operation."""
    return ("NOP")

def subReturn():
    """Return from the current subroutine (assumes a subroutine is currently
       being executed).
    """
    return ("RET")

def setSpeed(velocityNumber):
    """Set the current velocity table number in effect; the value supplied
       must be in the range 01..10.
    """
    return ("SPD", "V=%02d" % velocityNumber)

def stop():
    """Stop current program movement.  This is typically used when
       multitasking in order to temporarily halt the program flow.  The
       program flow can be restarted by issuing the appropriate exec
       command for the program, e.g. execStartSequential().
    """
    return ("STOP")

def setTag(tagNumber):
    """Set a tag; tags take up a program instruction, and are used for
       program flow control.  They must be in the range 001..999.
    """
    return ("TAG", "TAG=%03d" % tagNumber)

def taskCancel(taskNumber):
    """Forcibly terminate a task by task number.  The task number must be
       in the range 02..04.

       Note: Task 01 indicates the main task, and can not be cancelled;
             instead cancel all other tasks and then end().  For
             this reason, when multitasking, if 3 or fewer tasks are
             required, it might be useful to reserve task 01 as the
             control task and use an internal general input in order to
             notify it from one of the other tasks that it should do an
             orderly shutdown using taskCancel().
    """
    return ("TCAN", "TASK=%02d" % taskNumber)

def sleepInterval(interval):
    """Sleep the execution of the program for the specified period of
       time in tenths of seconds; the interfval must be in the range
       000.0..999.9.
    """
    return ("TIM", "TM=%05.01f" % interval)

def timerPreset(timerNumber, value):
    """Set the specified timer to an initial value.  The following
       limitations apply:

           The timer must be in the range 1..9.
           The timer value must be in the range 000.0..999.9.
    """
    return ("TIMP", "TN%d=%05.01f" % (timerNumber, value))

def taskRestart(taskNumber):
    """The designated task is restarted.  The task must be in the range
       of 01..04.
    """
    return ("TRSA", "TASK=%02d" % taskNumber)

def taskSuspend(taskNumber):
    """The designated task is temporarily suspended as if it had called
       stop() on itself, and may be later resumed with a call to
       taskRestart().  The task must be in the range of 01..04.
    """
    return ("TSTO", "TASK=%02d" % taskNumber)

def taskStart(taskNumber):
    """Start the designated task.  The task must be in the range 02..04;
       task 01 is started manually via the serial interface, or can be
       configured to start automatically on system startup.
    """
    return ("TSTR", "TASK=%02d" % taskNumber)

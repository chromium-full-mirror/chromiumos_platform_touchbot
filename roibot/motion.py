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
#
# This module defines more complex motion commands than the simple Jog is
# able to handle on its own, such as moving to a specified coordinate.  It
# also provides for barrier functions to allow for more coordinated
# operations among robots, or among multiple controolers in a single robot,
# which could be required if there are more than 4 degrees of freedom
# supported in a single robot with more than one CA10/CA20 controller.
#

import time
import roibot

xreadTimeoutError = roibot.ROIbotTimeoutException("Read timeout")
motionTimeoutError = roibot.ROIbotTimeoutException("Motion timeout")


axisToIndexTable = {
    "X" : 0,
    "Y" : 1,
    "Z" : 2,
    "R" : 3,
}


#
# Utility functions
#
def assertOneAxis(x, y, z, rotation):
    """Asserts that of 4 axes, one is non-"SP" and the other three are
       "SP".  This function is rather dumb in order to be rather quick,
       and does not provide sophisticated diagnostics on the precise
       use failure.

       If the assertion does not fail, the axis on which the motion will
       occur is returned as a string matching the robot report string."""
    count = 0
    if x != "SP":
        count = count + 1
        axis = "X=" + x
    if y != "SP":
        count = count + 1
        axis = "Y=" + y
    if z != "SP":
        count = count + 1
        axis = "Z=" + z
    if rotation != "SP":
        count = count + 1
        axis = "R=" + rotation
    if count != 1:
        raise roibot.ROIbotParameterException("assertOneAxis")
    return axis

#
# Implementation functions
#


def waitForCondition(roibot, conditionFunction, context, timeout, timeoutError):
    """This function is a barrier function which calls a condition function
       every 10ms until the condition is true or a timeout occurs.  If a
       timeout occurs, it raises the exception timeoutError.

       The timeout is in 10ms ticks."""
    for ms10 in xrange(int(timeout)):
        if conditionFunction(roibot, context):
            return
        time.sleep(.01)
    raise motionTimeoutError

#
# Waits with timeouts.  These functions are specified as conditional
# predicate functions to determine completion plus a wrapper to the
# external function which is expected as the interface.
#

# waitForExecution()
def condExecutionDone(roibot, context):
    """This condition function returns whether or not the robot is
       currently executing a command.  This is useful for self terminating
       operations which clear the execution bit on completion, such as
       returning all axes to their origin position."""
    report0 = roibot.modeRequestStatus(0)
    report0status1 = int(str(report0[1][1]).lstrip("ST1="),16)
    # still in execution?
    if report0status1 & 0x02:
        return False;
    return True

def waitForExecution(roibot, timeout=10000):
    """Delay until the currently executing operation has completed.

       The timeout is in 10ms ticks and defaults to 10000 (100 seconds)."""
    waitForCondition(roibot, condExecutionDone, 0, timeout, motionTimeoutError)

# waitOneAxis()
def condOneAxisDone(roibot, watchFor):
    """Check if the current position of the watchFor axis value is equal
       to the specified value, within some small fuzz factor to account
       for polling latency, since we can not request a move to an absolute
       coordinate."""
    fuzz = 6  # strongly timing dependent!!!
    axis, want = watchFor.split("=")
    want = float(want)
    axis = axisToIndexTable[axis]
    position = roibot.monRequestPresentPosition()
    offset = float(position[1][axis].split("=")[1])
    if abs(want - offset) < fuzz:
        return True
    return False

def waitOneAxis(roibot, x="SP", y="SP", z="SP", rotation="SP", timeout=10000):
    """Wait for a single axis to reach a location, as specified by the
       parameter.  Valid axis parameters are specified by
       a name/value pair parameter:

           <axis>=<+/->####.##

       Valid values for the <axis> element are:

            x           Move the X axis
            y           Move the Y axis
            z           Move the Z axis
            rotation    Move the rotational axis

       Values are absolute.  An optional timeout parameter may be specified;
       see waitForExecution() for details."""
    watchFor = assertOneAxis(x, y, z, rotation)
    waitForCondition(roibot, condOneAxisDone, watchFor, timeout,
                     motionTimeoutError)

#
# Explicit command operations
#
def moveOneAxis(roibot, x="SP", y="SP", z="SP", rotation="SP"):
    """Perform motion along one axis, specified by the parameter.  Only
       one axis may be moved.  Valid axis parameters are specified by
       a name/value pair parameter:

           <axis>=<+/->####.##

       Valid values for the <axis> element are:

            x           Move the X axis
            y           Move the Y axis
            z           Move the Z axis
            rotation    Move the rotational axis

       Values are absolute, and motion occurs regardless of the current
       axis values.

       This function is a blocking function, and will not return until the
       motion is completed or an error or stop condition occurs.
       """
    watchFor = assertOneAxis(x, y, z, rotation)
    axis = watchFor[0]
    want = float(watchFor.split("=")[1])
    position = roibot.monRequestPresentPosition()
    offset = float(position[1][axisToIndexTable[axis]].split("=")[1])

    if want < offset:
        direction = "-"
    else:
        direction = "+"

    jogX = waitX = "SP"
    jogY = waitY = "SP"
    jogZ = waitZ = "SP"
    jogR = waitR = "SP"
    if axis == "X":
        jogX = direction + "H"
    elif axis == "Y":
        jogY = direction + "H"
    elif axis == "Z":
        jogZ = direction + "H"
    elif axis == "R":
        jogR = direction + "H"

    if not roibot.execJog(jogX, jogY, jogZ, jogR):
        return False  # TODO:(tlambert) throw exception

    waitOneAxis(roibot, x, y, z, rotation)

    if not roibot.execJog("SP", "SP", "SP", "SP"):
        return False  # TODO(tlambert): throw exception

    return True

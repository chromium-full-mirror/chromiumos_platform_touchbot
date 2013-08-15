# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from position import Position
from profile import Profile
from touchbotcomm import TouchbotComm


class Touchbot:
    """ High level Touchbot control class

    This class hides the internals of communicating with the robot and
    offers high level robot control commands.
    """

    AXIS_Z = 1
    AXIS_SHOULDER = 2
    AXIS_ELBOW = 3
    AXIS_WRIST = 4
    AXIS_HAND = 5
    ALL_AXES_BUT_HAND = [AXIS_Z, AXIS_SHOULDER, AXIS_ELBOW, AXIS_WRIST]

    def __init__(self, ip_address, port):
        self.comm = TouchbotComm(ip_address, port)

    def CalibratePosition(self):
        """ Make the robot go limp and record its position after the operator
        moves it into the desired configuration.
        returns a Position object of the recorded posisition
        """
        successful = True
        for axis in Touchbot.ALL_AXES_BUT_HAND:
            response = self.FreeAxis(axis)
            if not response or response[0] != 0:
                successful = False
        if not successful:
            print 'There was an error entering free mode.'
            return None

        print 'Move the robot CAREFULLY to where you want it.'
        raw_input('Press "enter" to record that position.')

        response = self.UnFreeAxes()
        if not response or response[0] != 0:
            print 'There was an error leaving free mode.'
            return None

        return self.GetCurrentPosition()

    def FreeAxis(self, axis):
        """ Set a given axis into free mode, ie: make it go limp """
        if axis not in Touchbot.ALL_AXES_BUT_HAND:
            return None
        return self.comm.SendCmd('freemode', axis)

    def UnFreeAxes(self):
        """ Return all axes to computer control """
        return self.comm.SendCmd('freemode', -1)

    def GetCurrentPosition(self):
        """ Record the current position as a Position object """
        response = self.comm.SendCmd('where')
        if not response:
            return None
        error_code, data = response
        if error_code != 0:
            return None
        return Position.FromTouchbotResponse(data)

    def GetCurrentProfile(self):
        """ Get a copy of the current movement profile """
        error_code, data = self.comm.SendCmd('profile')
        return Profile.FromTouchbotResponse(data)

    def SetProfileData(self, profile):
        """ Replace the robot's current profile with this one """
        return self.comm.SendCmd('profile', str(profile))

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

    # Network connection parameters for the robot
    TOUCHBOT_IP_ADDR = '192.168.0.1'
    TOUCHBOT_PORT = 10100

    # Useful speeds for movement
    SPEED_VERY_SLOW = 1.0
    SPEED_SLOW = 5.0
    SPEED_MEDIUM = 10.0
    SPEED_FAST = 15.0
    SPEED_VERY_FAST = 20.0

    AXIS_Z = 1
    AXIS_SHOULDER = 2
    AXIS_ELBOW = 3
    AXIS_WRIST = 4
    AXIS_HAND = 5
    ALL_AXES_BUT_HAND = [AXIS_Z, AXIS_SHOULDER, AXIS_ELBOW, AXIS_WRIST]

    # GPIO addresses for the robot's fingers
    FINGER_FL = 16
    FINGER_BL = 15
    FINGER_BR = 14
    FINGER_FR = 13
    ALL_FINGERS = [FINGER_FL, FINGER_BL, FINGER_BR, FINGER_FR]

    # GPIO addresses for the nest close and open valves
    NEST_CLOSE_VALVE = 800013
    NEST_OPEN_VALVE = 800015

    # GPIO address for the fingertip detection sensor
    FINGERTIP_DETECT = 810005

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

    def GetGPIO(self, gpio_num):
        """ Get the value of a GPIO input from the robot """
        error_code, raw_data = self.comm.SendCmd('sig', gpio_num)
        if error_code == 0:
            return int(raw_data.split()[1])
        else:
            return None

    def SetGPIO(self, gpio_num, value):
        """ Set the value of a GPIO output on the robot """
        return self.comm.SendCmd('sig', gpio_num, value)

    def SetAngles(self, pos):
        """ Move the robot to pos by the raw joint angles """
        return self.comm.SendCmd('movej', pos.ax_1, pos.ax_2, pos.ax_3,
                                 pos.ax_4, pos.ax_5)
    def SetCartesian(self, pos):
        """ Move the robot to pos by Cartesian coordinates """
        return self.comm.SendCmd('movec', pos.x, pos.y, pos.z,
                                 pos.yaw, pos.pitch, pos.roll)

    def Wait(self):
        return self.comm.SendCmd('waitForEom')

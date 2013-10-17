# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import math
import time

from numpy import clip
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

    # How high above something to approach it from to be safe
    SAFETY_CLEARANCE = 40

    # Useful speeds for movement
    SPEED_VERY_SLOW = 1.0
    SPEED_SLOW = 5.0
    SPEED_MEDIUM = 10.0
    SPEED_FAST = 15.0
    SPEED_VERY_FAST = 20.0
    MAX_SPEED = 300.0

    # Limits on how far the robot hand can move the fingers in and out
    MIN_FINGER_DISTANCE = 15
    MAX_FINGER_DISTANCE = 140

    # How long it takes for the fingertip pistons to extend (in seconds)
    MINIMUM_FINGER_EXTENSION_TIME = 0.05

    # Setting for the accuracy (InRange) value of a profile
    BLEND_MOVEMENTS = -1
    ALWAYS_STOP = 0
    MAX_ACCURACY = 1

    # Settings for how to interpolate points (straight or curved)
    STRAIGHT_INTERPOLATION = -1
    JOINT_INTERPOLATION = 0

    # Indicies for adressing specific axes of the robot's arm
    AXIS_Z = 1
    AXIS_SHOULDER = 2
    AXIS_ELBOW = 3
    AXIS_WRIST = 4
    AXIS_HAND = 5
    ALL_AXES = [AXIS_Z, AXIS_SHOULDER, AXIS_ELBOW, AXIS_WRIST, AXIS_HAND]

    # GPIO addresses for the robot's fingers
    FINGER_BR = 16
    FINGER_FR = 15
    FINGER_FL = 14
    FINGER_BL = 13
    ALL_FINGERS = [FINGER_FR, FINGER_FL, FINGER_BL, FINGER_BR]

    # GPIO addresses for the nest close and open valves
    NEST_CLOSE_VALVE = 800013
    NEST_OPEN_VALVE = 800015

    # GPIO address for the fingertip detection sensor
    FINGERTIP_DETECT = 810005

    # Paths to pre-recorded Positions hovering above the nest
    NEST_POSITION_FILES = ['nest/size0.p', 'nest/size1.p',
                           'nest/size2.p', 'nest/size3.p']

    # Paths to pre-recorded Positions hovering above the fingertip detector
    FINGERTIP_DETECT_POSITION_FILES = ['detector/fingerfr.p',
                                       'detector/fingerfl.p',
                                       'detector/fingerbl.p',
                                       'detector/fingerbr.p']

    # It appears that the units are not exactly mm, but are scaled slightly
    # By scaling distances by this value the accuracy goes up dramatically
    DISTANCE_SCALING_FACTOR = 0.75


    def __init__(self, ip_address=TOUCHBOT_IP_ADDR, port=TOUCHBOT_PORT):
        self.comm = TouchbotComm(ip_address, port)

        self.nest_positions = [Position.FromPickledFile(filename)
                               for filename in Touchbot.NEST_POSITION_FILES]
        if not all(self.nest_positions):
            print 'WARNING: Some nest positions loaded incorrectly'

        self.fingertip_detect_positions = [Position.FromPickledFile(filename)
             for filename in Touchbot.FINGERTIP_DETECT_POSITION_FILES]
        if not all(self.fingertip_detect_positions):
            print 'WARNING: Some fingertip detector position loaded incorrectly'

        self.finger_size = -1
        self.SetFingerStates([0, 0, 0, 0])
        self.OpenNest()

    def CalibratePosition(self):
        """ Make the robot go limp and record its position after the operator
        moves it into the desired configuration.
        Returns a Position object of the recorded posisition.
        """
        successful = True
        response = self.FreeAxes()
        if not response or response[0] != 0:
            print 'There was an error entering free mode.'
            return None

        print 'Move the robot CAREFULLY to where you want it.'
        raw_input('Press "enter" to record that position.')

        response = self.UnFreeAxes()
        if not response or response[0] != 0:
            print 'There was an error leaving free mode.'
            return None

        return self.GetCurrentPosition()

    def FreeAxes(self):
        """ Set all axis into free mode, ie: make them go limp. """
        return self.comm.SendCmd('freemode', 0)

    def UnFreeAxes(self):
        """ Return all axes to computer control. """
        return self.comm.SendCmd('freemode', -1)

    def GetCurrentPosition(self):
        """ Record the current position as a Position object. """
        response = self.comm.SendCmd('where')
        if not response:
            return None
        error_code, data = response
        if error_code != 0:
            return None
        return Position.FromTouchbotResponse(data)

    def GetCurrentProfile(self):
        """ Get a copy of the current movement profile. """
        error_code, data = self.comm.SendCmd('profile')
        return Profile.FromTouchbotResponse(data)

    def SetProfileData(self, profile):
        """ Replace the robot's current profile with this one. """
        return self.comm.SendCmd('profile', str(profile))

    def GetGPIO(self, gpio_num):
        """ Get the value of a GPIO input from the robot. """
        error_code, raw_data = self.comm.SendCmd('sig', gpio_num)
        if error_code == 0:
            return int(raw_data.split()[1])
        else:
            return None

    def SetGPIO(self, gpio_num, value):
        """ Set the value of a GPIO output on the robot. """
        return self.comm.SendCmd('sig', gpio_num, value)

    def SetAngles(self, pos, blocking=True):
        """ Move the robot to pos by the raw joint angles. """
        response = self.comm.SendCmd('movej', pos.ax_1, pos.ax_2, pos.ax_3,
                                     pos.ax_4, pos.ax_5)
        if blocking:
            self.Wait()
        return response

    def SetCartesian(self, pos, finger_distance=None, blocking=True):
        """ Move the robot to pos by Cartesian coordinates. """
        # If a finger spacing has been specified add that to the movement
        # command.  The finger spacing motors were added as an additional axis
        # so are not controlled by the 'movec' command by default.  They must
        # be specified before with the 'moveExtraAxis' command, and then are
        # moved when the robot receives the next 'movec.'
        if finger_distance:
            finger_distance = clip(finger_distance,
                                   Touchbot.MIN_FINGER_DISTANCE,
                                   Touchbot.MAX_FINGER_DISTANCE)
            adjusted_dist = finger_distance * Touchbot.DISTANCE_SCALING_FACTOR
            self.comm.SendCmd('moveExtraAxis', adjusted_dist)

        response = self.comm.SendCmd('movec', pos.x, pos.y, pos.z,
                                     pos.yaw, pos.pitch, pos.roll)
        if blocking:
            self.Wait()
        return response

    def Wait(self):
        return self.comm.SendCmd('waitForEom')

    def _AddSafetyClearance(self, pos):
        new_pos = copy.deepcopy(pos)
        new_pos.ax_1 += Touchbot.SAFETY_CLEARANCE
        return new_pos

    def _ManipulateFingers(self, size, should_keep_fingers):
        """ Either attach or detach all four fingers. """
        if size < 0 or size > len(self.nest_positions):
            return False

        nest_pos = self.nest_positions[size]
        above_nest_pos = self._AddSafetyClearance(nest_pos)

        self.OpenNest()
        response = self.SetAngles(above_nest_pos)
        if not response or response[0] != 0:
            print 'Error getting into position for size %d fingertips' % size
            return False
        self.SetAngles(nest_pos)

        self.SetFingerStates([1, 1, 1, 1])

        if should_keep_fingers:
            self.finger_size = size
        else:
            time.sleep(1)
            self.CloseNest()
            self.finger_size = -1

        time.sleep(1)
        self.SetFingerStates([0, 0, 0, 0])
        self.SetAngles(above_nest_pos)
        self.OpenNest()
        return True

    def DetectFingertips(self):
        """ Check the state of the fingertips -- see if they're connected. """
        states = []
        for pos in self.fingertip_detect_positions:
            self.SetAngles(pos)
            states.append(self.GetGPIO(Touchbot.FINGERTIP_DETECT) != 0)
        return states

    def GetFingertips(self, size):
        """ Pick up all four fingertips of a given size."""
        if not self._ManipulateFingers(size, should_keep_fingers=True):
            return False
        fingertips_present = self.DetectFingertips()
        return all(fingertips_present)

    def DropFingertips(self):
        """ Put the currently attached finger tips back in the nest. """
        if not self._ManipulateFingers(self.finger_size,
                                       should_keep_fingers=False):
            return False
        fingertips_present = self.DetectFingertips()
        return not all(fingertips_present)

    def SetFingerStates(self, states):
        """ Control which fingers are extended and which are retracted. """
        for finger, state in zip(Touchbot.ALL_FINGERS, states):
            self.SetGPIO(finger, state)

    def FingerStates(self):
        """ See which fingers are extended and which are retracted. """
        return [self.GetGPIO(finger) for finger in Touchbot.ALL_FINGERS]

    def OpenNest(self):
        """ Open the nest to allow fingertips to pass in and out. """
        self.SetGPIO(Touchbot.NEST_CLOSE_VALVE, 0)
        self.SetGPIO(Touchbot.NEST_OPEN_VALVE, 1)

    def CloseNest(self):
        """ Close the nest to keep fingertips from leaving. """
        self.SetGPIO(Touchbot.NEST_CLOSE_VALVE, 1)
        self.SetGPIO(Touchbot.NEST_OPEN_VALVE, 0)

    def IsLegalSpeed(self, speed):
        """ Is a speed an acceptable value for this robot """
        return speed > 0.0 and speed < Touchbot.MAX_SPEED

    def IsLegalRelativeCoordinate(self, coords):
        """ Are the x and y values between 0 and 1 """
        if len(coords) != 2:
            return False
        x, y = coords
        return -0.05 <= x <= 1.05 and -0.05 <= y <= 1.05

    def IsLegalFingerList(self, fingers):
        """ Check that a finger selection list is legal """
        return (len(fingers) == len(Touchbot.ALL_FINGERS) and
                all([bool(f in [0, 1]) for f in fingers]))

    def CenterIfSingleFinger(self, fingers, abs_pos, finger_distance):
        """ Offset them if only 1 finger is down (you're on your own for >1
        finger) This way the *finger* itself will be centered at the point,
        not the point where all the fingers meet.
        """
        if len(fingers) == 4 and sum(fingers) == 1:
            # Find which finger is down and how many degrees off center it is
            finger_index = fingers.index(1)
            finger_angle_offset = (90 * finger_index) - 45

            # Shift the x and y accordingly for both points in the line
            angle = math.radians(abs_pos.yaw + finger_angle_offset)
            abs_pos.x += math.cos(angle) * finger_distance / 2.0
            abs_pos.y += math.sin(angle) * finger_distance / 2.0

        return abs_pos

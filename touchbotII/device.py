# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import pickle

from position import Position


class Device:
    """ This is a class to represent the details of a given device
    that the robot will interact with.

    A device object is instantiated by giving it the file path of
    a pickled "device.p" file.  It loads in the contents and then
    uses that to perform transforms on the data so that the touchbot
    may adjust the points to where the touchpad actually is.

    Usage:
        # Two points in relative (0.0 to 1.0 scale) coordinates
        relative_p1 = (0.1, 0.1)
        relative_p2 = (0.9, 0.9)
        # Load the device details
        d = Device('./lumpy.p')
        # Convert the relative coordinates to ones you can tell the bot
        abs_p1 = d.RelativePosToAbsolutePos(relative_p1)
        abs_p2 = d.RelativePosToAbsolutePos(relative_p2)
        # Send the converted points directly as movements
        bot.SetAngles(abs_p1)
        bot.SetAngles(abs_p2)
    """
    def __init__(self, device_file):
        self.device_data = None
        with open(device_file, 'r') as fo:
            self.device_data = pickle.load(fo)
            self.tr = self.device_data['top right']
            self.tl = self.device_data['top left']
            self.bl = self.device_data['bottom left']
            self.br = self.device_data['bottom right']

    def __InterpolateValue(self, v1, v2, ratio):
        """ Linearly interpolate between v1 and v2 """
        return (1.0 - ratio) * v1 + ratio * v2

    def __InterpolatePosition(self, p1, p2, ratio):
        """ Linearly interpolate all values in two positions """
        return Position(self.__InterpolateValue(p1.x, p2.x, ratio),
                        self.__InterpolateValue(p1.y, p2.y, ratio),
                        self.__InterpolateValue(p1.z, p2.z, ratio),
                        self.__InterpolateValue(p1.roll, p2.roll, ratio),
                        self.__InterpolateValue(p1.pitch, p2.pitch, ratio),
                        self.__InterpolateValue(p1.yaw, p2.yaw, ratio),
                        self.__InterpolateValue(p1.ax_1, p2.ax_1, ratio),
                        self.__InterpolateValue(p1.ax_2, p2.ax_2, ratio),
                        self.__InterpolateValue(p1.ax_3, p2.ax_3, ratio),
                        self.__InterpolateValue(p1.ax_4, p2.ax_4, ratio),
                        self.__InterpolateValue(p1.ax_5, p2.ax_5, ratio))

    def RelativePosToAbsolutePos(self, rel_p, angle=None):
        """ Convert from relative (0.0->1.0 scaled) coordinates to absolute
        values for this device.
        """
        rel_x, rel_y = rel_p
        ptop = self.__InterpolatePosition(self.tl, self.tr, rel_x)
        pbot = self.__InterpolatePosition(self.bl, self.br, rel_x)
        abs_p = self.__InterpolatePosition(ptop, pbot, rel_y)
        if angle is not None:
            abs_p.yaw = angle
        return abs_p

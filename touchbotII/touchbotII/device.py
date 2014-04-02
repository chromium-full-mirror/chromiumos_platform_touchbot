# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import pickle
import sys

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

    If this script is run from the command line it will take in a device spec
    as an argument, compute the width and height of the touchpad and print them
    This is useful so you can figure out what relative coordinates you need if
    you want the fingers to be a fixed, absolute distance apart.
    The dimensions are returned in millimeters.

    Usage:
        localhost ~ # python device.py link.p
        68.1363218184 102.914542215
    """
    def __init__(self, device_file):
        self.device_data = None
        with open(device_file, 'r') as fo:
            self.device_data = pickle.load(fo)
            self.tr = self.device_data['corners']['top right']
            self.tl = self.device_data['corners']['top left']
            self.bl = self.device_data['corners']['bottom left']
            self.br = self.device_data['corners']['bottom right']
            self.click_z = self.device_data['click_z']

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

    def RelativePosToAbsolutePos(self, rel_p, angle=None, is_click=False):
        """ Convert from relative (0.0->1.0 scaled) coordinates to absolute
        values for this device.
        """
        rel_x, rel_y = rel_p
        ptop = self.__InterpolatePosition(self.tl, self.tr, rel_x)
        pbot = self.__InterpolatePosition(self.bl, self.br, rel_x)
        abs_p = self.__InterpolatePosition(ptop, pbot, rel_y)
        if angle is not None:
            abs_p.yaw += angle

        if is_click:
            abs_p.z = abs_p.ax_1 = self.click_z
        return abs_p

    def __Distance(self, pos1, pos2):
        dx = pos1.x - pos2.x
        dy = pos1.y - pos2.y
        return (dx * dx + dy * dy) ** 0.5

    def DeviceHeight(self):
        heights = [];
        for x in [0.0, 1.0]:
            p1 = self.RelativePosToAbsolutePos((x, 0.0))
            p2 = self.RelativePosToAbsolutePos((x, 1.0))
            heights.append(self.__Distance(p1, p2))
        return (heights[0] + heights[1]) / 2.0

    def DeviceWidth(self):
        widths = [];
        for y in [0.0, 1.0]:
            p1 = self.RelativePosToAbsolutePos((0.0, y))
            p2 = self.RelativePosToAbsolutePos((1.0, y))
            widths.append(self.__Distance(p1, p2))
        return (widths[0] + widths[1]) / 2.0

if __name__ == '__main__':
    try:
        device = Device(sys.argv[1])
    except:
        print 'Usage: %s device.p' % __file__
        sys.exit(1)

    print device.DeviceHeight(), device.DeviceWidth()

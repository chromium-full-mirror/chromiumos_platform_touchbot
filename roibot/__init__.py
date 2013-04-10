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
# See README.philosophy for why this file exists/is as it is.
#

import os
import pickle
import error
import motion
import program
from roibot import *


class BoundingVolume:
    """This class represents the area in which a touchpad is.  It loads the data
    from a manually generated pickled file, and presents it to the script in
    a simpler format instead of having to remember all the matrix indices.
    """

    # How much room to give when lifting the finger off the touchpad (in mm)
    TOUCHPAD_CLEARANCE = 15

    # The offsets from the calibrated z value and the tap and click z's
    TAP_Z_OFFSET = 0
    CLICK_Z_OFFSET = 3

    def __init__(self, device):
        exec 'from devices.%s import bounds' % device
        self.bounds = bounds
        if os.path.isfile('calibrated_dimensions.py'):
            from calibrated_dimensions import z, calibrated_device
            if calibrated_device == device:
                print 'Calibrated values for %s found' % device
                self.bounds['paperZ'] = z
                self.bounds['tapZ'] = z + self.TAP_Z_OFFSET
                self.bounds['clickZ'] = z + self.CLICK_Z_OFFSET

    def minX(self):
        return self.bounds['minX']

    def maxX(self):
        return self.bounds['maxX']

    def minY(self):
        return self.bounds['minY']

    def maxY(self):
        return self.bounds['maxY']

    def upZ(self):
        return self.bounds['paperZ'] - self.TOUCHPAD_CLEARANCE

    def paperZ(self):
        return self.bounds['paperZ']

    def tapZ(self):
        return self.bounds['tapZ']

    def clickZ(self):
        return self.bounds['clickZ']

    def keyCoordinates(self, key):
        if self.bounds.get('keys'):
            return self.bounds['keys'].get(key)
        return None

    def convert(self, touchpad_x, touchpad_y):
        """Take a set of coordinates on the touchpad and convert them into the
        robot's view. Since the touchpad is rotated 90 degrees from the
        touchpad, the x and y coordinates are switched and then the values are
        scaled to fit the bounds of this specific touchpad

        The touchpad coordinates are to be specified in the range from 0.0-1.0
        Refer to the diagram of the touchpad below to specify any points.
             ____________
            |1          2|
            |  touchpad  |
            |            |
            |3__________4|

            1: (0.0, 0.0)
            2: (1.0, 0.0)
            3: (0.0, 1.0)
            4: (1.0, 1.0)
        """
        range_y = self.maxY() - self.minY()
        range_x = self.maxX() - self.minX()
        robot_x = self.maxX() - float(touchpad_y) * range_x
        robot_y = self.maxY() - float(touchpad_x) * range_y

        return  robot_x, robot_y

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
    # TODO(charliemooney) Reimplement device files as something less cryptic
    def __init__(self, device):
        path = device + ".pp"
        path = os.path.join(os.path.dirname(__file__), "devices", path)
        self.deviceRange = pickle.load(open(path, "r"))

    def minX(self):
        return self.deviceRange[0][0]

    def maxX(self):
        return self.deviceRange[0][1]

    def minY(self):
        return self.deviceRange[1][0]

    def maxY(self):
        return self.deviceRange[1][1]

    def upZ(self):
        # TODO(charliemooney@) Get rid of magic number (touchpad clearance)
        return self.paperZ() - 15

    def paperZ(self):
        return self.deviceRange[2][0]

    def clickZ(self):
        return self.deviceRange[2][1]

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

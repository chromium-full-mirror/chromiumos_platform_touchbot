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

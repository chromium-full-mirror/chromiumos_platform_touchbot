# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

from collections import namedtuple

from device import Device
from position import Position
from profile import Profile
from touchbot import Touchbot
from touchbotcomm import TouchbotComm

sys.path.append(os.path.dirname(os.path.realpath(__file__)))

PositionArg = namedtuple('Position', ['x', 'y', 'angle', 'finger_distance'])

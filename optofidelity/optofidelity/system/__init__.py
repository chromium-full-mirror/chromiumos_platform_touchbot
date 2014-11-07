# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Classes to manage and operate multiple OptoFidelity robots.

The classes in this module build a tree with a root of OptofidelityTestSystem,
which contains DeviceUnderTests. Whereas each DeviceUnderTest contains
multiple TestApps and a TestApp can have multiple pages.

During the calibration phase, the robot will automatically detect how to access
all those apps and pages, and access the high speed camera to calibrate the
screen location in the camera space. All this calibration data can then be
stored and read from a file to skip the lengthy calibration process.
"""
from optofidelity.system.util import DUTException, RetryFunction
from optofidelity.system.system import OptofidelityTestSystem
from optofidelity.system.calibration import CameraCalibration
from optofidelity.system.app import TestApp, ClankTestApp
from optofidelity.system.dut import DeviceUnderTest, AndroidDUT

OptofidelityTestSystem.RegisterDUTClass(AndroidDUT)
OptofidelityTestSystem.RegisterAppClass(ClankTestApp)
# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Classes to operate touch devices on the Optofidelity robot.

This package is responsible to navigate devices via the Optofidelity robot,
perform gestures on them and record these interactions using a high speed
camera.

The main entry point for this package is the BenchmarkSystem class, and a list
of BenchmarkSubject objects. Each subject has a reference to a HighSpeedCamera
object to allow the recording of interactions.
"""
from .backend import DUTBackend, RobotBackend
from .camera import HighSpeedCamera
from .navigator import Navigator
from .subject import BenchmarkSubject
from .system import BenchmarkSystem
from .updater import Updater

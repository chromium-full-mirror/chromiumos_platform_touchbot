# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Classes for detecting objects in video streams of the OptoFidelity robot.

This module is to be used on a video recording from the OptoFidelity robot
working on a touchscreen. It allows the detection of the touchscreen, the
robot finger as well as the detection of a line being drawn on the screen.

For the purpose of latency measurements, the line and screen detection also
accurately detects the frame when an updated frame is being drawn on the
screen.
"""
from optofidelity.detection.finger import Finger
from optofidelity.detection.detector import Frame, Video
from optofidelity.detection.line import Line
from optofidelity.detection.screen import ScreenFlash, TestArea
from optofidelity.detection.trace import Trace, Event
from optofidelity.detection.processor import VideoProcessor

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Classes for detecting objects in video streams of the OptoFidelity robot.

The basis for this package is the Detector class from which multiple detectors
derive. Each detector's  purpose is to process video frames and extract Events
which are consolidated in a Trace class.

These traces can then later be processed to calculate latencies.
"""
from optofidelity.detection.finger import FingerMove, FingerLED
from optofidelity.detection.detector import Frame, Video
from optofidelity.detection.line import Line
from optofidelity.detection.screen import ScreenFlash
from optofidelity.detection.trace import Trace, Event
from optofidelity.detection.processor import (VideoProcessor,
                                              MultithreadedVideoProcessor,
                                              ProcessorDebugger)

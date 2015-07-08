# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for FingerDetector."""

import numpy as np

from optofidelity.detection._finger_detector import FingerDetector
from optofidelity.detection.events import FingerEvent

from .test_detector import DetectorTest


class FingerDetectorTest(DetectorTest):

  def testPreprocessing(self):
    frame = self.calibratedFrame("finger.png")
    location = FingerDetector().Preprocess(frame, None)
    delta = np.abs(location - 35.5)
    self.assertLess(delta, 1)


  def testEventGeneration(self):
    location_sequence = np.asarray([
        10.0,
        11.0,
        12.0,
        50.0,    # Spurious jump that should be ignored
        13.0,
        None,  # Not detected in this frames
        14.0,
        14.0,    # Movement stopped. Should not report new events
        14.0,
        15.0
    ])
    # Dictionary of which event is expected at which time
    expected_events = {
        0: FingerEvent(time=0, location=10.0),
        1: FingerEvent(time=1, location=11.0),
        2: FingerEvent(time=2, location=12.0),
        4: FingerEvent(time=4, location=13.0),
        6: FingerEvent(time=6, location=14.0),
        9: FingerEvent(time=9, location=15.0)
    }

    # Test if series of profiles generates expected events.
    self.assertExpectedEventsGenerated(FingerDetector(),
                                       location_sequence, expected_events)

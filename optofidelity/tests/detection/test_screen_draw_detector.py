# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for ScreenDrawDetector."""
import numpy as np

from optofidelity.detection._screen_draw_detector import ScreenDrawDetector
from optofidelity.detection.events import ScreenDrawEvent

from .test_detector import DetectorTest


class ScreenDrawDetectorTest(DetectorTest):
  def testPreProcessing(self):
    frame = self.calibratedFrame("screen_draw.png")
    min_color, max_color = ScreenDrawDetector().Preprocess(frame, None)
    self.assertLess(min_color, 0.01)
    self.assertGreater(max_color, 0.99)

  def testEventGeneration(self):
    minmax_sequence = [
        # 0: Screen draw fading in
        (0, 0),
        (0, 0.2),
        (0.2, 0.8),
        (0.8, 1.0),
        (1.0, 1.0),
        # 5: Screen draw fading out
        (1.0, 1.0),
        (0.8, 1.0),
        (0.2, 0.8),
        (0, 0.2),
        (0, 0),
    ]
    # Dictionary of expected events.
    BLACK = ScreenDrawEvent.STATE_BLACK
    WHITE = ScreenDrawEvent.STATE_WHITE
    expected_events = [
        ScreenDrawEvent(time=4, start_time=1, state=WHITE),
        ScreenDrawEvent(time=9, start_time=6, state=BLACK),
    ]

    self.assertExpectedEventsGenerated(ScreenDrawDetector(),
                                       minmax_sequence, expected_events)
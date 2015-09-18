# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for LineDetector."""
import numpy as np

from optofidelity.detection._line_detector import LineDetector
from optofidelity.detection.events import LineDrawEvent

from .test_detector import DetectorTest


class LineDetectorTest(DetectorTest):
  def testPreProcessing(self):
    frame = self.calibratedFrame("line.png")
    profile = LineDetector().Preprocess(frame, None)
    expected = [0, 0, 0, 0,
                0, 0.75, 1, 1,
                1, 1, 1, 1,
                1, 1, 0]
    every_40th_entry = profile[0:-1:40]
    diff = np.abs(expected - every_40th_entry)
    self.assertLess(np.max(diff), 0.1)

  def testEventGeneration(self):
    profile_sequence = np.asarray([
        # 0: Start empty
        [ 0,  0,  0,  0,  0,  0,  0,  0],
        # 1: Line Fading in
        [ 0, .5, .5,  0,  0,  0,  0,  0],
        [ 0,  1,  1,  0,  0,  0,  0,  0],
        [ 0,  1,  1,  0,  0,  0,  0,  0],
        # 4: New segment
        [ 0,  1,  1, .1, .1,  0,  0,  0],
        [ 0,  1,  1, .5, .5,  0,  0,  0],
        [ 0,  1,  1,  1,  1,  0,  0,  0],
        [ 0,  1,  1,  1,  1,  0,  0,  0],
        # 8: New segment
        [ 0,  1,  1,  1,  1, .1, .1,  0],
        [ 0,  1,  1,  1,  1, .5, .5,  0],
        [ 0,  1,  1,  1,  1,  1,  1,  0],
        [ 0,  1,  1,  1,  1,  1,  1,  0],
        # 12: line reset
        [ 0, .8, .8, .8, .8,  0,  0,  0],
        [ 0, .1, .1, .1, .1,  0,  0,  0],
        [ 0,  0,  0,  0,  0,  0,  0,  0],
    ])
    # stretch by repeating each value 10 times.
    profile_sequence = np.repeat(profile_sequence, 10, axis=1)

    # Dictionary of expected events.
    expected_events = [
        LineDrawEvent(time=6, location=49.0, start_time=4),
        LineDrawEvent(time=10, location=69.0, start_time=8),
        LineDrawEvent(time=13, location=None, start_time=13),
    ]

    # Test if series of profiles generates expected events.
    self.assertExpectedEventsGenerated(LineDetector(),
                                       profile_sequence, expected_events)

    # Mirror the profiles and, match up the expected location and run again.
    # The algorithm should work in both directions
    profile_sequence = np.fliplr(profile_sequence)
    for v in expected_events:
        if v.location is not None:
            v.location = profile_sequence.shape[1] - v.location

    self.assertExpectedEventsGenerated(LineDetector(),
                                       profile_sequence, expected_events)

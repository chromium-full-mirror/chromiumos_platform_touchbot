# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Abstract base class for all detector tests."""

from unittest import TestCase

from optofidelity.detection._calibrated_frame import CalibratedFrame
from optofidelity.detection.screen_calibration import ScreenCalibration

from . import test_data


class DetectorTest(TestCase):
  def calibratedFrame(self, image_name, prev_image_name=None):
    calib = ScreenCalibration(test_data.CalibrationBlackImage(),
                              test_data.CalibrationWhiteImage())
    image = test_data.LoadImage(image_name)
    prev_image = None
    if prev_image_name:
        prev_image = test_data.LoadImage(prev_image_name)
    return CalibratedFrame(image, prev_image, calib, 0)

  def uncalibratedFrame(self, image_name, prev_image_name=None):
    image = test_data.LoadImage(image_name)
    prev_image = None
    if prev_image_name:
        prev_image = test_data.LoadImage(prev_image_name)
    return CalibratedFrame(image, prev_image, None, 0)

  def assertExpectedEventsGenerated(self, detector, data_sequence,
                                    expected_events, print_only=False):
    for i, data in enumerate(data_sequence):
      events = detector.GenerateEvents(data, i, None)
      if print_only:
        print i, events
        continue
      if i in expected_events:
        self.assertEqual(len(events), 1)
        expected = expected_events[i]
        event = events[0]

        self.assertAlmostEqual(event.location, expected.location)
        self.assertEqual(event.time, expected.time)
        self.assertEqual(event.start_time, expected.start_time)
        self.assertEqual(event.state, expected.state)
      else:
        self.assertEqual(len(events), 0)

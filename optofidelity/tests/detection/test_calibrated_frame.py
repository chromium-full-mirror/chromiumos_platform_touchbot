# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for CalibratedFrame."""

from unittest import TestCase

import numpy as np

from optofidelity.detection._calibrated_frame import CalibratedFrame
from optofidelity.detection.screen_calibration import ScreenCalibration

from . import test_data


class CalibratedFrameTest(TestCase):
  def testCalibratedFields(self):
    prev_frame = test_data.CalibrationBlackImage()
    frame = test_data.CalibrationWhiteImage()
    calibration = ScreenCalibration(prev_frame, frame)
    calibrated_frame = CalibratedFrame(frame, prev_frame, calibration, 0)

    self.assertTrue(np.allclose(calibrated_frame.screen_space_normalized, 1))
    self.assertTrue(np.all(calibrated_frame.screen_space_foreground == False))

    self.assertEqual(calibrated_frame.camera_space_shape, (720, 1280))
    self.assertEqual(calibrated_frame.screen_space_shape, (322, 566))

  def testDelta(self):
    prev_frame = test_data.CalibrationBlackImage()
    frame = test_data.CalibrationWhiteImage()
    calibrated_frame = CalibratedFrame(frame, prev_frame, None, 0)

    calibration = ScreenCalibration(prev_frame, frame)
    delta = calibrated_frame.camera_space_delta
    screen_space_delta = calibration.CameraToScreenSpace(delta)

    self.assertTrue(np.all(screen_space_delta > 0.5))

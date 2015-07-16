# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for ScreenCalibration."""
from unittest import TestCase
import cPickle as pickle

import numpy as np

from optofidelity.detection.screen_calibration import ScreenCalibration
from optofidelity.videoproc import DebugView

from . import test_data


class ScreenCalibrationTests(TestCase):
  def createCalibration(self):
    return ScreenCalibration(test_data.CalibrationBlackImage(),
                             test_data.CalibrationWhiteImage())

  def assertCalibrationIsConsistent(self, calibration):
    # Should not throw any exceptions on validation
    calibration.Validate()

    # Check reference images. They should be mostly homogeneus
    avg_white = np.mean(calibration.white_reference)
    avg_black = np.mean(calibration.black_reference)
    max_white_deviation = np.max(calibration.white_reference - avg_white)
    max_black_deviation = np.max(calibration.black_reference - avg_black)
    self.assertLess(np.abs(max_white_deviation), 0.1)
    self.assertLess(np.abs(max_black_deviation), 0.1)

  def testCalibrationFromImages(self):
    calibration = self.createCalibration()
    self.assertCalibrationIsConsistent(calibration)

  def testCalibrationFromVideo(self):
    with test_data.CalibrationVideo() as video_reader:
      calibration = ScreenCalibration.FromScreenFlashVideo(video_reader)
      self.assertCalibrationIsConsistent(calibration)

  def testCalibrationIssue(self):
    for filename in ("calibration_issue_1.avi", ):
      with test_data.LoadVideo(filename) as video_reader:
        calibration = ScreenCalibration.FromScreenFlashVideo(video_reader)
        self.assertCalibrationIsConsistent(calibration)

  def testCompactPickling(self):
    before = self.createCalibration()
    pickled = pickle.dumps(before, protocol=2)

    # pickled data should be less than 15MB, just enough for the
    # black and white frame.
    self.assertLess(len(pickled),  15 * 1024 * 1024)
    after = pickle.loads(pickled)

    self.assertTrue(np.allclose(before.black_reference, after.black_reference))
    self.assertTrue(np.allclose(before.white_reference, after.white_reference))

  def testNormalization(self):
    calibration = self.createCalibration()
    black_screen_space = calibration.CameraToScreenSpace(
            test_data.CalibrationBlackImage())
    white_screen_space = calibration.CameraToScreenSpace(
            test_data.CalibrationWhiteImage())
    black_normalized = calibration.NormalizeFrame(black_screen_space)
    white_normalized = calibration.NormalizeFrame(white_screen_space)

    self.assertTrue(np.allclose(black_normalized, 0))
    self.assertTrue(np.allclose(white_normalized, 1))

  def testPWMCalibration(self):
    calib = ScreenCalibration.FromScreenFlashVideo(
        test_data.LoadVideo("pwm_calibration.avi"))
    self.assertCalibrationIsConsistent(calib)

  def testStabilization(self):
    self.skipTest("Manual verification required.")
    calib = ScreenCalibration(test_data.LoadImage("stabilization_black.png"),
                              test_data.LoadImage("stabilization_white.png"))
    img1 = test_data.LoadImage("stabilization_1.png")
    calib.StabilizeFrame(img1, debug=True)

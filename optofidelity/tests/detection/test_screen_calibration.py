# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for ScreenCalibration."""
from unittest import TestCase
import cPickle as pickle

import numpy as np
import cv2
from optofidelity.detection.screen_calibration import ScreenCalibration
from optofidelity.videoproc import DebugView
from tests.config import CONFIG
from . import test_data


class ScreenCalibrationTests(TestCase):
  def createCalibration(self):
    return ScreenCalibration(test_data.CalibrationBlackImage(),
                             test_data.CalibrationWhiteImage())

  def assertCalibrationIsConsistent(self, calibration):
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

  def testLowBrightnessCalibration(self):
    with test_data.LoadVideo("calibration_1.avi") as video_reader:
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

  def testPWMCalibration1(self):
    video = test_data.LoadVideo("pwm_calibration.avi")
    calibration = ScreenCalibration.FromScreenFlashVideo(video)

    self.verifyPWMCalibration(video, calibration)

  def testPWMCalibration2(self):
    video = test_data.LoadVideo("pwm_calibration_2.avi")
    calibration = ScreenCalibration.FromScreenFlashVideo(video)
    self.verifyPWMCalibration(video, calibration)

  def verifyPWMCalibration(self, video, calibration):
    self.assertIsNotNone(calibration.pwm_profile)
    if not CONFIG.get("user_interaction"):
      return

    screen_space = calibration.CameraToScreenSpace(video.FrameAt(127))
    normalized = calibration.NormalizeFrame(screen_space, debug=True,
                                            pwm_compensation=True)

    for i, frame in video.Frames():
      screen_space = calibration.CameraToScreenSpace(frame)
      normalized = calibration.NormalizeFrame(screen_space,
                                              pwm_compensation=True)
      print i
      cv2.imshow("PWM Calibration", normalized)
      cv2.waitKey()

  def testStabilization(self):
    self.skipTest("Manual verification required.")
    calib = ScreenCalibration(test_data.LoadImage("stabilization_black.png"),
                              test_data.LoadImage("stabilization_white.png"))
    img1 = test_data.LoadImage("stabilization_1.png")
    calib.StabilizeFrame(img1, debug=True)

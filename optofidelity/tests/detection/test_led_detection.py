# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for LEDDetector."""

import numpy as np

from optofidelity.detection._led_detector import Flash, LEDDetector
from optofidelity.detection.events import LEDEvent
from optofidelity.detection.screen_calibration import ScreenCalibration

from . import test_data
from .test_detector import DetectorTest


class LEDDetectorTest(DetectorTest):
  def executeLEDPreprocessingTest(self, on_image, off_image):
    def assertLEDFlash(flashes, off_to_on):
      self.assertGreater(len(flashes), 0)
      for flash in flashes:
        if off_to_on:
          self.assertGreater(flash.color, 0)
        else:
          self.assertLess(flash.color, 0)

    frame = self.uncalibratedFrame(on_image, off_image)

    flashes = LEDDetector().Preprocess(frame, None)
    assertLEDFlash(flashes, True)

    frame = self.uncalibratedFrame(off_image, on_image)
    flashes = LEDDetector().Preprocess(frame, None)
    assertLEDFlash(flashes, False)

  def executeFalsePositiveTest(self, on_image, off_image, black_image=None,
                               white_image=None):
    if black_image is not None and white_image is not None:
      calibration = ScreenCalibration(test_data.LoadImage(black_image),
                                      test_data.LoadImage(white_image))
      frame = self.calibratedFrame(on_image, off_image, calibration)
    else:
      frame = self.uncalibratedFrame(on_image, off_image)
    flashes = LEDDetector().Preprocess(frame, None)
    self.assertEqual(len(flashes), 0)

  def testPreprocessing1(self):
    self.executeLEDPreprocessingTest("led_1_on.png", "led_1_off.png")

  def testPreprocessing2(self):
    self.executeLEDPreprocessingTest("led_2_on.png", "led_2_off.png")

  def testPreprocessing3(self):
    self.executeLEDPreprocessingTest("led_4_on.png", "led_4_off.png")

  def testPreprocessing4(self):
    self.executeLEDPreprocessingTest("led_3_on.png", "led_3_off.png")

  def testFalsePositive0(self):
    self.executeFalsePositiveTest("led_fp_0.png", "led_fp_0_prev.png")

  def testFalsePositive1(self):
    self.executeFalsePositiveTest("led_fp_1.png", "led_fp_1_prev.png",
                                  "led_fp_1_calib_black.png",
                                  "led_fp_1_calib_white.png")

  def testEventGeneration(self):
    def flash(coords, color):
      return Flash(np.asarray(coords), float(color))
    flashes_sequence = [
      [flash((32, 32), 0.5)],  # Flash fading in over multiple frames
      [flash((32, 32), 1.0)],
      [], [], [], [], [], [], [], [], [], [],  # Wait 10 frames
      [flash((32, 32), -0.5)],  # Flash fading out over multiple frames
      [flash((32, 32), -1.0)],
      [], [], [], [], [], [], [], [], [], [],  # Wait 10 frames
      [flash((32, 32), 1.0)],  # Bouncing flash
      [flash((32, 32), -1.0)],
      [flash((32, 32), 1.0)],
    ]
    expected_events = {
      0: LEDEvent(0, LEDEvent.STATE_ON),
      12: LEDEvent(12, LEDEvent.STATE_OFF),
      24: LEDEvent(24, LEDEvent.STATE_ON)
    }
    self.assertExpectedEventsGenerated(LEDDetector(), flashes_sequence,
                                       expected_events)

  def testMultiFrameFadeIn(self):
    # Tests an edge case where an led fades in over multiple frames. In the
    # first frame, only the LED itself is detected as a valid flash, but in the
    # following frame a reflection is bright enough to be detected as well.
    # The reflection should be supressed and not generate another LED event.
    def flash(coords):
      return Flash(np.asarray(coords), 1.0)
    flashes_sequence = [
      [flash((199, 126))],
      [flash((225, 152)), flash((197., 123.))]
    ]
    expected_events = {
      0: LEDEvent(0, LEDEvent.STATE_ON)
    }
    self.assertExpectedEventsGenerated(LEDDetector(), flashes_sequence,
                                       expected_events)

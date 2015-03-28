# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for LEDDetector."""

import numpy as np

from optofidelity.detection._led_detector import LEDDetector, Flash
from optofidelity.detection.events import LEDEvent

from .test_detector import DetectorTest

class LEDDetectorTest(DetectorTest):

  def executeLEDPreprocessingTest(self, on_image, off_image):
    def assertLEDFlash(flashes, off_to_on):
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

  def testPreprocessing1(self):
    self.executeLEDPreprocessingTest("led_1_on.png", "led_1_off.png")

  def testPreprocessing2(self):
    self.executeLEDPreprocessingTest("led_2_on.png", "led_2_off.png")

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
      [], [], [], [], [], [], [], [], [], [],  # Wait 10 frames
      [flash((32, 32), 1.0)],  # 2 Flashes bouncing and slightly offset in time
      [flash((64, 64), 1.0)],
      [flash((32, 32), 1.0)],
      [flash((32, 32), 1.0), flash((64, 64), 1.0)],
      []
    ]
    expected_events = {
      0: LEDEvent(0, LEDEvent.STATE_ON),
      12: LEDEvent(12, LEDEvent.STATE_OFF),
      24: LEDEvent(24, LEDEvent.STATE_ON),
      37: LEDEvent(37, LEDEvent.STATE_ON),
      38: LEDEvent(38, LEDEvent.STATE_ON)
    }
    self.assertExpectedEventsGenerated(LEDDetector(), flashes_sequence,
                                       expected_events)
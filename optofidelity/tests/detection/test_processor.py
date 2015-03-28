# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for both implementations of VideoProcessor."""

from unittest import TestCase, skip
import numpy as np

from optofidelity.detection.processor import CreateVideoProcessor
from optofidelity.detection.fake import FakeVideoProcessor
from optofidelity.detection.screen_calibration import ScreenCalibration
from optofidelity.detection.events import LEDEvent, ScreenDrawEvent
from optofidelity.videoproc import FakeVideoReader

from . import test_data

class ProcessorTest(TestCase):
  def createTestVideoProcessor(self, multithreaded):
    calib = ScreenCalibration(test_data.CalibrationBlackImage(),
                              test_data.CalibrationWhiteImage())
    return CreateVideoProcessor(calib, multithreaded)

  def testSingleFrameProcessing(self):
    for multithreaded in (True, False):
      frame = test_data.LoadImage("led_1_on.png")
      prev_frame = test_data.LoadImage("led_1_off.png")

      processor = self.createTestVideoProcessor(multithreaded)
      processor.EnableDetectors(led=True)
      events = processor.ProcessFrame(0, frame, prev_frame, [])
      self.assertEqual(len(events), 1)
      event = events[0]
      self.assertEqual(event.time, 0)
      self.assertEqual(event.state, LEDEvent.STATE_ON)

  def testVideoProcessing(self):
    for multithreaded in (True, False):
      with test_data.CalibrationVideo() as video_reader:
        processor = self.createTestVideoProcessor(multithreaded)
        processor.EnableDetectors(screen_draw=True)
        events = processor.ProcessVideo(video_reader, [], False)

        self.assertEqual(len(events), 2)

        black_event = events[0]
        self.assertLess(np.abs(black_event.time - 21), 2)
        self.assertEqual(black_event.state, ScreenDrawEvent.STATE_BLACK)

        white_event = events[1]
        self.assertLess(np.abs(white_event.time - 44), 2)
        self.assertEqual(white_event.state, ScreenDrawEvent.STATE_WHITE)

  @skip("Requires manual validation")
  def testProgressDisplayAndDebugging(self):
    for multithreaded in (True, False):
      with test_data.CalibrationVideo() as video_reader:
        processor = self.createTestVideoProcessor(multithreaded)
        processor.EnableDetectors(screen_draw=True)
        processor.ProcessVideo(video_reader, ["all"], True)

  @skip("Requires manual validation")
  def testSingleFrameDebugging(self):
    frame = test_data.LoadImage("led_on.png")
    prev_frame = test_data.LoadImage("led_off.png")

    processor = self.createTestVideoProcessor(False)
    processor.EnableDetectors(screen_draw=True)
    processor.ProcessFrame(0, frame, prev_frame, ["all"])

  def testFakeProcessor(self):
    events = [LEDEvent(10, LEDEvent.STATE_ON),
              LEDEvent(20, LEDEvent.STATE_OFF)]
    processor = FakeVideoProcessor(events)
    video_reader = FakeVideoReader(50, (1280, 720), 300)
    result = processor.ProcessVideo(video_reader, [], False)
    self.assertEqual(result, events)

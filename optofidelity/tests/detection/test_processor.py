# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for both implementations of VideoProcessor."""

from unittest import TestCase

import numpy as np

from optofidelity.detection import (MultithreadedVideoProcessor,
                                    SinglethreadedVideoProcessor, Trace)
from optofidelity.detection.events import LEDEvent, ScreenDrawEvent
from optofidelity.detection.fake import FakeVideoProcessor
from optofidelity.detection.screen_calibration import ScreenCalibration
from optofidelity.videoproc import FakeVideoReader
from tests.config import CONFIG

from . import test_data


class ProcessorTest(TestCase):
  def setUp(self):
      self.calib = ScreenCalibration(test_data.CalibrationBlackImage(),
                                     test_data.CalibrationWhiteImage())

  def createTestVideoProcessor(self, multithreaded):
    if multithreaded:
      return MultithreadedVideoProcessor()
    else:
      return SinglethreadedVideoProcessor()

  def testVideoProcessing(self):
    for multithreaded in (True, False):
      with test_data.CalibrationVideo() as video_reader:
        processor = self.createTestVideoProcessor(multithreaded)
        processor.EnableDetectors(screen_draw=True)
        events = processor.ProcessVideo(video_reader, self.calib, [])

        self.assertEqual(len(events), 2)

        black_event = events[0]
        self.assertLess(np.abs(black_event.time - 21), 2)
        self.assertEqual(black_event.state, ScreenDrawEvent.STATE_BLACK)

        white_event = events[1]
        self.assertLess(np.abs(white_event.time - 44), 2)
        self.assertEqual(white_event.state, ScreenDrawEvent.STATE_WHITE)

  def testProgressDisplayAndDebugging(self):
    CONFIG.Require("user_interaction")
    for multithreaded in (True, False):
      with test_data.CalibrationVideo() as video_reader:
        processor = self.createTestVideoProcessor(multithreaded)
        processor.EnableDetectors(screen_draw=True)
        processor.ProcessVideo(video_reader, self.calib, ["all"])

  def testFakeProcessor(self):
    events = Trace([LEDEvent(10, LEDEvent.STATE_ON),
                    LEDEvent(20, LEDEvent.STATE_OFF)])
    processor = FakeVideoProcessor(events)
    video_reader = FakeVideoReader(50, (1280, 720), 300)
    calib = processor.CreateScreenCalibration(video_reader)
    result = processor.ProcessVideo(video_reader, calib, [])
    self.assertEqual(result, events)

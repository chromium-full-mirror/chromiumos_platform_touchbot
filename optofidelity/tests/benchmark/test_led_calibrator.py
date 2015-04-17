# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from optofidelity.benchmark import LEDCalibrator
from optofidelity.detection import LEDEvent, Trace
from optofidelity.detection.fake import FakeVideoProcessor
from optofidelity.system.fake import FakeBenchmarkSystem


class LEDCalibratiorTests(unittest.TestCase):
  def setUp(self):
    self.video_processor = FakeVideoProcessor()
    self.calibrator = LEDCalibrator(self.video_processor)
    system = FakeBenchmarkSystem()
    self.subject = system.fake_subject

  def testLEDCalibration(self):
    self.video_processor.fake_trace = Trace([
      LEDEvent(10, True),
      LEDEvent(14, True),  # Down delay = 4
      LEDEvent(50, False),
      LEDEvent(56, False),  # Up delay = 6
    ])
    delays = self.calibrator.CalibrateLED(self.subject, False)
    self.assertEqual(delays, (4, 6))

# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Fake implementation of VideoProcessor for testing."""

from safetynet import List, Optional
import numpy as np

from ._detector import Detector
from .events import Event
from .trace import Trace
from .screen_calibration import ScreenCalibration
from .st_processor import SinglethreadedVideoProcessor


class FakeVideoProcessor(SinglethreadedVideoProcessor):
  """Fake video processor that generates pre-specified list of events."""

  def __init__(self, trace=None):
    """
    :param Optional[Trace] trace: list of events to generate.
    """
    super(FakeVideoProcessor, self).__init__()
    self.fake_trace = trace

  def ProcessVideo(self, video_reader, screen_calibration, debug_flags):
    if self.fake_trace:
      return self.fake_trace
    else:
      super(FakeVideoProcessor, self).ProcessVideo(video_reader,
          screen_calibration, debug_flags)

  def CreateScreenCalibration(self, video_reader):
    if self.fake_trace:
      shape = video_reader.frame_shape
      return ScreenCalibration(np.zeros(shape), np.ones(shape))
    else:
      return super(FakeVideoProcessor, self).CreateScreenCalibration(
          video_reader)

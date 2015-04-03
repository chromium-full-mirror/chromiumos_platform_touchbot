# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Fake implementation of VideoProcessor for testing."""

from safetynet import List, Optional
import numpy as np

from ._detector import Detector
from .events import Event
from .screen_calibration import ScreenCalibration
from .st_processor import SinglethreadedVideoProcessor


class FakeDetector(Detector):
  """This detector generates a pre-specified list of events.

  We are doing the look up of the event in preprocess so we are covering
  the logic that passes the results of Preprocess into GenerateEvents when
  using this class.
  """
  NAME = "fake"

  def __init__(self, events):
    """
    :param List[Event] events: list of events to generate
    """
    self.events_map = dict([(e.time, e) for e in events])

  def Preprocess(self, calib_frame, debugger):
    return self.events_map.get(calib_frame.frame_index, None)

  def GenerateEvents(self, preprocessed_data, frame_index, debugger):
    event = preprocessed_data
    if event:
      return [event]
    return []


class FakeVideoProcessor(SinglethreadedVideoProcessor):
  """Fake video processor that generates pre-specified list of events.

  Note: The events are generated at the correct time, which means if the
  video to process only has 500 frames, only events until the timestamp 500 will
  be generated.
  """

  def __init__(self, trace=None):
    """
    :param Optional[List[Event]] trace: list of events to generate.
    """
    super(FakeVideoProcessor, self).__init__()
    self.fake_trace = trace

  def _InitDetectors(self):
    if self.fake_trace:
      self._detectors = [FakeDetector(self.fake_trace)]
    else:
      super(FakeVideoProcessor, self)._InitDetectors()

  def CreateScreenCalibration(self, video_reader):
    if self.fake_trace:
      shape = video_reader.frame_shape
      return ScreenCalibration(np.zeros(shape), np.ones(shape))
    else:
      return super(FakeVideoProcessor, self).CreateScreenCalibration(
          video_reader)

# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

import numpy as np

from optofidelity.util import nputil
from optofidelity.videoproc import Canvas

from ._detector import Detector
from .events import AnalogStateEvent, ScreenDrawEvent

_log = logging.getLogger(__name__)


class ScreenDrawDetector(Detector):
  """Detects full screen draws switching between black and white."""

  NAME = "screen_draw"

  EDGE_WIDTH = 10
  """Width of edges on the sides of the screen we analyse for screen flashes."""

  def Preprocess(self, calib_frame, debugger):
    profile = np.mean(calib_frame.screen_space_normalized, 0)
    if debugger:
      debugger.screen_space_canvas.PlotProfile(Canvas.BLUE, profile)

    segment = [profile[:self.EDGE_WIDTH], profile[-self.EDGE_WIDTH:]]
    return (np.min(segment), np.max(segment))

  def GenerateEvents(self, preprocessed_data):
    data = np.asarray(preprocessed_data, dtype=np.float)
    profile_min = data[:, 0]
    profile_max = data[:, 1]

    min_changes = nputil.FindStateChanges(profile_min)
    max_changes = nputil.FindStateChanges(profile_max)
    for min_change, max_change in zip(min_changes, max_changes):
      start = min([min_change[0], max_change[0]])
      end = max([min_change[1], max_change[1]])
      color = np.mean([profile_min[end], profile_max[end]])
      state = (ScreenDrawEvent.STATE_BLACK if color < 0.5
                                           else ScreenDrawEvent.STATE_WHITE)
      yield ScreenDrawEvent(end, start, state)

    for i, data in enumerate(preprocessed_data):
      if data is None:
        continue
      yield AnalogStateEvent(i, 1.0 - np.mean(data))

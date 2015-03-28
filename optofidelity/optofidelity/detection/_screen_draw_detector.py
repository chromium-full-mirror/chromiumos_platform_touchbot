# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

import numpy as np

from optofidelity.videoproc import Canvas, Filter, Shape

from ._detector import Detector
from .events import ScreenDrawEvent

_log = logging.getLogger(__name__)


class ScreenDrawDetector(Detector):
  """Detects full screen draws switching between black and white."""

  NAME = "screen_draw"

  CHANGE_THRESH = 0.9
  """How much of the target color has to be reached for the screen to be
     be considered fully changed."""

  NO_CHANGE_THRESH = 0.05
  """How much can the color deviate from it's supposed color to be considered
     unchanged."""

  EDGE_WIDTH = 10
  """Width of edges on the sides of the screen we analyse for screen flashes."""


  def __init__(self):
    self._color = None
    self._last_no_draw_time = 0

  def Preprocess(self, calib_frame, debugger):
    profile = np.mean(calib_frame.screen_space_normalized, 0)
    if debugger:
      debugger.screen_space_canvas.Plot(Canvas.BLUE, profile)

    segment = [profile[:self.EDGE_WIDTH], profile[-self.EDGE_WIDTH:]]
    return (np.min(segment), np.max(segment))

  def GenerateEvents(self, preprocessed_data, frame_index, debugger):
    min_level, max_level = preprocessed_data

    # Note the last time the profile stays below the no_change threshold. This
    # is the time index just before the draw starts.
    # If the threshold exceeds the change threshold we consider the draw
    # done and generate both the start and end draw event.
    if self._color == ScreenDrawEvent.STATE_BLACK:
      if max_level < self.NO_CHANGE_THRESH:
        self._last_no_draw_time = frame_index
      elif min_level > self.CHANGE_THRESH:
        self._color = ScreenDrawEvent.STATE_WHITE
        return [ScreenDrawEvent(frame_index, state=self._color,
                                start_time=self._last_no_draw_time + 1)]

    # Analogous to the black logic.
    elif self._color == ScreenDrawEvent.STATE_WHITE:
      if min_level > 1.0 - self.NO_CHANGE_THRESH:
        self._last_no_draw_time = frame_index
      elif max_level < 1.0 - self.CHANGE_THRESH:
        self._color = ScreenDrawEvent.STATE_BLACK
        return [ScreenDrawEvent(frame_index, state=self._color,
                                start_time=self._last_no_draw_time + 1)]

    # Wait for a solid black or white screen to set initial color
    else:
      if max_level < self.NO_CHANGE_THRESH:
        self._color = ScreenDrawEvent.STATE_BLACK
      elif max_level > 1.0 - self.NO_CHANGE_THRESH:
        self._color = ScreenDrawEvent.STATE_WHITE

    return []

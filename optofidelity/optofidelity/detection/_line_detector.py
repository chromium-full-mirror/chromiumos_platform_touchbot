# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from collections import namedtuple
import logging

import numpy as np

from optofidelity.videoproc import Canvas

from ._detector import Detector
from .events import LineDrawEvent

_log = logging.getLogger(__name__)


ProfileSegment = namedtuple("ProfileSegment", ["array", "start", "end"])


def _CalculateProfile(image, mask):
  return np.sum(image * mask, 0) / np.sum(mask, 0)


def _SegmentProfile(profile, threshold):
  segmentation = (profile > threshold)
  objects = []
  object_start = None
  for i, value in enumerate(segmentation):
    if value and object_start is None:
      object_start = i
    elif not value and object_start is not None:
      objects.append(ProfileSegment(profile, object_start, i))
      object_start = None
  if object_start is not None:
    objects.append(ProfileSegment(profile, object_start, i))
  return objects


class LineDetector(Detector):
  """Detects vertical lines drawn on the screen."""

  NAME = "line"

  DRAW_END_MIN_COLOR = 0.9
  """How much of the target color a line segment has to reach to be considered
     fully drawn."""

  DRAW_START_MIN_COLOR = 0.05
  """How much of the target color a line segment has to reach to be considered
     starting to draw."""

  MIN_SEGMENT_COLOR = 0.5
  """Minimum color for a pixel to be considered part of the currently
     drawing segment."""

  MIN_SEGMENT_LENGTH = 3
  """Minimum length of a line segment."""

  LINE_WIDTH = 8
  """Width of drawn line in rectified space pixels."""

  RESET_SUPPRESS_DURATION = 10
  """After a reset all line detection is suppressed for this duration (In number
     of camera frames)."""

  def __init__(self):
    self._last_no_draw_map = None
    self._line_obj = None
    self._current_location = 0
    self._suppress_until = None

  def Preprocess(self, calib_frame, debugger):
    """Preprocessing step to process 2D frames into a 1D profile.

    The profile of a line roughly looks like this:
         _________________
        |                 \
        |                  \_
     ___|                    \_________________
               ^         |----|        ^
       fully drawn     transition   no line
      line segments       area       drawn

    The line is expected to be at the center of the screen and have at least a
    width of LINE_WIDTH.
    """
    center = int(calib_frame.screen_space_shape[0] / 2)
    top = int(center - (self.LINE_WIDTH / 2))
    bottom = int(center + (self.LINE_WIDTH / 2))

    mask = np.zeros(calib_frame.screen_space_shape, dtype=np.bool)
    mask[top:bottom, :] = True

    profile = _CalculateProfile(1 - calib_frame.screen_space_normalized, mask)
    if debugger:
      debugger.screen_space_canvas.DrawMask(Canvas.RED, mask)
      debugger.screen_space_canvas.PlotProfile(Canvas.BLUE, profile.array)
    return profile

  def GenerateEvents(self, preprocessed_data, frame_index, debugger):
    def log(msg, *params):
      _log.debug("%04d: " + msg, frame_index, *params)

    profile = preprocessed_data

    def Reset():
      self._line_obj = None
      self._suppress_until = frame_index + self.RESET_SUPPRESS_DURATION
      return [LineDrawEvent(frame_index, location=None, start_time=frame_index)]

    # Note the timestamp at which each profile pixel has last been below the
    # DRAW_START_MIN_COLOR threshold. This is the frame before the drawing
    # started.
    if self._last_no_draw_map is None:
      self._last_no_draw_map = np.zeros(profile.shape)
    no_draw_indices = (profile < self.DRAW_START_MIN_COLOR)
    self._last_no_draw_map[no_draw_indices] = frame_index

    if self._suppress_until and frame_index < self._suppress_until:
      log("Suppressing. until=%d", self._suppress_until)
      return []

    # Segment line in current frame
    objects = _SegmentProfile(profile, self.MIN_SEGMENT_COLOR)

    # If we have not seen a line before, just store this line object.
    if self._line_obj is None:
      if len(objects) == 1:
        self._line_obj = objects[0]
      return []

    # If the line disappeared generate a reset event.
    if len(objects) == 0:
      return Reset()

    # Determine new line segment and location
    new_line = objects[0]
    new_location = None
    new_slice = None

    if self._line_obj.start - new_line.start > self.MIN_SEGMENT_LENGTH:
      # New segment drawn on left side of existing line.
      new_location = new_line.start + 1
      new_slice = np.s_[new_line.start:self._line_obj.start]
    elif new_line.end - self._line_obj.end > self.MIN_SEGMENT_LENGTH:
      # New segment draw on right side of existing line.
      new_location = new_line.end - 1
      new_slice = np.s_[self._line_obj.end:new_line.end]
    elif self._line_obj.start - new_line.start < -self.MIN_SEGMENT_LENGTH:
      # Left side of line is disappearing. Reset.
      return Reset()
    elif new_line.end - self._line_obj.end < -self.MIN_SEGMENT_LENGTH:
      # Right side of line is disappearing. Reset.
      return Reset()

    if new_slice is not None:
      # Wait until the median color level meets the DRAW_END_MIN_COLOR
      # requirement, then generate draw events.
      level = np.median(profile[new_slice])
      log("New segment. level=%d", level)
      if level > self.DRAW_END_MIN_COLOR:
        last_no_draw = np.max(self._last_no_draw_map[new_slice])
        self._line_obj = new_line
        self._current_location = new_location
        return [LineDrawEvent(frame_index, location=float(new_location),
                              start_time=int(last_no_draw + 1))]

    if debugger:
      debugger.screen_space_canvas.DrawVLine(Canvas.BLUE,
                                             self._current_location)

    return []

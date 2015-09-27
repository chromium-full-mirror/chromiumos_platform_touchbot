# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

import matplotlib.pyplot as pyplot
import numpy as np

from optofidelity.util import nputil
from optofidelity.videoproc import Canvas, Shape

from ._detector import Detector
from .events import LineDrawEvent

_log = logging.getLogger(__name__)


class LineDetector(Detector):
  """Detects vertical lines drawn on the screen."""

  NAME = "line"

  MIN_SEGMENT_LENGTH = 3
  """Minimum length of a line segment."""

  LINE_WIDTH = 16
  """Width of drawn line in rectified space pixels."""

  MAX_NOISE_LEVEL = 0.2
  """Maximum expected noise level."""

  MIN_EDGE_DISTANCE = 5
  """Minimum distance required from the edge."""

  WHITE_SETTLED_THREHSOLDS = dict(min_value=0.9,
                                 max_slope=0.1,
                                 max_mid_range=0.1)
  """Thresholds to identify a white color has settled
     (see nputil.FindSettlingIndex)"""

  BLACK_SETTLED_THRESHOLDS = dict(max_value=0.1)
  """Thresholds to identify a black color has settled
     (see nputil.FindSettlingIndex)"""

  LINE_RESET_DURATION = 5
  """Duration of a line reset in number of camera frames."""

  LINE_RESET_MIN_DISTANCE = 0.5
  """How much the line location has to change to consider a line reset, in
     relative distance 0..1 of the full line length.
  """

  def Preprocess(self, calib_frame, debugger):
    """Segments the left and right side of the line.

    Since the line ends are not abrubt and have a transition from black to white
    over a couple of pixels, we return the start and end location of these
    transitions. If a new line segment is slightly showing, the start location
    on that side will move to the location of the new segment, but the end
    location will stay where it is until the segment is fully drawn.
    """
    # We are looking for the line in the center of the screen
    center = int(calib_frame.screen_space_shape[0] / 2)
    top = int(center - (self.LINE_WIDTH / 2))
    bottom = int(center + (self.LINE_WIDTH / 2))
    line_shape = Shape.FromRectangle(calib_frame.screen_space_shape,
                                top=top, bottom=bottom)

    # Segment the profile to find the line
    profile = line_shape.CalculateProfile(calib_frame.screen_space_normalized)
    profile = calib_frame.CompensatePWMProfile(profile)
    segmentations = list(nputil.Segment(profile < self.MAX_NOISE_LEVEL))

    if debugger:
      debugger.screen_space_canvas.DrawMask(Canvas.RED, line_shape.contour)
      debugger.screen_space_canvas.PlotProfile(Canvas.BLUE, profile)

    if not len(segmentations):
      return (None, None, None, None)

    # The largest segmentation is the line
    left, right = max(segmentations, key=lambda s: s[1] - s[0])
    _log.debug("%04d line: %d:%d",
               calib_frame.frame_index, left, right)

    # Find left transition period
    left_start = left_end = 0
    if left > self.MIN_EDGE_DISTANCE:
      left_start = nputil.FindSettlingIndexReverse(profile, left,
          **self.WHITE_SETTLED_THREHSOLDS)
      left_end = nputil.FindSettlingIndex(profile, left,
          **self.BLACK_SETTLED_THRESHOLDS)

    # Find right transition perios
    right_start = right_end = len(profile) - 1
    if right < len(profile) - self.MIN_EDGE_DISTANCE:
      right_start = nputil.FindSettlingIndex(profile, right,
          **self.WHITE_SETTLED_THREHSOLDS)
      right_end = nputil.FindSettlingIndexReverse(profile, right,
          **self.BLACK_SETTLED_THRESHOLDS)

    if debugger:
      debugger.screen_space_canvas.DrawVLine(Canvas.GREEN, left_start)
      debugger.screen_space_canvas.DrawVLine(Canvas.RED, left_end)
      debugger.screen_space_canvas.DrawVLine(Canvas.GREEN, right_start)
      debugger.screen_space_canvas.DrawVLine(Canvas.RED, right_end)

    _log.debug("%04d line transitions: %d:%d and %d:%d",
               calib_frame.frame_index,left_start, left_end, right_end,
               right_start)

    return left_start, left_end, right_end, right_start

  def GenerateEvents(self, preprocessed_data, debug=False):
    if debug:
      for data in preprocessed_data:
        print "(%s, %s, %s, %s)" % data

    def FindDrawTimes(line_end):
      # Find times when a new segment is fully drawn
      filtered_line_end = nputil.BoxFilter(line_end, self.MIN_SEGMENT_LENGTH)
      draw_times = np.nonzero(np.diff(filtered_line_end))[0] + 1
      draw_times = list(nputil.DeDuplicate(draw_times, min_distance=2))

      for i in range(len(draw_times)):
        draw_time = draw_times[i]
        if i < len(draw_times) - 1:
          next_draw = draw_times[i + 1]
        else:
          next_draw = len(draw_times)

        # Average the location until before the next draw event.
        location = np.mean(nputil.NonNan(line_end[draw_time:(next_draw - 1)]))
        if np.isnan(location):
          location = line_end[draw_time]
        yield (draw_time, location)

    def FindDrawStartTime(draw_time, location, line_start, line_end):
      # Walk back in time and search for location when the first screen reaction
      # has passed the draw location. This is the start time of the draw.
      draw_direction = np.sign(line_end[draw_time] - line_end[draw_time - 1])
      for i in range(draw_time, -1, -1):
        if (draw_direction < 0 and line_start[i] >= location or
            draw_direction > 0 and line_start[i] <= location):
          return i + 1
      return draw_time

    # Unpack preprocessed data
    line_transitions = np.asarray(preprocessed_data, dtype=np.float)
    (left_start, left_end) = (line_transitions[:, 0], line_transitions[:, 1])
    (right_end, right_start) = (line_transitions[:, 2], line_transitions[:, 3])

    max_end = np.max((nputil.NonNan(left_end), nputil.NonNan(right_end)))
    left_norm_loc = left_end / max_end
    right_norm_loc = right_end / max_end

    # Map that is true at each index a line was not present
    reset_map = np.isnan(left_end)

    # Find line resets where the line length is shrinking rapidly
    line_length =  right_norm_loc - left_norm_loc
    line_length[np.isnan(line_length)] = 0
    reset_map[np.diff(line_length) < -0.1] = True

    if debug:
      pyplot.figure()
      pyplot.plot(left_norm_loc)
      pyplot.plot(right_norm_loc)
      pyplot.plot(line_length, "--")
      pyplot.plot(reset_map, "-o")

    # Merge left and right end into coherent line location
    line_start = np.full(left_start.shape, np.nan)
    line_end = np.full(left_end.shape, np.nan)
    padding = 10
    for start, end in nputil.Segment(~reset_map):
      start = start + padding
      end = end - padding
      slice = np.s_[start:end]
      left_distance = nputil.MinMaxRange(left_norm_loc[slice])
      right_distance = nputil.MinMaxRange(right_norm_loc[slice])

      if left_distance < 0.2 and right_distance < 0.2:
        continue
      if right_distance > left_distance:
        line_start[slice] = right_start[slice]
        line_end[slice] = right_end[slice]
      else:
        line_start[slice] = left_start[slice]
        line_end[slice] = left_end[slice]

    draws = list(FindDrawTimes(line_end))
    draw_start_times = [FindDrawStartTime(draw_time, location, line_start,
                                          line_end)
                        for draw_time, location in draws]

    if debug:
      pyplot.figure()
      pyplot.plot(line_start, "-x")
      pyplot.plot(line_end, "-x")
      pyplot.plot([t for t, _ in draws], [l for _, l in draws], "o")
      pyplot.plot(draw_start_times, [l for _, l in draws], "x")
      pyplot.show()

    for (draw_time, location), draw_start_time in zip(draws, draw_start_times):
      yield LineDrawEvent(draw_time, location, draw_start_time)

    for start, end in nputil.Segment(reset_map):
      yield LineDrawEvent(end, None, start)




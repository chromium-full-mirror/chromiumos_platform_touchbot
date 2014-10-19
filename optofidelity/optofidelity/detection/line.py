# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contracts import contract
import numpy as np

from optofidelity.detection.trace import Event
from optofidelity.videoproc import Viewer, Filter, Shape, Canvas
from optofidelity.detection.detector import Detector

class LineSegment(object):
  """Contains information of a line segment detected by the Line class.

  A line segment describes a segment of a horizontal line, which start/end
  bein values on the x-axis of the video frames. The level of the line is
  the average grayscale value of the line normalized to the final grayscale
  value of the segment when it is finished drawing.
  """
  @contract(start=">=0", end=">=0", draw_start=">=0")
  def __init__(self, start, end, draw_start):
    self.start = start
    self.end = end
    self.draw_start = draw_start
    self.draw_end = None
    self.level = 0

  def UpdateLevel(self, normalized):
    """Update the level of this segment from a normalized profile.

    See Line.Preprocess for information on this profile.
    """
    if self.start > self.end:
      idx = range(self.end, self.start)
    else:
      idx = range(self.start, self.end)
    self.level = np.median(normalized[idx])

  def __repr__(self):
    return "(%d, %d, %d)" % (self.end, self.draw_start, self.draw_end)

  @property
  def length(self):
    return np.abs(self.end - self.start)


class Line(object):
  """Detects line draw events.

  For initialization it requires an image of the fully drawn, non occluded line,
  which will be called target line.
  Per default the line is expected to be drawn from left to right, but it
  automatically detects if the direction is reversed and sets self.reverse to
  True.
  """
  name = "line"

  draw_end_thresh = 0.9
  """How much of the target color a line segment has to reach to be considered
     fully drawn."""

  target_line_min_area = 500
  """Minimum size of the target line shape, in square pixels."""

  target_line_min_eccentricity = 0.99
  """Minimum eccentricity of the target line shape."""

  target_line_max_orientation = 0.1
  """Maximum orientation of the target line shape in radians from horizontal."""

  target_line_search_step = 10
  """When searching for the target line, look only at every Nth frame."""

  target_line_search_max_steps = 10
  """How many frames to look at when looking for a target line."""

  target_line_padding = 5
  """How many pixels of padding around the target line to account for camera
     shake?"""

  profile_object_threshold = 0.1
  """Areas above this threshold are considered to be an object in the
     image profile."""

  border_touching_threshold = 5
  """Any object that's closer to the border than this threshold is considered
     to touch the border."""

  minimum_line_length = 4
  """Minimum length of a newly detected line."""

  minimum_line_level = 0.5
  """Minimum brightness level of a newly detected line."""

  transition_epsilon = 0.01
  """Near-zero epsilon to detect when the transition area hits zero."""

  segment_merge_level = 0.3
  """Line segments with an level difference lower than this threshold will be
     merged."""

  segment_min_length = 2
  """Minimum length of a line segment."""

  def __init__(self):
    # Calibration Information
    self.target_shape = None
    self._target_left = None
    self._target_right = None
    self._drawn_profile = None

    # Stateful Information
    self.found = False
    self.segments = []
    self.reverse = False
    self._line_end = None

  def Initialize(self, video, debug):
    step = -self.target_line_search_step
    stop = -step * self.target_line_search_max_steps
    for frame in video.Frames(start=-1, stop=stop, step=step):
      if self.DetectTargetLine(frame, debug=debug):
        return True
    return False

  def DetectTargetLine(self, frame, debug):
    """Detect the final line that is to be drawn.

    The parameter frame has to be a Frame instance from an image showing the
    non-occluded target line.
    Returns False if the detection failed.
    """
    def is_target_line(region, labels, debug):
      if debug:
        print region.label, region.area, region.eccentricity, region.orientation
      return (region.area > self.target_line_min_area and
              region.eccentricity > self.target_line_min_eccentricity and
              np.abs(region.orientation) < self.target_line_max_orientation)

    # Find object fitting the is_target_line function.
    binary = frame.foreground
    self.target_shape = Shape.Find(binary, is_target_line, debug=debug)
    if not self.target_shape:
      return False

    self._target_left = self.target_shape.left
    self._target_right = self.target_shape.right

    # Add margin to account for camera shake.
    padding = self.target_line_padding
    self.target_shape = self.target_shape.WithMargin(padding, padding)

    # Calculate profile of drawn line and empty screen as reference.
    self._drawn_profile = Filter.ExtractProfile(
        (1 - frame.normalized) * self.target_shape.mask)

    if debug:
      res = Canvas(frame.rectified)
      res.DrawContour([0, 1, 0], self.target_shape)
      Viewer.DebugView(contour=res.image)
    return True

  def _FindLine(self, profile):
    """Search profile for the beginning of a line draw.

    Since the robot finger is passing through the same area, we have to
    reject the robot finger and identify the peak in the profile that
    represents the line.

    Returns a tuple (start, end) if the line is _found and sets
    self.reverse if the line is drawn from right to left.
    """
    # segment objects on profile line (1D version of shape detection)
    segmentation = (profile > self.profile_object_threshold).astype(np.int)
    segmentation_diff = np.diff(segmentation)

    objects = []
    object_start = 0
    for i in range(len(segmentation_diff)):
      if segmentation_diff[i] > 0:
        object_start = i
      elif segmentation_diff[i] < 0:
        objects.append((object_start, i))

    # The first object will be the robot finger.
    if len(objects) <= 1:
      return None

    # find leftmost and rightmost objects
    leftmost_object = min(objects, key=lambda o: o[0])
    rightmost_object = max(objects, key=lambda o: o[1])

    # check if the object is at the start or end of the target line
    line = None
    border_threshold = self.border_touching_threshold
    if leftmost_object[0] < self._target_left + border_threshold:
      line = leftmost_object
      self.reverse = False
    elif rightmost_object[1] > self._target_right - border_threshold:
      line = rightmost_object
      self.reverse = True
    if not line:
      return None

    # check if the line is dark and long enough
    line_level = np.mean(profile[line[0]:line[1]])
    line_length = line[1] - line[0]
    if (line_level > self.minimum_line_level and
        line_length > self.minimum_line_length):
      return line
    return None

  def _FindTransition(self, profile):
    """Find beginnging and end of transition area in the profile profile."""
    # Determine directions depending on the direction the line is being drawn
    forward = +1 if not self.reverse else -1
    backward = -1 if not self.reverse else +1
    front = 0 if not self.reverse else len(profile)
    back = len(profile) if not self.reverse else 0

    # find transition period around the end of the line
    # the transition starts where the profile starts decreasing from 1 and
    # ends where it hits 0.
    transition_start = self._line_end
    transition_end = self._line_end
    for i in range(self._line_end, front, backward):
      if profile[i] > 1 - self.transition_epsilon:
        transition_start = i
        break
    for i in range(self._line_end, back, forward):
      if profile[i] < self.transition_epsilon:
        transition_end = i
        break
    return (transition_start, transition_end)

  def _AddNewSegments(self, timestamp, profile, transition_start,
                      transition_end):
    """Add new segments to self.segments after they have been fully drawn."""
    forward = +1 if not self.reverse else -1
    backward = -1 if not self.reverse else +1

    # Add initial line segment
    if not self.segments:
      self.segments.append(LineSegment(transition_start,
                                       transition_end + backward,
                                       timestamp))

    # Look for potential new segment
    last_segment = self.segments[-1]
    new_segment = LineSegment(last_segment.end + forward,
                              transition_end + backward,
                              timestamp)
    new_segment.UpdateLevel(profile)

    segment_level_diff = np.abs(last_segment.level - new_segment.level)

    if segment_level_diff < self.segment_merge_level:
      # segments colors are very close to each other, merge them.
      last_segment.end = new_segment.end
    elif new_segment.length > self.segment_min_length:
      # segment is big enough, append as new segment
      self.segments.append(new_segment)

  def Preprocess(self, frame, debug):
    """Preprocessing step to process 2D frames into a 1D profile.

    The profile of a line roughly looks like this:
      ____________________
                          \                       _
                           \_                    / \
                             \__________________/   \___
            ^            |----|        ^          ^
       fully drawn     transition   no line     robot
      line segments       area       drawn      finger

    This method returns data to be passed to GenerateEvents. This method
    is stateless and can be called on any frames out of order."""
    if not self.target_shape:
      return None
    return Filter.ExtractProfile(1 - frame.normalized,
                                 self._drawn_profile)

  def GenerateEvents(self, preprocessed_data, timestamp, debug):
    """Generate Line events from sequential preprocessed data.

    Returns a list of LINE_DRAW_START, LINE_DRAW_END and LINE_RESET events as
    they are happening in the video stream.
    This method is stateful, requires data generated by Preprocess and has to
    be called with this data from frames in sequential order.
    """
    events = []
    profile = preprocessed_data

    if debug_canvas:
      debug_canvas.Plot(Canvas.BLUE, profile)

    if not self.target_shape:
      return events

    # Search for start of line drawing
    if not self.found:
      line = self._FindLine(profile)
      if line:
        self._line_end = line[1] if not self.reverse else line[0]
        self.found = True

    if not self.found:
      return events

    # Update existing segments and create draw events
    for segment in self.segments:
      segment.UpdateLevel(profile)
      if segment.draw_end is None and segment.level > self.draw_end_thresh:
        segment.draw_end = timestamp
        events.append(Event(segment.draw_start, Event.LINE_DRAW_START,
                            location=segment.end))
        events.append(Event(segment.draw_end, Event.LINE_DRAW_END,
                            location=segment.end))

    # Find transition area and add new line segments to the segment list
    (transition_start, transition_end) = self._FindTransition(profile)
    self._AddNewSegments(timestamp, profile, transition_start,
                         transition_end)
    self._line_end = transition_end

    if debug:
      for segment in self.segments:
        debug.canvas.DrawHLine(Canvas.GREEN, segment.end,
                                    self.target_shape.center_y)

      debug.canvas.DrawHLine(Canvas.YELLOW, transition_start,
                                  self.target_shape.center_y)
      debug.canvas.DrawHLine(Canvas.YELLOW, transition_end,
                                  self.target_shape.center_y)
    return events

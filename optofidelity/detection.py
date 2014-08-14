# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Classes for detecting objects in video streams of the OptoFidelity robot.

This module is to be used on a video recording from the OptoFidelity robot
working on a touchscreen. It allows the detection of the touchscreen, the
robot finger as well as the detection of a line being drawn on the screen.

For the purpose of latency measurements, the line and screen detection also
accurately detects the frame when an updated frame is being drawn on the
screen.
"""
import bisect
import numpy as np
import skimage.morphology as morphology

from videoproc import Viewer, Filter, Shape, Canvas


class Event(object):
  """Describes an event detected in the camera stream."""
  LINE_DRAW_START = "LineDrawStart"
  LINE_DRAW_END = "LineDrawEnd"
  LINE_RESET = "LineReset"
  SCREEN_DRAW_START = "ScreenDrawStart"
  SCREEN_DRAW_END = "ScreenDrawEnd"
  FINGER_MOVED = "FingerMoved"
  FINGER_DOWN = "FingerDown"
  FINGER_UP = "FingerUp"

  def __init__(self, time, event_type, location=None, color=None):
    self.event_type = event_type
    self.time = time
    self.location = location
    self.color = color

  def __repr__(self):
    optional = []
    if self.location:
      optional.append("location=%d" % self.location)
    if self.color:
      optional.append("color=%s" % self.color)

    optional_str = ""
    if optional:
      optional_str = " (%s)" % (",".join(optional))
    return "%d %s%s" % (self.time, self.event_type, optional_str)


class Trace(object):
  """Describes a series of events, ordered by time."""
  def __init__(self):
    self._events = []
    self._times = []

  def AddAll(self, events):
    for event in events:
      self.Add(event)

  def Add(self, event):
    i = bisect.bisect_left(self._times, event.time)
    self._events.insert(i, event)
    self._times.insert(i, event.time)

  def Events(self, event_type=None):
    if event_type:
      return [e for e in self._events if e.event_type == event_type]
    else:
      return self._events


class Frame(object):
  """This class stores multiple versions and views of a camera frame.

  This class stores a cropped version of the image, enhances it with noise
  filtering and calculates the reflectance.
  """
  def __init__(self, im, crop_shape=None, index=0):
    self.original = im
    self.cropped = im
    self.index = index

    self.crop_shape = crop_shape
    if crop_shape:
      # crop to bounding box of object
      self.cropped = crop_shape.Cropped(crop_shape.RemoveBackground(im))

    # noise filtering
    self.enhanced = Filter.Median(self.cropped, disk_size=3)

    # noise filtered reflectance
    self.reflectance = Filter.Reflectance(self.cropped, disk_size=40,
                                          scale=0.5)
    self.reflectance = Filter.Median(self.reflectance, disk_size=1)

  def DebugView(self):
    Viewer.DebugView(cropped=self.cropped,
                     enhanced=self.enhanced,
                     reflectance=self.reflectance)

class Screen(object):
  """Represents the device screen in the video stream.

  It detects the screen in a video showing the flashing screen and also
  allows for detection of screen flashes in any video.

  Screen.shape is the detected screen shape object.
  """

  def __init__(self, frames=None, shape=None, debug=False):
    """Initialize by either providing a shape or frames iterator.

    Providing a shape allows you to reuse a previously computed screen shape.
    Providing an iterator on frames (i.e. from VideoReader.Frames()) will
    detect the screen in these video frames.
    """
    self._prev_draw_avg = None
    self._prev_frame_avg = None
    if frames:
      self._DetectScreen(frames, debug)
    elif shape:
      self.shape = shape
    else:
      raise ValueError("Must provide either shape or frames")

  def _DetectScreen(self, frames, debug=False):
    """Detect the devices flashing screen.

    The frames argument has to be a python iterator that yields
    video frames. Those video frames have to show the device's screen
    flashing black and white.
    """
    # accumulate difference between camera frames
    i, prev_frame = frames.next()
    delta_accum = np.zeros(prev_frame.shape)
    for i, frame in frames:
      delta = np.abs(frame - prev_frame)
      delta_accum += delta
      prev_frame = frame
    delta_accum = Filter.Equalize(delta_accum)

    # threshold the result. The largest connected component is the screen.
    binary = Filter.OtsuSegmentation(delta_accum)
    binary = morphology.binary_closing(binary, morphology.disk(2))
    binary = morphology.binary_erosion(binary, morphology.disk(4))
    self.shape = Shape.FindMax(binary, lambda p: p.area)

    if debug:
      res = Canvas(prev_frame)
      res.DrawContour([1, 0, 0], self.shape)
      Viewer.DebugView(accum=delta_accum,
                       binary=binary,
                       mask=res.image)

  def Update(self, frame, debug=False):
    """Check for the screen flashing.

    This method returns a list of events that will contain SCREEN_DRAW_START
    and SCREEN_DRAW_END events as they happen in the video stream.
    """
    events = []
    avg = np.mean(frame.enhanced)

    # init at first frame
    if self._prev_draw_avg is None:
      self._prev_draw_avg = avg
      self._prev_frame_avg = avg
      return

    # calculate diff to last frame and last draw
    draw_diff = self._prev_draw_avg - avg
    frame_diff = self._prev_frame_avg - avg
    if debug:
      print "avg={} draw_diff={} frame_diff={}".format(avg, draw_diff,
                                                       frame_diff)

    # screen has to have changed enough since last draw,
    # and only little since last frame to determine if drawing is finished.
    if abs(draw_diff) > 0.5 and abs(frame_diff) < 0.02:
      self._prev_draw_avg = avg
      color = "White" if avg > 0.5 else "Black"
      events.append(Event(frame.index, Event.SCREEN_DRAW_END, color=color))

    self._prev_frame_avg = avg
    return events


class LineSegment(object):
  """Contains information of a line segment detected by the Line class.

  A line segment describes a segment of a horizontal line, which start/end
  bein values on the x-axis of the video frames. The level of the line is
  the average grayscale value of the line normalized to the final grayscale
  value of the segment when it is finished drawing.
  """
  def __init__(self, start, end, draw_start):
    self.start = start
    self.end = end
    self.draw_start = draw_start
    self.draw_end = None
    self.level = 0

  def UpdateLevel(self, normalized):
    """Update the level of this segment from a normalized profile.

    See Line._CalculateNormalizedProfile for information on this profile.
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
  """Represents a straight horizontal line drawn on the devices screen.

  It detects line segments being drawn. For initialization it requires an image
  of the fully drawn, non occluded line, which will be called target line. Per
  default the line is expected to be drawn from left to right, but it
  automatically detects if the direction is reversed and sets self.reverse to
  True.

  frame: A Frame instance of an image showing the target line.
  draw_end_thresh: How much of the target color does a line segment have
                   to reach to be considered fully drawn? (Default: 0.9)

  Line.found: True if the line has been found.
  Line.target_shape: The shape object of the target line.
  Line.segments: An array of all line segments that have been detected so far.
  Line.reverse: True if the line is being drawn from right to left.
  Line.debug_canvas: If Update is called with debug=True, this will contain
                    a Canvas object showing debug information.
  """
  def __init__(self, frame, draw_end_thresh=0.9, debug=False):
    self.found = False
    self.target_shape = None
    self.segments = []
    self.debug_canvas = None
    self.reverse = False

    self._line_end = None
    self._target_profile = None
    self._target_left = None
    self._target_right = None
    self._target_length = None
    self._draw_end_thresh = draw_end_thresh

    self._DetectTargetLine(frame, debug)

  def _DetectTargetLine(self, frame, debug=False):
    """Detect the final line that is to be drawn."""
    def is_target_line(region, labels, debug=False):
      if debug:
        print region.label, region.area, region.eccentricity, region.orientation
      return (region.area > 500 and # large size
              region.eccentricity > 0.99 and # very elongated
              np.abs(region.orientation) < 0.1) # horizontally oriented

    # find object fitting the is_target_line function
    binary = frame.reflectance < 0.9
    self.target_shape = Shape.Find(binary, is_target_line, debug=debug,
                                   required=True)
    self._target_left = self.target_shape.left
    self._target_right = self.target_shape.right
    self._target_length = self._target_right - self._target_left

    # add margin to account for camera shake
    self.target_shape = self.target_shape.WithMargin(5, 5)

    # isolate the line in white on black background
    isolated_line = (1.0 - frame.reflectance) * self.target_shape.mask

    # project the image along the x axis. This profile is later
    # used for normalization
    self._target_profile = np.sum(isolated_line, 0)

    if debug:
      res = Canvas(frame.cropped)
      res.DrawContour([0, 1, 0], self.target_shape)

      Viewer.DebugView(isolated_line=isolated_line,
                       contour=res.image)

  def _CalculateNormalizedProfile(self, frame):
    r"""Calculate a normalized profile of the line.

    To ease calculations this method isolates and projects the line onto
    the X axis. This turns the line detection from a 2D into a 1D problem.

    The profile of a line roughly looks like this:
      ____________________
                          \                       _
                           \_                    / \
                             \__________________/   \___
            ^            |----|        ^          ^
       fully drawn     transition   no line     robot
      line segments       area       drawn      finger

    The profile is normalized in relation to the profile of the target line.
    """
    # Isolate the line in white on black background and calculate profile
    isolated_line = (1.0 - frame.reflectance) * self.target_shape.mask
    profile = np.sum(isolated_line, 0)

    # To normalize, we divide by the target profile. However in areas
    # of the picture where there is no line, the target profile will be close
    # to zero which will cause numerical instabilities.
    # To prevent this we normalize only areas where the line is present and
    # assume everything else to be zero.
    normalized = np.zeros(profile.shape)
    line_area = [self._target_profile > 0.1]
    normalized[line_area] = (profile[line_area] /
                             self._target_profile[line_area])
    normalized = np.clip(normalized, 0, 1)
    return normalized

  def _FindLine(self, normalized):
    """Search profile for the beginning of a line draw.

    Since the robot finger is passing through the same area, we have to
    reject the robot finger and identify the peak in the profile that
    represents the line.

    Returns a tuple (start, end) if the line is _found and sets
    self.reverse if the line is drawn from right to left.
    """
    # segment objects on profile line (1D version of shape detection)
    segmentation = (normalized > 0.1).astype(np.int)
    segmentation_diff = np.diff(segmentation)

    objects = []
    object_start = 0
    for i in range(len(segmentation_diff)):
      if segmentation_diff[i] > 0:
        object_start = i
      elif segmentation_diff[i] < 0:
        objects.append((object_start, i))

    # find leftmost and rightmost objects
    leftmost_object = min(objects, key=lambda o: o[0])
    rightmost_object = max(objects, key=lambda o: o[1])

    # The first object will be the robot finger.
    if len(objects) <= 1:
      return None

    # check if the object is at the start or end of the target line
    if leftmost_object[0] < self._target_left + 5:
      line = leftmost_object
      self.reverse = False
    elif rightmost_object[1] > self._target_right - 5:
      line = rightmost_object
      self.reverse = True
    if not line:
      return None

    # check if the line is dark and long enough
    line_level = np.mean(normalized[line[0]:line[1]])
    line_length = line[1] - line[0]
    if line_level > 0.5 and line_length > 4:
      return line
    return None

  def _FindTransition(self, normalized):
    """Find beginnging and end of transition area in the normalized profile."""
    # Determine directions depending on the direction the line is being drawn
    forward = +1 if not self.reverse else -1
    backward = -1 if not self.reverse else +1
    front = 0 if not self.reverse else len(normalized)
    back = len(normalized) if not self.reverse else 0

    # find transition period around the end of the line
    # the transition starts where the profile starts decreasing from 1 and
    # ends where it hits 0.
    transition_start = self._line_end
    transition_end = self._line_end
    for i in range(self._line_end, front, backward):
      if normalized[i] > 0.99:
        transition_start = i
        break
    for i in range(self._line_end, back, forward):
      if normalized[i] < 0.01:
        transition_end = i
        break
    return (transition_start, transition_end)

  def _AddNewSegments(self, frame, normalized, transition_start,
                      transition_end):
    """Add new segments to self.segments after they have been fully drawn."""
    forward = +1 if not self.reverse else -1
    backward = -1 if not self.reverse else +1

    # Add initial line segment
    if not self.segments:
      self.segments.append(LineSegment(transition_start,
                                       transition_end + backward,
                                       frame.index))

    # Look for potential new segment
    last_segment = self.segments[-1]
    new_segment = LineSegment(last_segment.end + forward,
                              transition_end + backward,
                              frame.index)
    new_segment.UpdateLevel(normalized)

    segment_level_diff = np.abs(last_segment.level - new_segment.level)

    if segment_level_diff < 0.3:
      # segments colors are very close to each other, merge them.
      last_segment.end = new_segment.end
    elif new_segment.length > 2:
      # segment is big enough, append as new segment
      self.segments.append(new_segment)

  def Update(self, frame, debug=False):
    """Search for line segments being drawn.

    This method will return a list of LINE_DRAW_START, LINE_DRAW_END and
    LINE_RESET events as they are happening in the video stream.
    """
    if debug:
      self.debug_canvas = Canvas(frame.cropped)

    events = []
    normalized = self._CalculateNormalizedProfile(frame)

    # Search for start of line drawing
    if not self.found:
      line = self._FindLine(normalized)
      if line:
        self._line_end = line[1] if not self.reverse else line[0]
        self.found = True

    if not self.found:
      return events

    # Update existing segments and create draw events
    for segment in self.segments:
      segment.UpdateLevel(normalized)
      if segment.draw_end is None and segment.level > self._draw_end_thresh:
        segment.draw_end = frame.index
        events.append(Event(segment.draw_start, Event.LINE_DRAW_START,
                            location=segment.end))
        events.append(Event(segment.draw_end, Event.LINE_DRAW_END,
                            location=segment.end))

    # Have all segments disappeared? Line has been reset.
    average_level = np.mean([s.level for s in self.segments
                                     if s.draw_end is not None])
    if len(self.segments) >= 2 and average_level < 0.1:
      events.append(Event(frame.index, Event.LINE_RESET))
      self.found = False
      self._line_end = None
      return events

    # Find transition area and add new line segments to the segment list
    (transition_start, transition_end) = self._FindTransition(normalized)
    self._AddNewSegments(frame, normalized, transition_start, transition_end)
    self._line_end = transition_end

    if debug:
      self.debug_canvas.Plot([1, 0, 0], normalized)
      for segment in self.segments:
        self.debug_canvas.DrawLine([0, 0.5, 0], x=segment.end)

      self.debug_canvas.DrawLine([0.5, 0.5, 0], x=transition_start)
      self.debug_canvas.DrawLine([0.5, 0.5, 0], x=transition_end)
    return events


class Finger(object):
  """Represents the OptoFidelity robot finger.

  Finger.found: Is True when the finger has been detected
  Finger.finger_shape: Is the segmented shape of the finger
  Finger.debug_canvas: If Update is called with debug=True, this will
                       contain a canvas object showing debug info.
  """
  def __init__(self):
    self.found = False
    self.finger_shape = None
    self.debug_canvas = None
    self._location = None

  def Update(self, frame, debug=False):
    """Search for the current location of the finger.

    This method will return a list of FINGER_MOVED events when the finger
    is moving.
    """
    if debug:
      self.debug_canvas = Canvas(frame.reflectance)

    # extend the target area to view the full finger tip
    binary = (frame.reflectance < 0.9)

    # we are looking for a big object that is not very elongated
    # (i.e. not the line)
    def is_finger(region, labels, debug=False):
      if debug:
        print region.label, region.area, region.eccentricity
      return region.area > 2000 and region.eccentricity < 0.95
    self.finger_shape = Shape.Find(binary, is_finger, debug=debug)

    # the finger location is the bottom tip of the detected shape
    if self.finger_shape:
      coords = self.finger_shape.coords
      bottom_row = coords[coords[:, 0] == max(coords[:, 0]), :]
      location = bottom_row[:, 1].mean()
      self.found = True
      if debug:
        self.debug_canvas.DrawContour([0, 1, 0], self.finger_shape)
        self.debug_canvas.DrawLine([0, 1, 0], x=location)
      if self._location != location:
        self._location = location
        return [Event(frame.index, Event.FINGER_MOVED, location=location)]
    else:
      self.found = False

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
import numpy as np
import skimage.morphology as morphology
import skimage.transform as transform

from trace import Event
from videoproc import Viewer, Filter, Shape, Canvas

class Frame(object):
  """This class stores multiple versions and views of a camera frame.

  This class stores a cropped version of the image, enhances it with noise
  filtering and calculates the reflectance.
  """
  def __init__(self, im, prev_im, screen, index=0):
    self.original = im
    self.rectified = im
    self.index = index
    self.screen = screen

    if screen:
      self.crop_shape = screen.shape
      self.rectified = screen.Rectify(im)

    # noise filtered reflectance
    self.reflectance = Filter.Reflectance(self.rectified, disk_size=40,
                                          scale=0.5)
    self.reflectance = Filter.Median(self.reflectance, disk_size=1)

    if prev_im is not None:
      self.delta = im - prev_im
    else:
      self.delta = np.zeros(im.shape)

  def DebugView(self):
    Viewer.DebugView(original=self.original,
                     rectified=self.rectified,
                     reflectance=self.reflectance)

class Screen(object):
  """Represents the device screen in the video stream.

  It detects the screen in a video showing the flashing screen and also
  allows for detection of screen flashes in any video.

  Screen.shape is the detected screen shape object.
  """
  BLACK = 0
  WHITE = 1
  UNDEFINED = -1

  def __init__(self, screen=None, no_change_thresh=0.02,
               change_thresh=0.9):
    """Initialize empty or by providing a pre-calculated screen."""
    self.no_change_thresh = no_change_thresh
    self.change_thresh = change_thresh
    self.rect_scaling = 1.2

    # Calibration information
    self.shape = None
    self.rect_transform = None
    self.on_image = None
    self.on_profile = None
    self.off_image = None
    self.off_profile = None

    # Stateful information
    self.color = Screen.UNDEFINED
    self.last_no_draw_time = None
    self.debug_canvas = None

    if screen:
      self.shape = screen.shape
      self.rect_transform = screen.rect_transform
      self.on_image = screen.on_image
      self.on_profile = screen.on_profile
      self.off_image = screen.off_image
      self.off_profile = screen.off_profile

  def Save(self, hdf5):
    hdf5.create_dataset("shape", data=self.shape.mask)
    hdf5.create_dataset("on_image", data=self.on_image)
    hdf5.create_dataset("on_profile", data=self.on_profile)
    hdf5.create_dataset("off_image", data=self.off_image)
    hdf5.create_dataset("off_profile", data=self.off_profile)

  @classmethod
  def Load(self, hdf5):
    screen = Screen()
    screen.shape = Shape(mask=hdf5["shape"][()])
    screen.on_image = hdf5["on_image"][()]
    screen.on_profile = hdf5["on_profile"][()]
    screen.off_image = hdf5["off_image"][()]
    screen.off_profile = hdf5["off_profile"][()]
    screen.rect_transform = screen.EstimateRectTransform()
    return screen

  def Mirrored(self):
    """Returns horizontally mirrored Screen object."""
    screen_copy = Screen(screen=self)
    screen_copy.shape = Shape(np.fliplr(self.shape.mask))
    screen_copy.rect_transform = screen_copy.EstimateRectTransform()
    screen_copy.on_image = np.fliplr(self.on_image)
    screen_copy.on_profile = self.on_profile[::-1]
    screen_copy.off_image = np.fliplr(self.off_image)
    screen_copy.off_profile = self.off_profile[::-1]
    return screen_copy

  def EstimateRectTransform(self):
    """Estimates transformation from rectified device screen to video frame.

    Since transform.warp is doing inverse transformations, this matrix
    transform object can be used to rectify the screen in the video frame.
    """
    # Approximate rectangle from screen shape.
    dest_coords = self.shape.ApproximatePolygon(4)
    # Coords for transforms are x/y, when indexing y/x. So we have to switch.
    dest_coords = dest_coords[:, ::-1]

    # Coordinates in target image. Slightly inflates size so we are not losing
    # any information during warping.
    height = int(self.shape.height * self.rect_scaling)
    width = int(self.shape.width * self.rect_scaling)
    source_coords = np.array((
        (0, 0),
        (width, 0),
        (width, height),
        (0, height)
    ))
    tform = transform.ProjectiveTransform()
    tform.estimate(source_coords, dest_coords)
    return tform

  def Rectify(self, image):
    """Rectify the device screen from a video frame.

    The resulting image will show only the screen, warped to be rectangular.
    """
    height = int(self.shape.height * self.rect_scaling)
    width = int(self.shape.width * self.rect_scaling)
    res = transform.warp(image, self.rect_transform,
                         output_shape=(height, width))
    return res.astype(image.dtype)

  def Unrectify(self, image=None, coords=None):
    """Reverse rectification from device screen image into a video frame.

    The resulting image will show only the screen, warped to be rectangular.
    """
    if image is not None:
      res = transform.warp(image, self.rect_transform.inverse,
                           output_shape=self.shape.mask.shape)
      return res.astype(image.dtype)
    if coords is not None:
      res = self.rect_transform(coords)
      return res[0, 0], res[0, 1]

  def DetectScreen(self, frames, debug=False):
    """Detect the devices flashing screen.

    The frames argument has to be a python iterator that yields
    video frames. Those video frames have to show the device's screen
    flashing black and white.
    """
    # Extract information from video frames. We need the following information:
    # Image of the screen off (min average grayscale)
    # Image of the screen on (max average grayscale)
    # And the accumulative difference between frames to find the area that
    # is changing the most.
    i, prev_frame = frames.next()
    delta_accum = np.zeros(prev_frame.shape)
    on_frame = prev_frame
    on_frame_mean = np.mean(prev_frame)
    off_frame = on_frame
    off_frame_mean = on_frame_mean

    for i, frame in frames:
      delta = np.abs(frame - prev_frame)
      delta_accum += delta

      mean = np.mean(frame)
      if mean > on_frame_mean:
        on_frame = frame
        on_frame_mean = mean
      if mean < off_frame_mean:
        off_frame = frame
        off_frame_mean = mean
      prev_frame = frame
    delta_accum = Filter.Equalize(delta_accum)

    # Threshold the delta. The largest connected component is the screen.
    binary = Filter.OtsuSegmentation(delta_accum)
    binary = morphology.binary_closing(binary, morphology.disk(2))
    binary = morphology.binary_erosion(binary, morphology.disk(4))
    self.shape = Shape.FindMax(binary, lambda p: p.area)

    # Estimate rectification transformation
    self.rect_transform = self.EstimateRectTransform()

    # Calculate profile for screen on and off in cropped space
    self.on_image = self.Rectify(on_frame)
    self.off_image = self.Rectify(off_frame)
    self.on_profile = Filter.ExtractProfile(self.on_image)
    self.off_profile = Filter.ExtractProfile(self.off_image)

    if debug:
      res = Canvas(prev_frame)
      res.DrawContour([1, 0, 0], self.shape)
      Viewer.DebugView(accum=delta_accum,
                       shape=res.image,
                       rectified_on=self.on_image,
                       rectified_off=self.off_image)
    return True

  def Preprocess(self, frame, debug=False):
    """Preprocessing step to process frame into more compact data.

    This method returns data to be passed to GenerateEvents. This method
    is stateless and can be called on any frames out of order."""
    return Filter.ExtractProfile(frame.rectified, self.on_profile,
                                 self.off_profile)

  def GenerateEvents(self, preprocess_data, frame_index, debug_frame=None):
    """Generate Screen events from sequential preprocessed data.

    Returns a list of events that will contain SCREEN_DRAW_START
    and SCREEN_DRAW_END events as they happen in the video stream.
    This method is stateful, requires data generated by Preprocess and has to
    be called with this data from frames in sequential order.
    """
    events = []
    profile = preprocess_data

    if self.color == Screen.UNDEFINED:
      self.color = Screen.BLACK if np.mean(profile) < 0.5 else Screen.WHITE

    if debug_frame:
      self.debug_canvas = Canvas(debug_frame.rectified)

    # we are only looking at first and last 10 pixels of the profile, where the
    # screen draws start and end.
    segment = [profile[:10], profile[-10:]]
    min_level = np.min(segment)
    max_level = np.max(segment)

    # Note the last time the profile stays below the no_change threshold. This
    # is the time index just before the draw starts.
    # If the threshold exceeds the change threshold we consider the draw
    # done and generate both the start and end draw event.
    if self.color == Screen.BLACK:
      if max_level < self.no_change_thresh:
        self.last_no_draw_time = frame_index
      elif min_level > self.change_thresh:
        self.color = Screen.WHITE
        events.append(Event(self.last_no_draw_time + 1, Event.SCREEN_DRAW_START,
                            color="White"))
        events.append(Event(frame_index, Event.SCREEN_DRAW_END, color="White"))

    # Analogous to the black logic.
    elif self.color == Screen.WHITE:
      if min_level > 1.0 - self.no_change_thresh:
        self.last_no_draw_time = frame_index
      elif max_level < 1.0 - self.change_thresh:
        self.color = Screen.BLACK
        events.append(Event(self.last_no_draw_time + 1, Event.SCREEN_DRAW_START,
                            color="Black"))
        events.append(Event(frame_index, Event.SCREEN_DRAW_END, color="Black"))

    if debug_frame:
      self.debug_canvas.Plot([1, 0, 0], profile)

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
  """Represents a straight horizontal line drawn on the devices screen.

  It detects line segments being drawn. For initialization it requires an image
  of the fully drawn, non occluded line, which will be called target line. Per
  default the line is expected to be drawn from left to right, but it
  automatically detects if the direction is reversed and sets self.reverse to
  True.

  draw_end_thresh: How much of the target color does a line segment have
                   to reach to be considered fully drawn? (Default: 0.9)

  Line.found: True if the line has been found.
  Line.target_shape: The shape object of the target line.
  Line.segments: An array of all line segments that have been detected so far.
  Line.reverse: True if the line is being drawn from right to left.
  Line.debug_canvas: If Update is called with debug=True, this will contain
                    a Canvas object showing debug information.
  """
  def __init__(self, draw_end_thresh=0.9):
    self._draw_end_thresh = draw_end_thresh

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

    self.debug_canvas = None

  def DetectTargetLine(self, frame, debug=False):
    """Detect the final line that is to be drawn.

    The parameter frame has to be a Frame instance from an image showing the
    non-occluded target line.
    Returns False if the detection failed.
    """
    def is_target_line(region, labels, debug=False):
      if debug:
        print region.label, region.area, region.eccentricity, region.orientation
      return (region.area > 500 and # Large size
              region.eccentricity > 0.99 and # Very elongated
              np.abs(region.orientation) < 0.1) # Horizontally oriented

    # Find object fitting the is_target_line function.
    binary = frame.reflectance < 0.9
    self.target_shape = Shape.Find(binary, is_target_line, debug=debug)
    if not self.target_shape:
      return False

    self._target_left = self.target_shape.left
    self._target_right = self.target_shape.right

    # Add margin to account for camera shake.
    self.target_shape = self.target_shape.WithMargin(5, 5)

    # Calculate profile of drawn line and empty screen as reference.
    self._drawn_profile = Filter.ExtractProfile(
        (1 - frame.reflectance) * self.target_shape.mask)

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
    segmentation = (profile > 0.1).astype(np.int)
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
    if leftmost_object[0] < self._target_left + 5:
      line = leftmost_object
      self.reverse = False
    elif rightmost_object[1] > self._target_right - 5:
      line = rightmost_object
      self.reverse = True
    if not line:
      return None

    # check if the line is dark and long enough
    line_level = np.mean(profile[line[0]:line[1]])
    line_length = line[1] - line[0]
    if line_level > 0.5 and line_length > 4:
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
      if profile[i] > 0.99:
        transition_start = i
        break
    for i in range(self._line_end, back, forward):
      if profile[i] < 0.01:
        transition_end = i
        break
    return (transition_start, transition_end)

  def _AddNewSegments(self, frame_index, profile, transition_start,
                      transition_end):
    """Add new segments to self.segments after they have been fully drawn."""
    forward = +1 if not self.reverse else -1
    backward = -1 if not self.reverse else +1

    # Add initial line segment
    if not self.segments:
      self.segments.append(LineSegment(transition_start,
                                       transition_end + backward,
                                       frame_index))

    # Look for potential new segment
    last_segment = self.segments[-1]
    new_segment = LineSegment(last_segment.end + forward,
                              transition_end + backward,
                              frame_index)
    new_segment.UpdateLevel(profile)

    segment_level_diff = np.abs(last_segment.level - new_segment.level)

    if segment_level_diff < 0.3:
      # segments colors are very close to each other, merge them.
      last_segment.end = new_segment.end
    elif new_segment.length > 2:
      # segment is big enough, append as new segment
      self.segments.append(new_segment)

  def Preprocess(self, frame, debug=False):
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
    return Filter.ExtractProfile(1 - frame.reflectance,
                                 self._drawn_profile)

  def GenerateEvents(self, preprocess_data, frame_index, debug_frame=None):
    """Generate Line events from sequential preprocessed data.

    Returns a list of LINE_DRAW_START, LINE_DRAW_END and LINE_RESET events as
    they are happening in the video stream.
    This method is stateful, requires data generated by Preprocess and has to
    be called with this data from frames in sequential order.
    """
    events = []
    profile = preprocess_data

    if debug_frame:
      self.debug_canvas = Canvas(debug_frame.rectified)
      self.debug_canvas.Plot([1, 0, 0], profile)

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
      if segment.draw_end is None and segment.level > self._draw_end_thresh:
        segment.draw_end = frame_index
        events.append(Event(segment.draw_start, Event.LINE_DRAW_START,
                            location=segment.end))
        events.append(Event(segment.draw_end, Event.LINE_DRAW_END,
                            location=segment.end))

    # Have all segments disappeared? Line has been reset.
    average_level = np.mean([s.level for s in self.segments
                                     if s.draw_end is not None])
    if len(self.segments) >= 2 and average_level < 0.1:
      events.append(Event(frame_index, Event.LINE_RESET))
      self.found = False
      self._line_end = None
      return events

    # Find transition area and add new line segments to the segment list
    (transition_start, transition_end) = self._FindTransition(profile)
    self._AddNewSegments(frame_index, profile, transition_start,
                         transition_end)
    self._line_end = transition_end

    if debug_frame:
      self.debug_canvas.Plot([1, 0, 0], profile)
      for segment in self.segments:
        self.debug_canvas.DrawHLine([0, 0.5, 0], segment.end,
                                    self.target_shape.center_y)

      self.debug_canvas.DrawHLine([0.5, 0.5, 0], transition_start,
                                  self.target_shape.center_y)
      self.debug_canvas.DrawHLine([0.5, 0.5, 0], transition_end,
                                  self.target_shape.center_y)
    return events


class Finger(object):
  """Represents the OptoFidelity robot finger.

  Finger.found: Is True when the finger has been detected
  Finger.finger_shape: Is the segmented shape of the finger
  Finger.debug_canvas: If Update is called with debug=True, this will
                       contain a canvas object showing debug info.
  """
  def __init__(self, screen):
    self.screen = screen
    self.found = False
    self.finger_shape = None
    self.debug_canvas = None
    self.location = None
    self.led_switching = False

  def Preprocess(self, frame, debug=False):
    """Preprocessing step to process frame into more compact data.

    This method returns data to be passed to GenerateEvents. This method
    is stateless and can be called on any frames out of order."""
    # extend the target area to view the full finger tip
    binary = (frame.reflectance < 0.95)

    # we are looking for a big object that is not very elongated
    # (i.e. not the line)
    def is_finger(region, labels, debug=False):
      if debug:
        print (region.label, region.area, region.eccentricity, region.bbox[0],
              region.bbox[2])
      return (region.area > 1000 and region.eccentricity < 0.95 and
              region.bbox[0] < 5 and region.bbox[2] < labels.shape[0] - 5)
    finger_shape = Shape.Find(binary, is_finger, debug=debug)
    location = None

    # the finger location is the bottom tip of the detected shape
    if finger_shape:
      coords = finger_shape.coords
      bottom_row = coords[coords[:, 0] == max(coords[:, 0]), :]
      location = bottom_row[:, 1].mean()

    # Look for a large amount of change outside of the screen area, i.e. a
    # flashing LED:
    mask = ~self.screen.shape.WithMargin(10, 10).mask
    delta = np.abs(frame.delta) * mask
    # Filter out Noise, the flash should be at least 5 pixels big.
    delta = Filter.Min(delta, disk_size=5)
    # Determine on/off state of the LED.
    led_color = np.mean(frame.original[delta > 0.2])
    return (location, finger_shape, np.max(delta), led_color)

  def GenerateEvents(self, preprocess_data, frame_index, debug_frame=None):
    """Search for the current location of the finger.

    This method will return a list of FINGER_MOVED events when the finger
    is moving.
    """
    events = []

    if debug_frame:
      self.debug_canvas = Canvas(debug_frame.original,
                                 debug_frame.screen.Unrectify)

    (new_location, self.finger_shape, max_delta, led_color) = preprocess_data
    self.found = new_location is not None

    # Report new location if location has changed but not changed too much.
    if (new_location is not None and self.location != new_location and
        (self.location is None or np.abs(self.location - new_location) < 5)):
      self.location = new_location
      events.append(Event(frame_index, Event.FINGER_MOVED,
                          location=new_location))

    # If there is a strong change we expect it to be the flashing LED
    if max_delta > 0.2:
      # Use the led_switching flag to prevent multiple events
      if not self.led_switching:
        self.led_switching = True
        if led_color > 0.5:
          events.append(Event(frame_index, Event.FINGER_DOWN))
        else:
          events.append(Event(frame_index, Event.FINGER_UP))
    else:
      self.led_switching = False

    if debug_frame:
      if self.finger_shape:
        self.debug_canvas.DrawContour([0, 1, 0], self.finger_shape)
        self.debug_canvas.DrawHLine([0, 1, 0], self.location,
                                    self.finger_shape.bottom)

    return events

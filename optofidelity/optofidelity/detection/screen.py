# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import numpy as np
import skimage.morphology as morphology
import skimage.transform as transform

from optofidelity.trace import Event
from optofidelity.videoproc import Viewer, Filter, Shape, Canvas


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

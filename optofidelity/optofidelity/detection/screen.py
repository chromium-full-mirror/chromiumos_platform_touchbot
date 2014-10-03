# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import numpy as np
import skimage.morphology as morphology
import skimage.transform as transform

from optofidelity.detection.trace import Event
from optofidelity.videoproc import Canvas, Filter, Shape, VideoException, Viewer
from optofidelity.detection.detector import Detector

class TestArea(object):
  """Detects the test area on a device.

  This class can detect the flashing test area and can rectify images
  to show only this area.
  """
  def __init__(self):
    self.rect_scaling = 1.2

    self.shape = None
    self.rect_transform = None
    self.on_image = None
    self.on_profile = None
    self.off_image = None
    self.off_profile = None

  def Save(self, hdf5):
    hdf5.create_dataset("shape", data=self.shape.mask)
    hdf5.create_dataset("on_image", data=self.on_image)
    hdf5.create_dataset("on_profile", data=self.on_profile)
    hdf5.create_dataset("off_image", data=self.off_image)
    hdf5.create_dataset("off_profile", data=self.off_profile)

  @classmethod
  def Load(self, hdf5):
    test_area = TestArea()
    test_area.shape = Shape(mask=hdf5["shape"][()])
    test_area.on_image = hdf5["on_image"][()]
    test_area.on_profile = hdf5["on_profile"][()]
    test_area.off_image = hdf5["off_image"][()]
    test_area.off_profile = hdf5["off_profile"][()]
    test_area.rect_transform = test_area.EstimateRectTransform()
    return test_area

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

  def FindOnOffFrames(self, frames):
    """Search for brightest and darkest frames in a frames iterator."""
    i, prev_frame = frames.next()
    on_frame = prev_frame
    on_frame_mean = np.mean(on_frame)
    off_frame = on_frame
    off_frame_mean = np.mean(off_frame)

    for i, frame in frames:
      mean = np.mean(frame)
      if mean > on_frame_mean:
        on_frame = frame
        on_frame_mean = mean
      if mean < off_frame_mean:
        off_frame = frame
        off_frame_mean = mean
      prev_frame = frame
    return on_frame, off_frame

  def Detect(self, frames, debug=False):
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
    on_frame, off_frame = self.FindOnOffFrames(frames)
    delta = Filter.Truncate(on_frame - off_frame)

    # Find screen shape
    def is_screen(region, labels, debug=False):
      if debug:
        print region.label, region.area, region.solidity
      return (region.area > 10000 and # Large enough size
              region.solidity > 0.9) # No holes
    binary = delta > 0.5
    binary = morphology.binary_closing(binary, morphology.disk(2))
    binary = morphology.binary_erosion(binary, morphology.disk(4))
    self.shape = Shape.Find(binary, is_screen, required=True, debug=debug)

    # create a 1px rectangle mask along the edge of the video frame
    # if the screen mask overlaps in too many pixels with this rectangle,
    # the screen is probably outside the viewport of the camera.
    width, height = self.shape.mask.shape
    frame_border = np.zeros((width, height), dtype=np.bool)
    frame_border[:, 0] = True
    frame_border[:, height - 1] = True
    frame_border[0, :] = True
    frame_border[width - 1, :] = True
    border_overlap = np.sum(frame_border * self.shape.mask)

    if border_overlap > 10:
      raise VideoException("Screen out of camera view")

    # Estimate rectification transformation
    self.rect_transform = self.EstimateRectTransform()

    # Calculate profile for screen on and off in cropped space
    self.on_image = self.Rectify(on_frame)
    self.off_image = self.Rectify(off_frame)
    self.on_profile = Filter.ExtractProfile(self.on_image)
    self.off_profile = Filter.ExtractProfile(self.off_image)

    if debug:
      res = Canvas(on_frame)
      res.DrawContour([1, 0, 0], self.shape)
      Viewer.DebugView(delta=delta,
                       shape=res.image,
                       rectified_on=self.on_image,
                       rectified_off=self.off_image)
    return True

  def NormalizedBrightness(self, rectified_frame, slice_or_mask=None):
    """Returns normalized average brightness of frame.

    The brightness is normalized to 0 being the average brightness of the
    screen being black and 1 the average brightness of a fully white screen.
    """
    if slice_or_mask is not None:
      mean = np.mean(rectified_frame[slice_or_mask])
      on_mean = np.mean(self.on_image[slice_or_mask])
      off_mean = np.mean(self.off_image[slice_or_mask])
    else:
      mean = np.mean(rectified_frame[:])
      on_mean = np.mean(self.on_image[:])
      off_mean = np.mean(self.off_image[:])
    return (mean - off_mean) / (on_mean - off_mean)

  def VerifyFrame(self, frame, debug=False):
    """Check frame for camera shifts or lighting changes."""
    rectified = self.Rectify(frame)
    width, height = rectified.shape

    # calculate overall mean and mean along screen edges
    mean = self.NormalizedBrightness(rectified)
    top_mean = self.NormalizedBrightness(rectified, np.s_[:, 0])
    left_mean = self.NormalizedBrightness(rectified, np.s_[0, :])
    bottom_mean = self.NormalizedBrightness(rectified, np.s_[:, height - 1])
    right_mean = self.NormalizedBrightness(rectified, np.s_[width - 1, :])
    edge_means = [top_mean, left_mean, bottom_mean, right_mean]

    if debug:
      print "Overall mean:", mean
      print "Edge means:", edge_means

    # The brightness is normalized to the black screen being 0 and the white
    # screen being 1. If the lighting changed, the normalized brightness will
    # be outside the [0, 1] range.
    if mean > 1.1 or mean < -0.1:
      raise VideoException("Lighting changed.")

    # If the bezel shifted into the screen the deviation of the edge means
    # from the overall mean will be strong.
    deviations = np.abs(edge_means - mean)
    if np.any(deviations > 0.5):
      raise VideoException("Camera shifted.")


class ScreenFlash(Detector):
  """Represents the device screen in the video stream.

  It detects the screen in a video showing the flashing screen and also
  allows for detection of screen flashes in any video.

  Screen.shape is the detected screen shape object.
  """
  BLACK = 0
  WHITE = 1
  name = "screenflash"

  def __init__(self, no_change_thresh=0.05, change_thresh=0.9):
    """Initialize empty or by providing a pre-calculated screen."""
    self.no_change_thresh = no_change_thresh
    self.change_thresh = change_thresh

    # Stateful information
    self.color = None
    self.last_no_draw_time = 0
    self.debug_canvas = None

  def Initialize(self, video, debug=False):
    """Run sanity checks on the first frame of the video."""
    error_msg = None

    # Calculate profile of the first frame. It should look roughly like this:
    # (Or horizontally mirrored)
    # 1 ____________      ___________________
    #               \   _/
    #                \_/
    #               robot
    #               finger
    # 0
    frame = video.FrameAt(0)
    profile = self.Preprocess(frame, debug)

    # Determine color of the screen via the median of the profile. The median
    # roughly gets rid of the influence of the finger and returns the color
    # level of the screen.
    # The thresholds are very strict to catch any inconsistencies at this point.
    median = np.median(profile)
    if median < 1.0 - self.no_change_thresh:
      self.color = self.BLACK
    elif median > self.no_change_thresh:
      self.color = self.WHITE
    else:
      error_msg = "Inconsistent profile."

    # In GenerateEvents we are only processing the edges of the profile, make
    # sure that those values match up with the color we just determined.
    # This is not the case if the camera shifted slightly or the robot is in the
    # wrong app.
    edge_mean = np.mean([profile[:10], profile[-10:]])
    if ((self.color == self.BLACK and edge_mean > self.no_change_thresh) or
        (self.color == self.WHITE and edge_mean < 1.0 - self.no_change_thresh)):
      error_msg = "Inconsistent edge profile."

    if error_msg:
      if debug:
        print "ERROR:", error_msg
        canvas = Canvas(frame.rectified)
        canvas.Plot([1, 0, 0], profile)
        Viewer.DebugView(profile=canvas.image)
      raise VideoException(error_msg)
    return True

  def Preprocess(self, frame, debug=False):
    """Preprocessing step to process frame into more compact data.

    This method returns data to be passed to GenerateEvents. This method
    is stateless and can be called on any frames out of order."""
    return Filter.ExtractProfile(frame.rectified, frame.test_area.on_profile,
                                 frame.test_area.off_profile)

  def GenerateEvents(self, preprocessed_data, timestamp, debug_canvas=None):
    """Generate Screen events from sequential preprocessed data.

    Returns a list of events that will contain SCREEN_DRAW_START
    and SCREEN_DRAW_END events as they happen in the video stream.
    This method is stateful, requires data generated by Preprocess and has to
    be called with this data from frames in sequential order.
    """
    events = []
    profile = preprocessed_data

    # we are only looking at first and last 10 pixels of the profile, where the
    # screen draws start and end.
    segment = [profile[:10], profile[-10:]]
    min_level = np.min(segment)
    max_level = np.max(segment)

    # Note the last time the profile stays below the no_change threshold. This
    # is the time index just before the draw starts.
    # If the threshold exceeds the change threshold we consider the draw
    # done and generate both the start and end draw event.
    if self.color == self.BLACK:
      if max_level < self.no_change_thresh:
        self.last_no_draw_time = timestamp
      elif min_level > self.change_thresh:
        self.color = self.WHITE
        events.append(Event(self.last_no_draw_time + 1, Event.SCREEN_DRAW_START,
                            color="White"))
        events.append(Event(timestamp, Event.SCREEN_DRAW_END, color="White"))

    # Analogous to the black logic.
    elif self.color == self.WHITE:
      if min_level > 1.0 - self.no_change_thresh:
        self.last_no_draw_time = timestamp
      elif max_level < 1.0 - self.change_thresh:
        self.color = self.BLACK
        events.append(Event(self.last_no_draw_time + 1, Event.SCREEN_DRAW_START,
                            color="Black"))
        events.append(Event(timestamp, Event.SCREEN_DRAW_END, color="Black"))

    if debug_canvas:
      debug_canvas.Plot([1, 0, 0], profile)

    return events

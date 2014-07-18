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

from videoproc import Viewer, Filter, Shape, Canvas

class Frame(object):
  """This class stores multiple versions and views of a camera frame.

  This class stores a cropped version of the image, enhances it with noise
  filtering and calculates the reflectance.
  """
  def __init__(self, im, crop_shape=None):
    self.original = im
    self.cropped = im

    self.crop_shape = crop_shape
    if crop_shape:
      # crop to bounding box of object
      self.cropped = crop_shape.Cropped(crop_shape.RemoveBackground(im))

    # noise filtering
    self.enhanced = Filter.Median(self.cropped, disk_size=3)
    self.enhanced = Filter.Equalize(self.enhanced)

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

  Screen.draw_ended will be True after the device finished drawing a switch
                    between black and white screen color.
  Screen.color is set to Screen.WHITE or Screen.BLACK depending on the current
               color of the screen.
  Screen.shape is the detected screen segmentation object.
  """
  BLACK = 0
  WHITE = 1

  def __init__(self, shape=None, frames=None, debug=False):
    self.draw_ended = False
    self.color = Screen.WHITE
    self.shape = shape

    self.prev_draw_avg = None
    self.prev_frame_avg = None

    if frames:
      self.DetectScreen(frames, debug)

  def DetectScreen(self, frames, debug=False):
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
    """Check for the screen to flash."""
    self.draw_ended = False
    avg = np.mean(frame.enhanced)

    # init at first frame
    if self.prev_draw_avg is None:
      self.prev_draw_avg = avg
      self.prev_frame_avg = avg
      self.color = avg > 0.5
      return

    # calculate diff to last frame and last draw
    draw_diff = self.prev_draw_avg - avg
    frame_diff = self.prev_frame_avg - avg
    if debug:
      print "avg={} draw_diff={} frame_diff={}".format(avg, draw_diff,
                                                       frame_diff)

    # screen has to have changed enough since last draw,
    # and only little since last frame to determine if drawing is finished.
    if abs(draw_diff) > 0.5 and abs(frame_diff) < 0.02:
      self.draw_ended = True
      self.color = avg > 0.5
      self.prev_draw_avg = avg
    self.prev_frame_avg = avg

class Line(object):
  """Represents a straight horizontal line drawn on the devices screen.

  Line.found is True when the line has been detected and is currently drawing.
  Line.draw_ended will be True after the device finished drawing a new segment
                  of the line.
  Line.location will return the current location of the drawn line.
  Line.direction is set to either Line.RIGHT or Line.LEFT indicating the
                 movement direction of the line.

  Line.target_shape is the segmentation object of the final drawn line.
  Line.line_shape is the segmentation object of the line currently on the
                  screen.
  Line.search_shape is the segmentation object of where the algorithm waits for
                  next segment of the line to be drawn.
  """
  RIGHT = 1
  LEFT = 0

  def __init__(self, frame=None, debug=False):
    self.draw_ended = False
    self.found = False
    self.location = 0
    self.direction = None

    self.line_shape = None
    self.target_shape = None
    self.search_shape = None

    self.prev_draw_avg = None
    self.prev_frame_avg = None

    if frame:
      self.DetectTargetLine(frame, debug)

  def DetectTargetLine(self, frame, debug=False):
    """Detect the final line that is to be drawn.

    You have to provide the video frame that shows the line fully drawn,
    usually the very last frame of the video.
    """
    def is_target_line(region, labels, debug=False):
      if debug:
        print region.label, region.area, region.eccentricity, region.orientation
      return (region.area > 500 and # large size
              region.eccentricity > 0.99 and # very elongated
              np.abs(region.orientation) < 0.1) # horizontally oriented

    # find object fitting the is_target_line function
    binary = ~Filter.OtsuSegmentation(frame.reflectance)
    self.target_shape = Shape.Find(binary, is_target_line, debug=debug)
    self.target_shape = self.target_shape.WithMargin(10, -10)

    if debug:
      res = Canvas(frame.cropped)
      res.DrawContour([1, 0, 0], self.target_shape)
      Viewer.DebugView(cropped=frame.cropped,
                       reflectance=frame.reflectance,
                       binary=binary,
                       contour=res.image)

  def UpdateSearchObj(self):
    # the slice is a vertical rectangle and is intersected with the target mask
    # to build the search mask.
    search_slice = np.zeros(self.target_shape.mask.shape).astype(np.bool)
    if self.direction == Line.RIGHT:
      search_slice[:, self.location:self.location + 5] = True
    else:
      search_slice[:, self.location - 5:self.location] = True
    self.search_shape = Shape(search_slice & self.target_shape.mask)

  def UpdateLineObj(self, frame, debug):
    # segment and blank out everything outside the target line mask
    binary = ~Filter.OtsuSegmentation(frame.reflectance)
    binary[self.target_shape.mask == 0] = 0

    def is_line(region, labels, debug=False):
      if debug:
        print region.label, region.bbox

      # the line is not touching the top or bottom of the target area
      if np.any((labels == region.label) & self.target_shape.horizontal_edges):
        return False

      # the line is touching the left or right edge of the target area
      if np.any((labels == region.label) & self.target_shape.vertical_edges):
        return True
      return False

    self.line_shape = Shape.Find(binary, is_line, debug=debug)
    if self.line_shape:
      # touching left side? line is moving to the right
      if self.line_shape.left < self.target_shape.left + 10:
        self.direction = Line.RIGHT
        self.location = self.line_shape.right
      # touching right side? line is moving to the left
      elif self.line_shape.right > self.target_shape.right - 10:
        self.direction = Line.LEFT
        self.location = self.line_shape.left
      else:
        raise Exception("Line does not touch the target area?!")

      self.UpdateSearchObj()
    self.found = self.line_shape is not None

  def Update(self, frame, debug=False):
    """Search for line segments being drawn."""
    if not self.found:
      self.UpdateLineObj(frame, debug)

    if self.found:
      # average color in search mask
      avg = np.mean(frame.reflectance[self.search_shape.mask])

      # init at first frame
      if self.prev_draw_avg is None:
        self.prev_draw_avg = avg
        self.prev_frame_avg = avg
        return

      # calculate differences in average color
      draw_diff = self.prev_draw_avg - avg
      frame_diff = self.prev_frame_avg - avg
      self.prev_frame_avg = avg

      # screen has to have changed enough since last draw,
      # and only little since last frame to determine if drawing is finished.
      self.draw_ended = abs(draw_diff) > 0.2 and abs(frame_diff) < 0.05

      if self.draw_ended:
        # segment the line and update the search object
        self.UpdateLineObj(frame, debug)
        self.prev_draw_avg = np.mean(frame.reflectance[self.search_shape.mask])

      if debug:
        print "avg={} draw_diff={} frame_diff={}".format(avg, draw_diff,
                                                         frame_diff)

    if debug:
      out = Canvas(frame.original, frame.crop_shape)
      out.DrawContour([1, 0, 0], self.target_shape)
      out.DrawContour([0, 0, 1], self.search_shape)
      out.DrawContour([0, 1, 0], self.line_shape)
      out.Draw([0, 1, 1], self.target_shape.horizontal_edges)
      out.DrawLine([0, 1, 0], x=self.location)
      Viewer.VideoFrame(out.image)


class Finger(object):
  """Represents the OptoFidelity robot finger.

  Line.found is True when the line has been detected and is currently drawing.
  Line.draw_ended will be True after the device finished drawing a new segment
                  of the line.
  Line.location will return the current location of the drawn line.
  Line.direction is set to either Line.RIGHT or Line.LEFT indicating the
                 movement direction of the line.

  Line.target_shape is the segmentation object of the final drawn line.
  Line.line_shape is the segmentation object of the line currently on the
                  screen.
  Line.search_shape is the segmentation object of where the algorithm waits for
                  next segment of the line to be drawn.
  """
  def __init__(self, line):
    self.found = False
    self.location = 0
    self.finger_shape = None
    self.line = line

  def Update(self, frame, debug=False):
    self.found = False

    # extend the target area to view the full finger tip
    binary = (frame.reflectance < 0.9)

    # we are looking for a big object that is not very elongated
    # (i.e. not the line)
    def is_finger(region, labels, debug=False):
      if debug:
        print region.label, region.area, region.eccentricity
      return region.area > 2000 and region.eccentricity < 0.95
    self.finger_shape = Shape.Find(binary, is_finger, debug=debug)

    # the finger location is the top tip of the detected shape
    if self.finger_shape:
      coords = self.finger_shape.coords
      top_row = coords[coords[:, 0] == self.finger_shape.top, :]
      self.location = top_row[:, 1].mean()
      self.found = True

    if debug:
      out = Canvas(frame.reflectance)
      out.DrawContour([0, 1, 0], self.finger_shape)
      out.DrawLine([0, 1, 0], x=self.location)
      Viewer.VideoFrame(out.image)


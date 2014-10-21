# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Video processing tools to processing high speed camera videos.

This file contains various tools for video processing, starting with reading
video files, image filters and segmentation tools to detect objects in the
video as well as tools for visualizing results of a video analysis process.
"""
import matplotlib
matplotlib.use('TkAgg')

import cv2
import matplotlib.pyplot as plt
import numpy as np
import skimage.color
import skimage.transform as transform


class VideoException(Exception):
  """Exceptions during video processing.

  This exception generally tells the system that the image processing failed
  and cannot continue. The system can decide wether to retry the test, or to
  store the associated video for debugging purposes.
  """
  def __init__(self, error, frame=None, image=None):
    Exception.__init__(self)
    self.error = error
    self.image = image
    self.frame = frame

  def DebugView(self):
    print "Video Processing Error:"
    print self
    if self.image:
      Viewer.DebugView(error=self.image)

  def __str__(self):
    frame = "Frame %d: " % self.frame if self.frame else ""
    return frame + self.error

class Viewer(object):
  """Helper for viewing image data."""

  @staticmethod
  def VideoFrame(frame):
    """Display a video frame using OpenCV."""
    cv2.imshow('frame', frame)
    # give cv2 time to display the frame and return eventual key presses
    return cv2.waitKey(1) & 0xFF

  @staticmethod
  def DebugView(cmap_name="gray", **kwargs):
    """Display any number of images using matplotlib.

    The images are provided using keyword arguments, with the argument
    name being used as the image title.
    Optionally you can specify a colormap name as a first argument.
    """
    cmap = plt.get_cmap(cmap_name)

    num_plots = float(len(kwargs))
    num_rows = np.ceil(np.sqrt(num_plots))
    num_cols = np.ceil(num_plots / num_rows)

    plt.figure()
    for i, arg in enumerate(kwargs.items()):
      image = arg[1]
      if image is None:
        continue
      if image.dtype == np.bool:
        image = arg[1].astype(np.float)
      plt.subplot(num_rows, num_cols, i)
      if image.dtype == np.float:
        plt.imshow(arg[1], cmap=cmap, vmin=0, vmax=1)
      else:
        plt.imshow(arg[1], cmap=cmap)
      plt.title(arg[0])
    plt.show()


class Canvas(object):
  """Helper class for drawing contours, lines and masks.

  Allows the use of a transform function tform_fn that is called as
  tform_fn(image=) or tform_fn(coords=) to transform an image or coordinates
  before drawing them. This is used in combination with the Screen.Unrectify
  method to draw shapes and lines that were calculated on rectified images into
  full frame images.
  """

  plot_padding = 10
  """Padding at top and bottom of plots in pixels."""

  # A collection of colors for drawing. Chosen to be clearly visible on black
  # and white video streams. Colors are denoted in [blue, green, red].
  WHITE = [1, 1, 1]
  BLUE = [1, 0, 0]
  GREEN = [0, 0.7, 0]
  RED = [0, 0, 1]
  YELLOW = [0.7, 0.7, 0]
  BLACK = [0, 0, 0]

  def __init__(self, image=None, tform_fn=None):
    self.image = None
    if image is not None:
      self.image = skimage.color.gray2rgb(image)
    self.tform_fn = tform_fn

  def __nonzero__(self):
    return self.image is not None

  def Scaled(self, scale):
    return transform.rescale(self.image, scale)

  def Plot(self, color, plot):
    plot[plot > 1] = 1
    plot[plot < 0] = 0
    if len(plot) > self.image.shape[1]:
      plot = plot[:self.image.shape[1]]

    height = self.image.shape[0] - self.plot_padding * 2
    cols = (height - (plot * height)).astype(np.int) + self.plot_padding
    rows = range(len(plot))
    self.image[cols, rows] = color

  def DrawHLine(self, color, x, y):
    if self.tform_fn:
      (x, y) = self.tform_fn(coords=(x, y))
    for i in (0, 1, 2):
      self.image[:, x, i] = color[i]

  def DrawVLine(self, color, x, y):
    if self.tform_fn:
      (x, y) = self.tform_fn(coords=(x, y))
    for i in (0, 1, 2):
      self.image[y, :, i] = color[i]

  def Draw(self, color, mask):
    if self.tform_fn and (self.image.shape[0] != mask.shape[0] or
                          self.image.shape[1] != mask.shape[1]):
      mask = self.tform_fn(image=mask)
    self.image[mask] = color

  def DrawContour(self, color, shape):
    if shape is None:
      return
    self.Draw(color, shape.contour)

  def DrawShape(self, color, shape):
    if shape is None:
      return
    self.Draw(color, shape.mask)

  def Fill(self, image, tform_fn=None):
    self.image = skimage.color.gray2rgb(image)
    self.tform_fn = tform_fn

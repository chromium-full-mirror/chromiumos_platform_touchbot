# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Video processing tools to processing high speed camera videos.

This file contains various tools for video processing, starting with reading
video files, image filters and segmentation tools to detect objects in the
video as well as tools for visualizing results of a video analysis process.
"""
import cv2
import numpy as np


class VideoException(Exception):
  pass


class Viewer(object):
  """Helper for viewing image data."""

  @staticmethod
  def VideoFrame(frame):
    """Display a video frame using OpenCV."""
    cv2.imshow('frame', frame)
    # give cv2 time to display the frame and return eventual key presses
    return cv2.waitKey(1) & 0xFF

  @staticmethod
  def DebugView(title="", cmap_name="gray", **kwargs):
    """Display any number of images using matplotlib.

    The images are provided using keyword arguments, with the argument
    name being used as the image title.
    Optionally you can specify a colormap name as a first argument.
    """
    import matplotlib.pyplot as plt
    cmap = plt.get_cmap(cmap_name)

    num_plots = float(len(kwargs))
    num_rows = np.ceil(np.sqrt(num_plots))
    num_cols = np.ceil(num_plots / num_rows)

    figure = plt.figure()
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
    figure.canvas.set_window_title(title)
    plt.show()


class Canvas(object):
  """Helper class for drawing contours, lines and masks and simple graphs"""

  PLOT_PADDING = 10
  """Padding at top and bottom of plots in pixels."""

  # A collection of colors for drawing. Chosen to be clearly visible on black
  # and white video streams. Colors are denoted in [blue, green, red].
  WHITE = [1, 1, 1, 1]
  BLUE = [1, 0, 0, 1]
  GREEN = [0, 0.7, 0, 1]
  RED = [0, 0, 1, 1]
  YELLOW = [0.7, 0.7, 0, 1]
  BLACK = [0, 0, 0, 1]

  def __init__(self, buffer):
    self._buffer = buffer

  @classmethod
  def FromShape(cls, shape):
    return cls(np.zeros((shape[0], shape[1], 4)))

  def Transformed(self, transform_function):
    return Canvas(transform_function(self._buffer))

  def BlendWithImage(self, image):
    assert(len(image.shape) == 3)
    assert(image.shape[0] == self._buffer.shape[0])
    assert(image.shape[1] == self._buffer.shape[1])
    assert(image.shape[2] == 3)

    weight = np.zeros(image.shape)
    for i in (0, 1, 2):
      weight[:, :, i] = self._buffer[:, :, 3]
    weighted_image = image * (1 - weight)
    weighted_buffer = self._buffer[:, :, 0:3] * weight
    return weighted_image + weighted_buffer

  def Plot(self, color, plot):
    plot[plot > 1] = 1
    plot[plot < 0] = 0
    if len(plot) > self._buffer.shape[1]:
      plot = plot[:self._buffer.shape[1]]

    height = self._buffer.shape[0] - self.PLOT_PADDING * 2
    cols = (height - (plot * height)).astype(np.int) + self.PLOT_PADDING
    rows = range(len(plot))
    self._buffer[cols, rows] = color

  def DrawHLine(self, color, x):
    for i in (0, 1, 2, 3):
      self._buffer[:, x, i] = color[i]

  def DrawVLine(self, color, y):
    for i in (0, 1, 2, 3):
      self._buffer[y, :, i] = color[i]

  def DrawMask(self, color, mask):
    assert(mask.shape[0] == self._buffer.shape[0])
    assert(mask.shape[1] == self._buffer.shape[1])
    self._buffer[mask] = color

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Video processing tools to processing high speed camera videos.

This file contains various tools for video processing, starting with reading
video files, image filters and segmentation tools to detect objects in the
video as well as tools for visualizing results of a video analysis process.
"""
import os

from safetynet import List, Tuple, TypecheckMeta, typecheck
import numpy as np
import skimage.color

from .io import LoadImage, SaveImage
from .types import BinaryImage, Image, RGBAImage, RGBImage


@typecheck
def DebugView(title="", cmap_name="gray", **kwargs):
  """Display any number of images using matplotlib.

  The images are provided using keyword arguments, with the argument
  name being used as the image title.
  Blocks until the window is closed.

  :param str title: Title of window
  :param str cmap_name: Name of matplotlib colormap to use. Defaults to gray.
  :type kwargs: List[Image]
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


def ImageMatches(image, expected_image_path, force_update=False):
  if force_update or not os.path.exists(expected_image_path):
    SaveImage(expected_image_path, image)
    DebugView(title=os.path.basename(expected_image_path), created_image=image)
    return True

  expected_image = LoadImage(expected_image_path, gray=True)
  actual_image = skimage.color.rgb2gray(image)
  mse = np.mean((expected_image - actual_image) ** 2)
  if mse > 0.01:
    print "Image not matching expected image: %s" % expected_image_path
    DebugView(actual_image=actual_image, expected_image=expected_image)
    return False
  return True


class Canvas(object):
  """Helper class for drawing contours, lines and masks and simple graphs"""
  __metaclass__ = TypecheckMeta

  PLOT_PADDING = 10
  """Padding at top and bottom of plots in pixels."""

  # A collection of colors for drawing. Chosen to be clearly visible on black
  # and white video streams. Colors are denoted in [blue, green, red, alpha].
  WHITE  = (1.0, 1.0, 1.0, 1.0)
  BLUE   = (1.0, 0.0, 0.0, 1.0)
  GREEN  = (0.0, 0.7, 0.0, 1.0)
  RED    = (0.0, 0.0, 1.0, 1.0)
  YELLOW = (0.7, 0.7, 0.0, 1.0)
  BLACK  = (0.0, 0.0, 0.0, 1.0)

  def __init__(self, buffer):
    """
    :type buffer: RGBAImage
    """
    self._buffer = buffer

  @classmethod
  def FromShape(cls, shape):
    """Create canvas from array shape.

    :param Tuple[int, int] shape: (width, height) of canvas
    :rtype Canvas
    """
    return cls(np.zeros((shape[0], shape[1], 4)))

  def Transformed(self, transform_function):
    """Return canvas with buffer transformed by function.

    :rtype Canvas
    """
    return Canvas(transform_function(self._buffer))

  def BlendWithImage(self, image):
    """Blend canvas on top of image.

    :type image: RGBImage
    :rtype RGBImage
    """
    weight = np.zeros(image.shape)
    for i in (0, 1, 2):
      weight[:, :, i] = self._buffer[:, :, 3]
    weighted_image = image * (1 - weight)
    weighted_buffer = self._buffer[:, :, 0:3] * weight
    return weighted_image + weighted_buffer

  def PlotProfile(self, color, profile):
    """Plot normalized function with values 0..1

    This plots the profile along the image, thus the length of the profile array
    should be exactly the same as the width of the canvas.
    The y-value is scaled to stretch the full height of the canvas.

    :type color: Tuple[float, float, float, float]
    :type profile: np.ndarray
    """
    assert(len(profile) == self._buffer.shape[1])
    profile[profile > 1] = 1
    profile[profile < 0] = 0

    height = self._buffer.shape[0] - self.PLOT_PADDING * 2
    cols = (height - (profile * height)).astype(np.int) + self.PLOT_PADDING
    rows = range(len(profile))
    self._buffer[cols, rows] = color

  def DrawVLine(self, color, x):
    """Draw vertical line at x-location.

    :type color: Tuple[float, float, float, float]
    :type x: int
    """
    for i in (0, 1, 2, 3):
      self._buffer[:, x, i] = color[i]

  def DrawHLine(self, color, y):
    """Draw horizontal line at x-location.

    :type color: Tuple[float, float, float, float]
    :type x: int
    """
    for i in (0, 1, 2, 3):
      self._buffer[y, :, i] = color[i]

  def DrawMask(self, color, mask):
    """Fill area of mask with color.

    :type color: Tuple[float, float, float, float]
    :type mask: BinaryImage
    """
    assert(mask.shape[0] == self._buffer.shape[0])
    assert(mask.shape[1] == self._buffer.shape[1])
    self._buffer[mask] = color

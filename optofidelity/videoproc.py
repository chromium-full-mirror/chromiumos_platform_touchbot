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
import math
import matplotlib.pyplot as plt
import numpy as np
import skimage
import skimage.color
import skimage.exposure as exposure
import skimage.filter
import skimage.filter.rank as rank_filter
import skimage.measure as measure
import skimage.morphology as morphology
import skimage.transform as transform

class Shape(object):
  """Describes a segmented shape in an image.

  The shape is represented by a binary image aka mask, in which pixels
  that are part of the shape are True, all others are False.
  """
  def __init__(self, mask, props=None):
    mask = mask.astype(np.bool)
    if props is None:
      # Use the mask as a label image, since we only have one region,
      # with label=1.
      all_props = measure.regionprops(mask)
      if len(all_props) != 1:
        raise ValueError("Mask must have a unique region")
      props = all_props[0]

    self.mask = mask
    self.props = props
    self._contour = None

  def WithMargin(self, row_margin, col_margin):
    """Return a shape inflated with an margin.

    This method will increase the horizontal or vertical size of the shape by
    the specified margin. If the margin is negative, the size will be decreased
    """
    def MorphFn(margin):
      return (morphology.binary_dilation if margin > 0
              else morphology.binary_erosion)

    row_kernel = morphology.rectangle(math.fabs(row_margin), 1)
    col_kernel = morphology.rectangle(1, math.fabs(row_margin))

    mask = self.mask
    mask = MorphFn(row_margin)(mask, row_kernel)
    mask = MorphFn(col_margin)(mask, col_kernel)
    return Shape(mask)

  def RemoveBackground(self, image):
    """Blend out everything that does not belong to this shape."""
    avg = np.mean(image[self.mask])
    copy = image.copy()
    copy[~self.mask] = avg
    return copy

  def Cropped(self, image):
    """Return a view to the image 'image' that is cropped to this shape."""
    return image[self.top:self.bottom, self.left:self.right]

  @property
  def bbox(self):
    return self.props.bbox

  @property
  def top(self):
    return self.bbox[0]

  @property
  def left(self):
    return self.bbox[1]

  @property
  def bottom(self):
    return self.bbox[2]

  @property
  def right(self):
    return self.bbox[3]

  @property
  def coords(self):
    return self.props.coords

  @property
  def contour(self):
    """The inner contour of this shape.

    The contour is a binary image in which only the outer pixels
    surrounding the shape are True."""
    if self._contour is None:
      self._contour = morphology.binary_erosion(self.mask, morphology.disk(1))
      self._contour = self.mask & (~self._contour)
      self._contour = self._contour.astype(np.bool)
    return self._contour

  @property
  def horizontal_edges(self):
    """The horizontal component of the inner contour."""
    # Dilate with structure element:
    # 1 0 1
    # 1 0 1
    # 1 0 1
    elem = np.ones((3, 3), np.bool)
    elem[:, 1] = 0
    neigh1 = morphology.binary_dilation(self.contour, elem).astype(np.bool)

    # Dilate with structure element:
    # 1 0 0 0 1
    # 1 0 0 0 1
    # 1 0 0 0 1
    elem = np.ones((3, 5), np.bool)
    elem[:, 1:4] = 0
    neigh2 = morphology.binary_dilation(self.contour, elem).astype(np.bool)

    # combine all 3. This will result in a binary image that only contains
    # pixels which have neighbours 1-2 pixels to the left and right that deviate
    # vertically by 1 pixel at max.
    return neigh1 & neigh2 & self.contour

  @property
  def vertical_edges(self):
    """The vertical component of the inner contour."""
    # Dilate with structure element:
    # 1 1 1
    # 0 0 0
    # 1 1 1
    elem = np.ones((3, 3), np.bool)
    elem[1, :] = 0
    neigh1 = morphology.binary_dilation(self.contour, elem).astype(np.bool)

    # Dilate with structure element:
    # 1 1 1
    # 0 0 0
    # 0 0 0
    # 0 0 0
    # 1 1 1
    elem = np.ones((5, 3), np.bool)
    elem[1:4, :] = 0
    neigh2 = morphology.binary_dilation(self.contour, elem).astype(np.bool)

    # combine all 3. This will result in a binary image that only contains
    # pixels which have neighbours 1-2 pixels to the top and bottom that deviate
    # horizontally by 1 pixel at max.
    return neigh1 & neigh2 & self.contour


  @staticmethod
  def Find(binary_im, match_fn, required=False, debug=False):
    """Search for a unique shape in a binary image that fits match_fn.

    match_fn should have the following signature:
        match_fn(props, labels, debug=False).

    If the debug flag is set, this function will stop and display debug views
    of the data in case of errors.
    """
    matches = []
    def Exit(msg, fatal):
      if fatal:
        raise Exception(msg)
      elif debug:
        print msg

    # find all region props that match_fn returns True for
    labels = measure.label(binary_im)
    for props in measure.regionprops(labels, binary_im):
      if debug:
        is_match = match_fn(props, labels, debug)
        if is_match:
          print props.label, "is match"
      else:
        is_match = match_fn(props, labels)
      if is_match:
        matches.append(props)

    # handle no matches error
    if not matches:
      if debug and required:
        Viewer.DebugView(labels=labels)
      return Exit("Cannot find match for region", required)

    # handle too many matches error
    if len(matches) > 1:
      if debug:
        mask = np.zeros(labels.shape)
        for match in matches:
          mask[labels == match.label] = match.label
        Viewer.DebugView(labels=labels, matches=mask)
      return Exit("Multiple matches for region", True)

    # success
    match = matches[0]
    return Shape(labels == match.label, match)

  @staticmethod
  def FindMax(binary_im, key_fn):
    """Search for an shape in a binary image featuring a maximum value.

    All shape in the binary image are compared by the value returned by
    key_fn e.g. use this to find the largest shape in the image.
    """
    match = None
    labels = measure.label(binary_im)

    props = measure.regionprops(labels, binary_im)
    match = max(props, key=key_fn)
    return Shape(labels == match.label, match)

class VideoReader(object):
  """A wrapper around cv2.VideoCapture.

  This class allows for basic seeking in a video file. Note however
  that seeking backwards is slow, since it has to re-open the video file.
  """
  CV_CAP_PROP_FRAME_COUNT = 7

  def __init__(self, filename):
    self.cap = cv2.VideoCapture(filename)
    self.filename = filename
    self.num_frames = self.cap.get(VideoReader.CV_CAP_PROP_FRAME_COUNT)
    self.interactive = False
    self.current_frame = -1

  def Reset(self):
    self.cap.release()
    self.cap = cv2.VideoCapture(self.filename)
    self.current_frame = -1

  def Skip(self, n):
    """Skip n frames ahead. You can only skip frames forward."""
    for i in range(int(n)):
      if not self.cap.grab():
        return False
      self.current_frame += 1
    return True

  def Seek(self, frame):
    """Jump to a specific frame number. This method is slow, use with care."""
    if frame < 0:
      frame = self.num_frames + frame - 1

    if frame >= self.current_frame:
      frame -= self.current_frame
    else:
      self.Reset()

    self.Skip(frame)

  def FrameAt(self, frame):
    """Return the image at a specific frame number."""
    self.Seek(frame)
    return self.NextFrame()

  def NextFrame(self):
    """Read and return next frame."""
    ret, frame = self.cap.read()
    if ret:
      self.current_frame += 1
      return skimage.img_as_float(frame[:, :, 0])
    return None

  def PrevFrame(self):
    """Read and return previous frame. This method is slow, use with care."""
    self.Seek(self.current_frame - 1)
    return self.NextFrame()

  def EnterInteractive(self):
    """Enable interactive mode in Frames().

    After the interactive mode is enabled, Frames() will stop and wait for
    user input:
      j: go to next frame
      k: go to previous frame
      c: continue playing
    """
    self.interactive = True

  def Frames(self, frameskip=None):
    """Yield frames until the video ends.

    This method might block when the interactive mode is used
    """
    while True:
      if self.interactive:
        key = cv2.waitKey() & 0xFF
        if key == ord('k'):
          frame = self.PrevFrame()
        elif key == ord('j'):
          frame = self.NextFrame()
        elif key == ord('c'):
          self.interactive = False
          frame = self.NextFrame()
        else:
          continue
      else:
        frame = self.NextFrame()

      if frame is None:
        break
      yield self.current_frame, frame

      if frameskip:
        if not self.Skip(frameskip):
          break

class Filter(object):
  """A collection of commonly used image processing filters."""

  @staticmethod
  def Truncate(image, min_val=0.0, max_val=1.0):
    """Truncate values below 0 or above 1."""
    image = np.copy(image)
    image[image < min_val] = 0.0
    image[image > max_val] = 1.0
    return image

  @staticmethod
  def Equalize(image):
    """Rescale grayscale to range from 0 to 1."""
    return exposure.rescale_intensity(image)

  @staticmethod
  def OtsuSegmentation(image):
    """Return a binary imageage segmented using the Otsu threshold algorithm."""
    t_otsu = skimage.filter.threshold_otsu(image)
    return image > t_otsu

  @staticmethod
  def Median(image, disk_size, scale=1):
    """Median rank order filter."""
    return Filter._ScaledRankOrderFilter(rank_filter.median, image, disk_size,
                                         scale)

  @staticmethod
  def Min(image, disk_size, scale=1):
    """Minimageum rank order filter."""
    return Filter._ScaledRankOrderFilter(rank_filter.minimum, image, disk_size,
                                         scale)

  @staticmethod
  def Max(image, disk_size, scale=1):
    """Maximageum rank order filter."""
    return Filter._ScaledRankOrderFilter(rank_filter.maximum, image, disk_size,
                                         scale)

  @staticmethod
  def _ScaledRankOrderFilter(filter_fn, image, disk_size, scale=1):
    work_image = transform.rescale(image, (scale, scale))
    work_image = filter_fn(work_image, morphology.disk(disk_size))
    work_image = transform.resize(work_image, image.shape)
    return skimage.img_as_float(work_image)

  @staticmethod
  def Reflectance(image, disk_size, scale=1):
    """Return the reflectance part of the image.

    An image A can be described as a multiplication of illuminance I
    and reflectance R: A = I * R. We estimate the illuminance part with
    a strong median rank order filter, then calculate the reflectance."""
    illuminance = Filter.Median(image, disk_size, scale)
    illuminance[illuminance < 1e-5] = 1e-5 # prevent division by 0
    reflectance = image / illuminance
    return Filter.Truncate(reflectance)

  @staticmethod
  def ExtractBlackOnWhite(image, disk_size, scale=1):
    lowpass = Filter.Median(image, disk_size, scale)
    highpass = lowpass - image
    return Filter.Truncate(highpass)

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
      plt.imshow(arg[1], cmap=cmap, vmin=0, vmax=1)
      plt.title(arg[0])
    plt.show()

class Canvas(object):
  """Helper class for drawing contours, lines and masks.

  This class automatically translates cropped objects when
  the crop argument is used. This allows calculations to be
  made in a cropped version of the image, which can then easily
  be displayed in the uncropped image using this class.
  """
  def __init__(self, image, crop=None):
    self.image = skimage.color.gray2rgb(image)
    self.crop = crop
    self.cropped = self.image
    self.top, self.left = (0, 0)
    if crop:
      # note that modifying self.cropped will modify self.image
      self.cropped = crop.Cropped(self.image)
      self.top, self.left = (crop.top, crop.left)

  def DrawLine(self, color, x=None, y=None):
    for i in (0, 1, 2):
      if x is not None:
        self.image[:, x + self.left, i] = color[i]
      if y is not None:
        self.image[y + self.top, :, i] = color[i]

  def Draw(self, color, mask, no_crop=None):
    if no_crop:
      self.image[mask] = color
    else:
      self.cropped[mask] = color

  def DrawContour(self, color, shape, no_crop=None):
    if shape is None:
      return
    if no_crop:
      self.image[shape.contour] = color
    else:
      self.cropped[shape.contour] = color

  def DrawShape(self, color, shape, no_crop=None):
    if shape is None:
      return
    if no_crop:
      self.image[shape.mask] = color
    else:
      self.cropped[shape.mask] = color

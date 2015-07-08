# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of ScreenCalibration."""

import logging
import sys

from safetynet import Tuple, TypecheckMeta
import cv2
import numpy as np
import skimage.morphology as morphology
import skimage.transform as transform

from optofidelity.videoproc import DebugView, Filter, Shape

_log = logging.getLogger(__name__)


class ScreenCalibration(object):
  __metaclass__ = TypecheckMeta

  ENABLE_STABILIZATION = True
  """Enable image stabilization."""

  SHAPE_MARGIN = 12
  """The test area is reduced in size by this margin to account for potential
     camera shake."""

  DIFF_THRESHOLD = 0.2
  """Threshold used on the difference between the on and off image to find
     the test area."""

  CLOSING_KERNEL = morphology.disk(2)
  """Size of the disk shaped kernel used for the closing operation to close
     any holes in the detected shapes that might be caused by noise."""

  MIN_AREA = 5000
  """Minimum area of the screen in square pixels."""

  MIN_SOLIDITY = 0.9
  """Minimum solidity of the test_area."""

  RECTIFICATION_SCALING = 1.2
  """Factor by which the rectified image will be enlarged to make sure we are
     not losing any information due to interpolation."""

  DIFF_UNCHANGED_MAX_MID_RANGE = 0.01
  """If the mid-range value of a diff image exceeds this value it is considered
     to show no change."""

  REFERENCE_MIN_NUM_FRAMES = 6
  """Minimum number of frames to use for building a reference frame."""

  DIFF_CHANGE_MIN_DURATION = 2
  """Minimum number of frames that have to show change to accept it as as
     changing."""

  OUT_OF_VIEW_EDGE_PIXELS = 10
  """How many pixels of the test_area have to be at the edge of the screen
     to consider it being out of view?"""

  MIN_DYNAMIC_RANGE = 0.3
  """Minimum range between black and white."""

  def __new__(cls, black_frame, white_frame):
    """Creates new screen calibration from black and white video frames.

    If the white_frame is all white, the calibration will not do any
    calibration or transformation but return the original images.

    :param np.ndarray black_frame: Video frame of screen being black
    :param np.ndarray white_frame: Video frame of screen being white
    """
    self = super(ScreenCalibration, cls).__new__(cls)
    self.is_identity = np.allclose(white_frame, 1.0)

    if self.is_identity:
      self.shape = Shape(np.ones(white_frame.shape, dtype=np.bool))
      self._rectification_transform = None
    else:
      self.shape = self._CalculateShape(black_frame, white_frame)
      self._rectification_transform = self._EstimateRectTransform(self.shape)
    self.black_reference = self.CameraToScreenSpace(black_frame)
    self.white_reference = self.CameraToScreenSpace(white_frame)
    self.black_frame = black_frame
    self.white_frame = white_frame

    # Detect features for tracking
    image_width = self.black_frame.shape[1]
    self._feature_range = (0, image_width)
    self._good_features = None
    if not self.is_identity:
      space_left = self.shape.left
      space_right = image_width - self.shape.right
      if space_left > space_right:
        # Trim to show only space left of the screen
        self._feature_range = (0, self.shape.left - 100)
      else:
        # Trip to show only space right of the screen
        self._feature_range = (self.shape.right + 200, image_width)
      features_image = self._GetFeaturesImage(self.black_frame)
      self._good_features = cv2.goodFeaturesToTrack(features_image, 200, 0.01,
                                                    30)
    return self

  @property
  def camera_space_shape(self):
    """:returns Tuple[int, int]: Array shape of camera space frames."""
    return self.black_frame.shape

  @property
  def screen_space_shape(self):
    """:returns Tuple[int, int]: Array shape of screen space frames."""
    return self.black_reference.shape

  @classmethod
  def CreateIdentity(cls, frame_shape):
    return cls(np.zeros(frame_shape), np.ones(frame_shape))

  @classmethod
  def FromScreenFlashVideo(cls, video_reader, debug=False):
    """Create screen calibration from a video showing a flashing screen.

    :param VideoReader video_reader
    :param bool debug
    :returns ScreenCalibration
    """
    ref_images = []
    with video_reader.PrefetchEnabled():
      frames = video_reader.Frames()

      # Accumulator to calculate mean images.
      i, prev_frame = frames.next()
      mean_accum = np.zeros(prev_frame.shape)
      mean_accum_num = 0
      last_frame_below_thresh = 0

      for i, frame in frames:
        # Calculate the mid-range value of the inter-frame difference.
        # This reliably describes the general direction of change.
        diff = frame - prev_frame
        midrange = Filter.StableMidRange(diff)

        if np.abs(midrange) < cls.DIFF_UNCHANGED_MAX_MID_RANGE:
          # Add frame to accumulator
          mean_accum += frame
          mean_accum_num += 1
          last_frame_below_thresh = i
        elif i - last_frame_below_thresh > cls.DIFF_CHANGE_MIN_DURATION:
          # The screen is in the process of switching colors.
          if mean_accum_num > cls.REFERENCE_MIN_NUM_FRAMES:
            # We collected enough samples for a solid reference image.
            ref_images.append(mean_accum / mean_accum_num)
            if len(ref_images) >= 2:
              break
          # Reset mean accumulator
          mean_accum_num = 0
          mean_accum = np.zeros(prev_frame.shape)

        _log.debug("%4d: midrange=%.2f, N=%d", i, midrange, mean_accum_num)
        prev_frame = frame

    # Add the last accumulation in case we don't have enough reference images
    if mean_accum_num > cls.REFERENCE_MIN_NUM_FRAMES and len(ref_images) < 2:
      ref_images.append(mean_accum / mean_accum_num)

    if len(ref_images) < 2:
      raise Exception("Cannot find flashing screen")

    if np.mean(ref_images[0]) > np.mean(ref_images[1]):
      return cls(ref_images[1], ref_images[0])
    else:
      return cls(ref_images[0], ref_images[1])

  def _GetFeaturesImage(self, camera_space_frame):
    """Trims image to area not showing the screen nor robot arm.

    Returns a uint8 image for OpenCV
    """
    range_ = self._feature_range
    feature_image = camera_space_frame[:, range_[0]:range_[1]]
    return (feature_image * 255).astype(np.uint8)

  def StabilizeFrame(self, camera_space_frame, debug=False):
    """Stabilizes a frame to line up with the calibration image.
    """
    if self._good_features is None or not self.ENABLE_STABILIZATION:
      return camera_space_frame
    frame = self._GetFeaturesImage(camera_space_frame)
    ref = self._GetFeaturesImage(self.black_frame)

    # Match features
    features, st, err = cv2.calcOpticalFlowPyrLK(ref, frame,
                                                 self._good_features, None)
    # Filter so only features that have been matched are in the list.
    ref_features = self._good_features[st == 1]
    features = features[st == 1]

    # Average the translation between the features
    translation = np.median(features - ref_features, 0)

    # Translate image
    tform = transform.SimilarityTransform(translation=translation)
    stable = transform.warp(camera_space_frame, tform)

    if debug:
      delta = (0.5 + stable - self.black_frame)
      def GetCoords(feature):
        return (int(feature[0] + self._feature_range[0]), int(feature[1]))
      black = (0, 0, 0)
      for good_feature in self._good_features:
        print good_feature[0], GetCoords(good_feature[0])
        cv2.circle(delta, GetCoords(good_feature[0]), 5, black)
      for ref_feature, feature in zip(ref_features, features):
        cv2.line(delta, GetCoords(ref_feature), GetCoords(feature), black, 1)
      DebugView(debug=delta, title="Stabilization Debug")
    return stable

  def NormalizeFrame(self, screen_space_frame):
    """Normalizes color on a frame in screen space.

    :param np.ndarray screen_space_frame
    :returns np.ndarray
    """
    return Filter.Truncate((screen_space_frame - self.black_reference) /
                           (self.white_reference - self.black_reference))

  def Validate(self):
    """Runs some checks on the calibration.

    This method will raise an Exception should the calibration show that
    the screen is not fully shown in the camera view, the dynamic range is
    too small or the screen is not big enough.
    """
    if self.is_identity:
      return
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
    _log.debug("border_overlap=%.2f", border_overlap)

    if border_overlap > self.OUT_OF_VIEW_EDGE_PIXELS:
      raise Exception("Screen out of camera view")

    # Check dynamic range. We need enough resolution to distinguish shades
    # between black and white during later processing.
    dynamic_range = np.mean(self.white_reference - self.black_reference)
    _log.debug("dynamic_range=%.2f", dynamic_range)
    if dynamic_range <  self.MIN_DYNAMIC_RANGE:
      raise Exception("Not enough dynamic range.")

  def CameraToScreenSpace(self, camera_space_frame):
    """Transform camera space frame into screen space.

    :param np.ndarray camera_space_frame
    :returns np.ndarray
    """
    if self.is_identity:
      return camera_space_frame
    height = int(self.shape.height * self.RECTIFICATION_SCALING)
    width = int(self.shape.width * self.RECTIFICATION_SCALING)
    transformed = transform.warp(camera_space_frame,
                                 self._rectification_transform,
                                 output_shape=(height, width))
    return transformed.astype(camera_space_frame.dtype)

  def ScreenToCameraSpace(self, screen_space_frame):
    """Transform screen space frame into camera space.

    :param np.ndarray camera_space_frame
    :returns np.ndarray
    """
    if self.is_identity:
      return screen_space_frame
    transformed = transform.warp(screen_space_frame,
                                 self._rectification_transform.inverse,
                                 output_shape=self.shape.mask.shape)
    return transformed.astype(screen_space_frame.dtype)

  def _EstimateRectTransform(self, shape):
    """Estimates transformation from rectified device screen to video frame.

    :param Shape shape: shape object of the detected screen
    :returns transform.Transform
    """
    # Approximate rectangle from screen shape.
    dest_coords = shape.ApproximatePolygon(4)
    # Coords for transforms are x/y, when indexing y/x. So we have to switch.
    dest_coords = dest_coords[:, ::-1]

    # Coordinates in target image. Slightly inflates target image size so we
    # are not losing too much information during warping.
    height = int(self.shape.height * self.RECTIFICATION_SCALING)
    width = int(self.shape.width * self.RECTIFICATION_SCALING)
    source_coords = np.array((
        (0, 0),
        (width, 0),
        (width, height),
        (0, height)
    ))
    tform = transform.ProjectiveTransform()
    tform.estimate(source_coords, dest_coords)
    return tform

  def _CalculateShape(self, black_frame, white_frame):
    """Detect screen from difference between the black and white frame.

    :returns Shape: shape object of the detected screen
    """
    delta = Filter.Truncate(white_frame - black_frame)

    margin_kernel = morphology.disk(self.SHAPE_MARGIN)
    binary = delta > self.DIFF_THRESHOLD
    binary = morphology.binary_closing(binary, self.CLOSING_KERNEL)
    binary = morphology.binary_erosion(binary, margin_kernel)
    shapes = Shape.Shapes(binary)
    shapes = [s for s in shapes
                if (s.area > self.MIN_AREA and
                    s.props.solidity > self.MIN_SOLIDITY)]
    if not shapes:
      raise Exception("Cannot find screen shape")
    return max(shapes, key=lambda s: s.area)

  def __getnewargs__(self):
    return (self.black_frame, self.white_frame)

  def __getstate__(self):
    return {}

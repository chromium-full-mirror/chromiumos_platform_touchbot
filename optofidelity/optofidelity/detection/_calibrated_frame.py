# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of CalibratedFrame."""

from safetynet import Optional, Tuple, TypecheckMeta
import numpy as np

from optofidelity.util import const_property
from optofidelity.videoproc import Filter, Shape

from .screen_calibration import ScreenCalibration


class CalibratedFrame(object):
  """Represents a video frame after calibration.

  This class gives access to multiple views of the video frame, some in
  screen space, some in camera space.
  Images in camera space are from the perspective of the camera, whereas images
  in screen space have been rectified to show only the screen.
  """
  __metaclass__ = TypecheckMeta

  BRIGHTNESS_OUT_OF_RANGE_THRESH = 0.1
  """Brightness that is out of range by this threshold amout will raise an
     exception."""

  FOREGROUND_MAX_BRIGHTNESS = 0.9
  """Everything below this threshold is considered to be the foreground
     objects on the screen."""

  def __init__(self, frame, prev_frame, screen_calibration, frame_index):
    """
    :param np.ndarray frame
    :param Optional[np.ndarray] prev_frame
    :param Optional[ScreenCalibration] screen_calibration
    :param int frame_index
    """
    self.camera_space_frame = frame
    self.camera_space_prev_frame = prev_frame
    self.frame_index = frame_index

    self._screen_calibration = screen_calibration

  @property
  def has_calibration(self):
    """:returns bool: True if screen calibration is present."""
    return self._screen_calibration is not None

  @const_property
  def screen_space_frame(self):
    """:returns np.ndarray: this frame in screen space."""
    self._require_calibration()
    return self._screen_calibration.CameraToScreenSpace(self.camera_space_frame)

  @const_property
  def screen_space_prev_frame(self):
    """:returns np.ndarray: previous frame in screen space."""
    if self.camera_space_prev_frame is None:
      return None
    self._require_calibration()
    return self._screen_calibration.CameraToScreenSpace(
        self.camera_space_prev_frame)

  @const_property
  def screen_space_normalized(self):
    """:returns np.ndarray: color normalized frame in screen space."""
    self._require_calibration()
    normalized = self._screen_calibration.NormalizeFrame(
        self.screen_space_frame)
    thresh = self.BRIGHTNESS_OUT_OF_RANGE_THRESH
    if (np.any(normalized > 1 + thresh) or np.any(normalized < -thresh)):
      raise ValueError("Brightness is outside of normalized range.")
    return Filter.Truncate(normalized)

  @const_property
  def screen_space_delta(self):
    """:returns np.ndarray: inter-frame delta in screen space."""
    self._require_calibration()
    if self.screen_space_prev_frame is not None:
      return self.screen_space_frame - self.screen_space_prev_frame
    else:
      return np.zeros(self.screen_space_shape)

  @const_property
  def screen_space_foreground(self):
    """:returns np.ndarray: binary image showing foreground in screen space."""
    self._require_calibration()
    return self.screen_space_normalized < self.FOREGROUND_MAX_BRIGHTNESS

  @const_property
  def screen_space_shape(self):
    """:returns Tuple[int, int]: array shape of screen space images."""
    self._require_calibration()
    return self.screen_space_frame.shape

  @const_property
  def camera_space_delta(self):
    """:returns np.ndarray: inter-frame delta in camera space."""
    if self.camera_space_prev_frame is not None:
      return self.camera_space_frame - self.camera_space_prev_frame
    else:
      return np.zeros(self.camera_space_shape)

  @const_property
  def camera_space_screen_shape(self):
    """:returns Shape: shape object representing the screen in camera space."""
    return self._screen_calibration.shape

  @const_property
  def camera_space_shape(self):
    """:returns Tuple[int, int]: array shape of camera space images."""
    return self.camera_space_frame.shape

  def _require_calibration(self):
    if not self._screen_calibration:
      raise ValueError("screen_calibration is required for this operation.")

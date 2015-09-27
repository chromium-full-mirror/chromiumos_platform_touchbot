# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of ScreenCalibration."""

import logging
import sys

from matplotlib import pyplot
from safetynet import Tuple, TypecheckMeta
import cv2
import numpy as np
import skimage.morphology as morphology
import skimage.transform as transform

from optofidelity.util import nputil
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

  OUT_OF_VIEW_EDGE_PIXELS = 10
  """How many pixels of the test_area have to be at the edge of the screen
     to consider it being out of view?"""

  WHITE_LEVEL_MIN = 0.8
  """Minimum level of a the white reference image."""

  WHITE_LEVEL_MAX = 0.95
  """Maximum level of a the white reference image."""

  PWM_COMPENSATION_LEVEL = 0.01
  """Compensate for PWM if the range of colors in the white reference image is
     larger than this value."""

  def __new__(cls, black_frame, white_frame, pwm_pulse=None):
    """Creates new screen calibration from black and white video frames.

    If the white_frame is all white, the calibration will not do any
    calibration or transformation but return the original images.

    :param np.ndarray black_frame: Video frame of screen being black
    :param np.ndarray white_frame: Video frame of screen being white
    """
    self = super(ScreenCalibration, cls).__new__(cls)
    self.is_identity = np.allclose(white_frame, 1.0)

    self.pwm_profile = None
    self.pwm_pulse = None
    self.pwm_pulse_length = None

    if pwm_pulse is not None:
      self.pwm_pulse = pwm_pulse
      self.pwm_profile = np.tile(pwm_pulse, 10)
      self.pwm_pulse_length = len(pwm_pulse)

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
    with video_reader.PrefetchEnabled():
      # Skim through video to find rough location of the screen.
      prev_frame = None
      delta_accum = np.zeros(video_reader.frame_shape)
      for i, frame in video_reader.Frames(step=10):
        if prev_frame is None:
          prev_frame = frame
          continue
        delta = np.abs(frame - prev_frame)
        delta_accum += delta
      shapes = Shape.Shapes(delta_accum > 0.9)
      screen_shape = max(shapes, key=lambda s: s.area)

      # Walk frame-by-frame to find reference image for black and white screen.
      ref_indices = []
      frames = video_reader.Frames()

      i, prev_frame = frames.next()
      change_direction = 0
      change_duration = 0

      for i, frame in frames:
        # Calculate the mid-range value of the inter-frame difference.
        # This reliably describes the general direction of change.
        diff = (frame - prev_frame) * screen_shape.mask
        midrange = Filter.StableMidRange(diff)
        _log.debug("%4d: midrange=%.2f, dir=%d, dur=%d", i, midrange,
                  change_direction, change_duration)

        if change_direction == 0:
          # Once the screen is clearly changing in one direction, make note
          # of the direction.
          if np.abs(midrange) > 0.05:
            change_direction = np.sign(midrange)
            change_duration = 1
        else:
          change_duration += 1
          if np.sign(midrange) != change_direction:
            # Wait until the screen is flipping it's change direction, this is
            # a reference frame we want to pick.
            if change_duration > 3:
              ref_indices.append(i - 1)
              if len(ref_indices) >= 2:
                break
            change_direction = 0
            change_duration = 0

        prev_frame = frame

    if len(ref_indices) < 2:
      raise Exception("Cannot find flashing screen")

    # Identify black and white screen
    black_ref = video_reader.FrameAt(ref_indices[0])
    white_ref = video_reader.FrameAt(ref_indices[1])
    white_index = ref_indices[1]
    if np.mean(black_ref) > np.mean(white_ref):
      (black_ref, white_ref) = (white_ref, black_ref)
      white_index = ref_indices[0]

    # Collect frames for PWM calibration
    (height, width) = video_reader.frame_shape
    pwm_frames = np.zeros((height, width, 6), dtype=np.float)
    for i in range(6):
      pwm_frames[:,:,i] = video_reader.FrameAt(white_index + i)
    white_ref = np.max(pwm_frames, axis=2)

    calibration = cls(black_ref, white_ref)
    calibration.CalibratePWM(pwm_frames)
    return calibration

  def CalibratePWM(self, pwm_frames, debug=False):
    def GetPWMProfile(pwm_frames, index):
      """Returns deviation from white reference as a profile."""
      screen_space_pwm = self.CameraToScreenSpace(pwm_frames[:, :, index])
      delta = self.white_reference - screen_space_pwm
      profile = np.mean(delta, 0)
      return profile

    def ListPWMPulseResponses(pwm_frames):
      """Yields snippets of PWM pulses detected in the pwm_frames."""
      for i in range(0, pwm_frames.shape[2]):
        profile = GetPWMProfile(pwm_frames, i)

        # No PWM artifacts? Great!
        if np.max(profile) - np.min(profile) < 0.2:
          return

        # The PWM will show up as pulses from 0 to 1, when the profile is
        # normalized. The state changes will show us when
        normalized = profile / np.max(profile)
        for start, end in nputil.FindPeaks(normalized, min_value=0.9,
                                           max_slope=0.1, max_mid_range=0.1):
          if start < 10:
            continue
          start = start - 10
          end = np.min((end + 10, len(profile)))
          pulse = profile[start:end]
          yield pulse

    def EstimateAveragePulseResponse(pulse_list):
      """Aligns all pulse responses and returns the averaged pulse response."""
      max_pulse_length = np.max([len(p) for p in pulse_list])
      pulse0 = np.copy(pulse_list[0])
      pulse0.resize(max_pulse_length)

      # Align all pulses to first pulse
      aligned_pulses = []
      for pulse in pulse_list:
        shift = nputil.EstimateShift(pulse0, pulse, "mae", debug=debug)
        matched = nputil.AlignArrays(pulse0, pulse, shift)
        aligned_pulses.append(matched)

      # Slightly overestimate. Overcorrection is less of a problem than under
      # correction.
      estimate = np.max(np.asarray(aligned_pulses), axis=0)
      estimate = estimate * 1.1

      # Force the beginning and end of the response to 0
      base_level = np.max((estimate[:2], estimate[-2:]))
      estimate = estimate - base_level
      estimate[estimate < 0] = 0

      if debug:
        pyplot.figure()
        for pulse in aligned_pulses:
          pyplot.plot(pulse)
        pyplot.plot(estimate, "o")
        pyplot.show()
      return pulse

    def EstimatePulseLength(pulse, pwm_frames):
      """Estimates the frequency of PWM pulses through cross-correlation."""
      lengths = []
      for i in range(0, pwm_frames.shape[2]):
        profile = GetPWMProfile(pwm_frames, i)

        # Correlation shows peaks at the frequency at which pulse repeats in
        # profile.
        corr = np.correlate(pulse, profile, "full")
        corr = corr / np.max(corr)

        # Find strong maximums
        maximums = nputil.FindLocalExtremes(corr)
        filtered_maximums = filter(lambda e: corr[e] > 0.5, maximums)
        sorted_maximums = sorted(filtered_maximums)

        # Distance between maximums is the pulse length
        lengths.extend(np.diff(sorted_maximums))

        if debug:
          pyplot.figure()
          pyplot.subplot(1, 2, 0)
          pyplot.plot(profile)
          pyplot.plot(pulse)
          pyplot.subplot(1, 2, 1)
          pyplot.plot(corr)
          pyplot.plot(sorted_maximums, [corr[e] for e in sorted_maximums], "o")

      if debug:
        pyplot.show()

      return int(np.mean(lengths))

    pulse_list = list(ListPWMPulseResponses(pwm_frames))
    if len(pulse_list) < 4:
      _log.info("No PWM artifact compensation needed.")
      return

    pulse = EstimateAveragePulseResponse(pulse_list)
    length = EstimatePulseLength(pulse, pwm_frames)
    _log.info("Detected PWM with pulse length of %d", length)

    pulse = np.copy(pulse)
    pulse.resize(length)
    self.pwm_pulse = pulse
    self.pwm_profile = np.tile(pulse, 10)
    self.pwm_pulse_length = length

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

  def NormalizeFrame(self, screen_space_frame, pwm_compensation=False,
                     debug=False):
    """Normalizes color on a frame in screen space.

    :param np.ndarray screen_space_frame
    :returns np.ndarray
    """
    normalized = Filter.Truncate((screen_space_frame - self.black_reference) /
                                 (self.white_reference - self.black_reference))

    if not pwm_compensation or self.pwm_profile is None:
      return normalized

    delta = 1.0 - normalized

    mask = delta < 0.8
    profile = np.sum(delta * mask, 0) / np.sum(mask, 0)

    shift = nputil.EstimateShift(profile, self.pwm_profile, "mae",
                                 max_shift=self.pwm_pulse_length, debug=debug)
    pwm_profile = 1.0 - nputil.AlignArrays(profile, self.pwm_profile, shift,
                                           mode="wrap")

    # stretch profile into picture
    stretched = np.tile(pwm_profile, (screen_space_frame.shape[0], 1))
    stretched[stretched < 0.1] = 0.1 # prevent division by 0

    compensated = Filter.Truncate(normalized / stretched)

    if debug:
      DebugView(orig=screen_space_frame, pwm=stretched, compensated=compensated)

    return compensated

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
    _log.info("border_overlap=%.2f", border_overlap)

    if border_overlap > self.OUT_OF_VIEW_EDGE_PIXELS:
      raise Exception("Screen out of camera view")

    white_max = Filter.StableMax(self.white_reference)
    _log.info("white_max=%.2f", white_max)
    if white_max > self.WHITE_LEVEL_MAX:
      raise Exception("Calibration is over exposed")
    if white_max < self.WHITE_LEVEL_MIN:
      raise Exception("Calibration is under exposed")

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
    return (self.black_frame, self.white_frame, self.pwm_pulse)

  def __getstate__(self):
    return {}

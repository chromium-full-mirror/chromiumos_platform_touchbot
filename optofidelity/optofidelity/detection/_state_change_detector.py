# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from matplotlib import pyplot
from safetynet import Optional
import cv2
import numpy as np
import skimage.filters
import skimage.color

from optofidelity.util import nputil
from optofidelity.videoproc import Canvas, DebugView, Filter, Image, Shape

from ._calibrated_frame import CalibratedFrame
from ._detector import Detector
from .events import AnalogStateEvent, StateChangeEvent

_log = logging.getLogger(__name__)

def MeasurePWMProfile(image, height=20):
  top = image.shape[0] - height
  measurement_area = Shape.FromRectangle(image.shape, top=top)
  return measurement_area.CalculateProfile(image)

def MeasurePWM(image, height=20):
  pwm_profile = MeasurePWMProfile(image, height)
  return np.tile(pwm_profile, (image.shape[0], 1))


class StateChangeDetector(Detector):
  """Detects screen switches between two different states."""

  NAME = "state_change"

  SETTLED_THRESHOLDS = dict(max_mean_distance=2.0, window_size=20)
  """Thresholds to identify when a state has settled.
     (see nputil.FindSettlingIndex)"""

  FINGER_SEARCH_AVERAGING_FILTER = 4
  """Number of frames to average for search of finger."""

  def __init__(self, area_of_interest, reference_frame):
    """This detector requires an area of interest mask and a reference frame.

    The state before interaction will be called CLOSED state, whereas the state
    after interaction will be called OPEN state, since most of the tests in this
    category are opening and closing activities.

    :param Optional[Shape] area_of_interest: Describes in which area of
           the screen the state change will happen. The more accurate this mask
           is, the higher the signal to noise ratio will be.
    :param Optional[Image] reference_frame: Normalized screen space picture of
           the screen in the closed state.
    """
    self.area_of_interest = area_of_interest
    self.reference_frame = reference_frame

  @classmethod
  def _FindFingerTouchdown(cls, video_reader, screen_calibration, debug=False):
    def debug_log(msg, *args):
      if debug:
        print msg % args
      _log.debug(msg, *args)

    frame_cache = {}
    def GetFrame(frame_num):
      calib_frame = frame_cache.get(frame_num)
      if calib_frame is None:
        frame = video_reader.FrameAt(frame_num)
        calib_frame = CalibratedFrame(frame, None, screen_calibration, frame_num)
        frame_cache[frame_num] = calib_frame
      return calib_frame

    def GetAveragedNormalizedFrame(frame_num, window_size):
      accum = np.copy(GetFrame(frame_num).screen_space_normalized)
      for i in range(frame_num + 1, frame_num + window_size):
        accum += GetFrame(i).screen_space_normalized
      return accum / window_size

    def FindBottomMostShape(frame_num, frame0):
      """Locate the bottommost shape, which should be the robot finger."""
      accum = np.zeros(frame0.shape)
      for i in range(frame_num, frame_num + 5):
        screen_space_normalized = GetFrame(i).screen_space_normalized
        cleaned = (frame0 - screen_space_normalized)

        # Compensate PWM
        pwm_image = MeasurePWM(cleaned)
        accum += (cleaned - pwm_image)
      accum = skimage.filters.gaussian_filter(accum, 3.0, mode="constant") / 5

      binary = accum > 0.1
      shapes = list(Shape.Shapes(binary))
      shapes = [s for s in shapes if s.area > 100]
      shape = None
      if shapes:
        shape = max(shapes, key=lambda s: s.bottom)

      if debug:
        canvas = Canvas.FromShape(accum.shape)
        if shape:
          canvas.DrawMask(Canvas.BLUE, shape.contour)
        debug_view = canvas.BlendWithImage(skimage.color.gray2rgb(accum))
        cv2.imshow("FindFingerTouchdown", debug_view)

      return shape

    def FindFirstFingerMovement(start_index, step_size, frame0):
      """Find first significant motion of robot finger.

      This algorithm finds the time at which the bottommost shape (the finger)
      starts moving. It works by recursively at decreasing step sizes to
      reduce the number of frames we need to process.
      """
      if step_size < 1:
        step_size = 1

      initial_shape = FindBottomMostShape(0, frame0)
      initial_location = initial_shape.bottom if initial_shape else 0
      debug_log("FindFirstFingerMovement 000: location=%d", initial_location)
      if debug:
        cv2.waitKey()

      for i in range(start_index + step_size, video_reader.num_frames,
                     step_size):
        shape =  FindBottomMostShape(i, frame0)
        location = shape.bottom if shape else 0

        debug_log("FindFirstFingerMovement %03d: location=%d", i, location)
        if debug:
          cv2.waitKey()

        if location > initial_location + 10:
          if step_size == 1:
            return i - step_size
          else:
            return FindFirstFingerMovement(i - step_size, step_size / 10,
                                           frame0)

    def FindTouchdown(start_index, frame0):
      """Find time at which the finger stops moving, i.e. it touches down."""
      last_location = 0
      last_change_frame = start_index
      found = False

      finger_shape = None
      for i in range(start_index, video_reader.num_frames):
        # Find y-location of finger
        shape = FindBottomMostShape(i, frame0)
        location = 0
        if shape:
          location = shape.bottom

        delta = location - last_location
        debug_log("FindFingerTouchdown %03d: location=%d, delta=%d", i,
                   location, delta)
        if debug:
          cv2.waitKey()

        if delta > 1 or location == 0:
          last_location = location
          last_change_frame = i
          finger_shape = shape
        elif delta >= -1:
          if i - last_change_frame > 5:
            found = True
            break
        else:
          found = True
          break

      if not found:
        raise Exception("Cannot find minimum finger location")

      _log.info("Found finger touching at %03d", last_change_frame)
      return finger_shape, last_change_frame

    frame0 = GetAveragedNormalizedFrame(0, 5)
    first_movement_index = FindFirstFingerMovement(0, 100, frame0)
    finger_shape, touchdown_index =  FindTouchdown(first_movement_index,
                                                   frame0)
    return finger_shape, GetAveragedNormalizedFrame(touchdown_index, 5)

  @classmethod
  def CreateKeyboardPressDetector(cls, video_reader, screen_calibration,
                                  aoi_size=(50, 35), aoi_offset=(5, 5),
                                  debug=False):
    """Returns a StateChangeDetector tuned to detect keyboard state changes.

    This method will locate the touchdown of the finger and set up an area of
    interest adjacent to the finger, where the key popup will apprear.
    """
    finger_shape, reference_frame = cls._FindFingerTouchdown(video_reader,
        screen_calibration, debug=debug)
    finger_y = finger_shape.bottom + aoi_offset[1]
    finger_x = finger_shape.right + aoi_offset[0]
    (left, right) = (finger_x, finger_x + aoi_size[0])

    # Flip direction of aoi if the finger is on the right side of the screen.
    if finger_x > reference_frame.shape[1] / 2.0:
      finger_x = finger_shape.left - aoi_offset[0]
      (left, right) = (finger_x - aoi_size[0], finger_x)

    aoi = Shape.FromRectangle(reference_frame.shape,
                              top = finger_y - aoi_size[1],
                              bottom = finger_y,
                              left = left,
                              right = right)
    if debug:
      DebugView(reference=reference_frame, aoi=aoi.mask)

    return cls(aoi, reference_frame)

  def Preprocess(self, calib_frame, debugger):
    """Calculates the state change level for each frame.

    The state change level describes the deviation from the closed state.
    """
    cleaned = (self.reference_frame - calib_frame.screen_space_normalized)
    cleaned = skimage.filters.gaussian_filter(cleaned, 2.0)

    # Compensate PWM
    pwm_image = calib_frame.MeasurePWM(cleaned)
    cleaned = Filter.Truncate(np.abs(cleaned - pwm_image))

    state_change_level = np.mean(cleaned[self.area_of_interest.mask])
    _log.info("%04d: state_change_level=%.4f", calib_frame.frame_index,
                                               state_change_level)

    if debugger:
      debugger.screen_space_canvas.DrawImage(cleaned)
      debugger.screen_space_canvas.DrawMask(Canvas.BLUE,
                                            self.area_of_interest.contour)
    return state_change_level

  def GenerateEvents(self, preprocessed_data, debug=False):
    """Segments the array of state change levels into discrete state changes."""
    if debug:
      for data in preprocessed_data:
        print "%.4f" % data

    level = np.asarray(preprocessed_data, np.float)
    normalized = nputil.NormalizeStates(level)
    filtered = nputil.LowPass(normalized, 5)

    if debug:
      pyplot.figure()
      pyplot.plot(normalized)
      pyplot.plot(filtered)

    for start, end in nputil.FindStateChanges(normalized,
          self.SETTLED_THRESHOLDS, self.SETTLED_THRESHOLDS, debug=debug):
      state = (StateChangeEvent.STATE_OPEN if normalized[end] > 0.5
                                          else StateChangeEvent.STATE_CLOSED)
      if debug:
        pyplot.vlines(start, 0, 1)
        pyplot.vlines(end, 0, 1)
      yield StateChangeEvent(end, start + 1, state)

    if debug:
      pyplot.show()

    for i, data in enumerate(normalized):
      if np.isnan(data):
        continue
      yield AnalogStateEvent(i, data)

# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from safetynet import Optional
import numpy as np
import skimage.filters

from optofidelity.util import nputil
from optofidelity.videoproc import Canvas, Filter, Image, Shape

from ._calibrated_frame import CalibratedFrame
from ._detector import Detector
from .events import AnalogStateEvent, StateChangeEvent

_log = logging.getLogger(__name__)


class StateChangeDetector(Detector):
  """Detects screen switches between two different states."""

  NAME = "state_change"

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
  def _FindFingerTouchdown(cls, video_reader, screen_calibration):
    def GetFrame(frame_num):
      return CalibratedFrame(video_reader.FrameAt(frame_num), None,
                             screen_calibration, frame_num)

    def FindBottomMostShape(frame, frame0):
      """Locate the bottommost shape, which should be the robot finger."""
      cleaned = 1.0 - (frame0.screen_space_normalized -
                       frame.screen_space_normalized)
      cleaned = skimage.filters.gaussian_filter(cleaned, 2.0)
      cleaned = Filter.Truncate(cleaned)

      binary = cleaned < 0.9
      shapes = list(Shape.Shapes(binary))
      if shapes:
        return max(shapes, key=lambda s: s.bottom)
      return None

    def FindFirstFingerMovement(start_index, step_size, frame0):
      """Find first significant motion of robot finger.

      This algorithm finds the time at which the bottommost shape (the finger)
      starts moving. It works by recursively at decreasing step sizes to
      reduce the number of frames we need to process.
      """
      if step_size < 1:
        step_size = 1
      for i in range(start_index + step_size, video_reader.num_frames,
                     step_size):
        frame = GetFrame(i)
        shape =  FindBottomMostShape(frame, frame0)
        _log.debug("FindFirstFingerMovement %03d", i)
        if shape:
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

      for i in range(start_index, video_reader.num_frames):
        frame = GetFrame(i)
        shape = FindBottomMostShape(frame, frame0)
        location = 0
        if shape:
          location = shape.bottom

        delta = location - last_location
        _log.debug("FindFingerTouchdown %03d: location=%d, delta=%d", i,
                   location, delta)
        if delta > 1 or location == 0:
          last_location = location
          last_change_frame = i
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
      return last_change_frame

    frame0 = GetFrame(0)
    first_movement_index = FindFirstFingerMovement(0, 100, frame0)
    touchdown_index = FindTouchdown(first_movement_index, frame0)

    touchdown_frame = GetFrame(touchdown_index)
    finger_shape = FindBottomMostShape(touchdown_frame, frame0)
    return finger_shape, touchdown_frame

  @classmethod
  def CreateKeyboardPressDetector(cls, video_reader, screen_calibration,
                                  aoi_size=(50, 35), aoi_offset=(5, 5)):
    """Returns a StateChangeDetector tuned to detect keyboard state changes.

    This method will locate the touchdown of the finger and set up an area of
    interest adjacent to the finger, where the key popup will apprear.
    """
    finger_shape, reference_frame = cls._FindFingerTouchdown(video_reader,
                                                             screen_calibration)
    finger_y = finger_shape.bottom + aoi_offset[1]
    finger_x = finger_shape.right + aoi_offset[0]
    (left, right) = (finger_x, finger_x + aoi_size[0])

    # Flip direction of aoi if the finger is on the right side of the screen.
    if finger_x > reference_frame.screen_space_shape[1] / 2.0:
      finger_x = finger_shape.left - aoi_offset[0]
      (left, right) = (finger_x - aoi_size[0], finger_x)

    aoi = Shape.FromRectangle(reference_frame.screen_space_shape,
                              top = finger_y - aoi_size[1],
                              bottom = finger_y,
                              left = left,
                              right = right)
    return cls(aoi, reference_frame.screen_space_normalized)

  def Preprocess(self, calib_frame, debugger):
    """Calculates the state change level for each frame.

    The state change level describes the deviation from the closed state.
    """

    cleaned = (self.reference_frame - calib_frame.screen_space_normalized)
    cleaned = skimage.filters.gaussian_filter(cleaned, 2.0)
    cleaned = Filter.Truncate(cleaned)

    state_change_level = np.mean(cleaned[self.area_of_interest.mask])
    _log.info("%04d: state_change_level=%.4f", calib_frame.frame_index,
                                               state_change_level)

    if debugger:
      debugger.screen_space_canvas.DrawImage(cleaned)
      debugger.screen_space_canvas.DrawMask(Canvas.BLUE,
                                            self.area_of_interest.contour)
    return state_change_level

  def GenerateEvents(self, preprocessed_data):
    """Segments the array of state change levels into discrete state changes."""
    level = np.asarray(preprocessed_data, np.float)
    normalized = level / np.max(level)

    for start, end in nputil.FindStateChanges(normalized, settled_threshold=0.1):
      state = (StateChangeEvent.STATE_OPEN if normalized[end] > 0.5
                                          else StateChangeEvent.STATE_CLOSED)
      yield StateChangeEvent(end, start, state)

    for i, data in enumerate(normalized):
      if np.isnan(data):
        continue
      yield AnalogStateEvent(i, data)

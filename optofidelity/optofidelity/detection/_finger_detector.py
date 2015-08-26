# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

import numpy as np

from optofidelity.videoproc import Canvas, Shape

from ._detector import Detector
from .events import FingerEvent

_log = logging.getLogger(__name__)

class FingerDetector(Detector):
  """Detects Finger movement events."""

  NAME = "finger"

  FINGER_MIN_AREA = 100
  """Minimal area of the robot finger in square pixels."""

  def __init__(self):
    self._current_location = None

  def Preprocess(self, calib_frame, debugger):
    def log(msg, *params):
      _log.debug("%04d: " + msg, calib_frame.frame_index, *params)

    binary = calib_frame.screen_space_foreground

    # we are looking for a big object that touches the top of the image,
    # but not the bottom of the image.
    shapes = Shape.Shapes(binary)
    max_top = 0
    max_bottom = binary.shape[0]
    shapes = [s for s in shapes
                if (s.area > self.FINGER_MIN_AREA and
                    s.top <= max_top and s.bottom < max_bottom)]
    if shapes:
      finger_shape = max(shapes, key=lambda s: s.area)

      # the finger location is the bottom tip of the detected shape
      coords = finger_shape.coords
      bottom_row = coords[coords[:, 0] == max(coords[:, 0]), :]
      location = bottom_row[:, 1].mean()
      log("location=%.2f", location)
      if debugger:
        debugger.screen_space_canvas.DrawMask(Canvas.GREEN,
                                              finger_shape.contour)
        debugger.screen_space_canvas.DrawVLine(Canvas.GREEN, int(location))
      return location
    return None

  def GenerateEvents(self, preprocessed_data, frame_index, debugger):
    new_location = preprocessed_data

    if new_location is None or new_location == self._current_location:
      return []

    return [FingerEvent(frame_index, location=new_location)]

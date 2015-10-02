# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

import matplotlib.pyplot as pyplot
import numpy as np

from optofidelity.util import nputil
from optofidelity.videoproc import Canvas, Shape

from ._detector import Detector
from .events import FingerEvent

_log = logging.getLogger(__name__)


class FingerDetector(Detector):
  """Detects Finger movement events."""

  NAME = "finger"

  FINGER_PROFILE_HEIGHT = 30
  """Height of area on top of the screen on which to calculate the profile."""

  LOW_PASS_KERNEL_SIZE = 3
  """Kernel size of time-series low pass for smoothing finger location."""

  MIN_FINGER_WEIGHT = 0.3

  def Preprocess(self, calib_frame, debugger):
    def log(msg, *params):
      _log.debug("%04d: " + msg, calib_frame.frame_index, *params)

    # Calculate profile at top edge of the screen
    shape = Shape.FromRectangle(calib_frame.screen_space_shape,
                                bottom=self.FINGER_PROFILE_HEIGHT)
    profile = shape.CalculateProfile(calib_frame.screen_space_normalized)
    profile = 1 - calib_frame.CompensatePWMProfile(profile)

    confidence = np.max(profile)
    if confidence < 0.01:
      return 0.0, 0.0

    profile = nputil.Normalize(profile)
    profile[profile < 0.5] = 0

    # calculate weighted center location (the brighter the profile pixel is,
    # the more it counts to the center location)
    location = np.average(range(len(profile)), weights=profile)

    if debugger:
      debugger.screen_space_canvas.PlotProfile(Canvas.BLUE, profile)
      debugger.screen_space_canvas.DrawMask(Canvas.GREEN, shape.contour)
      debugger.screen_space_canvas.DrawVLine(Canvas.GREEN, int(location))

    log("location=%.2f, confidence=%.2f", location, confidence)
    return location, confidence

  def GenerateEvents(self, preprocessed_data, debug=False):
    if debug:
      print "preprocessed_data = ["
      for location, confidence in preprocessed_data:
        print "  (%.4f,%.4f)," % (location, confidence)
      print "]"

    # Return low-pass filtered finger events
    data = np.asarray(preprocessed_data, dtype=np.float)
    locations = data[:, 0]
    confidences = nputil.NormalizeStates(data[:, 1])

    smoothed = nputil.LowPass(locations, self.LOW_PASS_KERNEL_SIZE)
    for frame_index in range(len(smoothed)):
      if confidences[frame_index] > 0.5:
        yield FingerEvent(frame_index, location=locations[frame_index])

    if debug:
      pyplot.figure()
      pyplot.plot(locations)
      pyplot.plot(smoothed)
      pyplot.figure()
      pyplot.plot(locations / np.max(locations))
      pyplot.plot(confidences)
      pyplot.show()

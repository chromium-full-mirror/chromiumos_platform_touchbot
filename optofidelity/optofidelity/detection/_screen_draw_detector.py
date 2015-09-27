# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from matplotlib import pyplot
import numpy as np

from optofidelity.util import nputil

from ._detector import Detector
from .events import AnalogStateEvent, ScreenDrawEvent

_log = logging.getLogger(__name__)


class ScreenDrawDetector(Detector):
  """Detects full screen draws switching between black and white.

  The algorithm calculates the average screen color for every frame and then
  uses nputil.FindStateChanges to identify when the screen is switching between
  black and white.
  """

  NAME = "screen_draw"

  BLACK_THRESHOLD = 0.1
  """Average normalized color of the screen to identify a black screen."""

  WHITE_THRESHOLD = 0.9
  """Average normalized color of the screen to identify a white screen."""

  MAX_NOISE_LEVEL = 0.2
  """Maximum expected noise level. If the screen crosses this level then
     a draw is about to happen."""

  MAX_TRANSITION_DURATION = 20
  """Maximum duration of a screen transition. In number of frames."""

  def Preprocess(self, calib_frame, debugger):
    return np.mean(calib_frame.screen_space_normalized[:])

  def GenerateEvents(self, preprocessed_data, debug=False):
    if debug:
      for brightness in preprocessed_data:
        print "%.4f" % brightness

    # Normalize brightness
    brightness = np.asarray(preprocessed_data, dtype=np.float)
    brightness = nputil.NormalizeStates(brightness, self.MAX_NOISE_LEVEL)

    # Find state changes
    changes = nputil.FindStateChanges(brightness,
                                      dict(max_value=self.BLACK_THRESHOLD),
                                      dict(min_value=self.WHITE_THRESHOLD),
                                      crossing_threshold=self.MAX_NOISE_LEVEL,
                                      debug=debug)
    if debug:
      pyplot.figure()
      pyplot.plot(brightness, "-x")

    for start, end in changes:
      if end - start > self.MAX_TRANSITION_DURATION:
        continue

      # Determine color of the screen after the state change
      color = brightness[end]
      state = (ScreenDrawEvent.STATE_BLACK if color < 0.5
                                           else ScreenDrawEvent.STATE_WHITE)
      if debug:
        pyplot.vlines(start, 0, 1)
        pyplot.vlines(end, 0, 1)

      yield ScreenDrawEvent(end, start + 1, state)

    if debug:
      pyplot.show()

    # Yield brightness level as analog state events for display in reports.
    for i, data in enumerate(preprocessed_data):
      yield AnalogStateEvent(i, 1.0 - data)

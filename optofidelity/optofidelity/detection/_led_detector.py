# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from collections import namedtuple
import logging

import numpy as np
import numpy.linalg as linalg

from optofidelity.videoproc import Canvas, Filter, Shape

from ._detector import Detector
from .events import Event, LEDEvent

_log = logging.getLogger(__name__)

Flash = namedtuple("Flash", ("coords", "color"))

class LEDDetector(Detector):
  """Detects flashing LEDs."""

  NAME = "led"

  LED_SCREEN_MARGIN = 50
  """Margin around the screen when blacking out the screen for LED
     detection."""

  LED_MEDIAN_FILTER_STRENGTH = 5
  """Kernel size of the minimum rank order filter applied for LED detection."""

  LED_MIN_DIFF_THRESHOLD = 0.2
  """Pixels that have changed by at least this amount from the last frame are
     candidates for a blinking LED."""

  LED_MIN_AREA = 100
  """Minimum size of an LED in the min filtered and thresholded picture."""

  SCREEN_MAX_AVG_DELTA = 0.01
  """Maximum average delta of the screen before suppressing LED events."""

  DEBOUNCE_DURATION = 5
  """Number of camera frames to ignore after an LED switched."""

  LED_MIN_DISTANCE = 20
  """Distance [in px] between two flashes to be considered separate LEDs."""

  def __init__(self):
    self.recent_flash_times = []

  def Preprocess(self, calib_frame, debugger):
    def log(msg, *params):
      _log.debug("%04d: " + msg, calib_frame.frame_index, *params)

    # Create mask showing everything outside the active screen.
    if calib_frame.has_calibration:
      margin = self.LED_SCREEN_MARGIN
      screen_shape = calib_frame.camera_space_screen_shape
      bigger_shape = screen_shape.WithMargin(margin, margin)
      off_screen_mask = (~bigger_shape.mask).astype(np.double)
    else:
     off_screen_mask = np.ones(calib_frame.camera_space_shape)

    # If the screen is switching, reflections of the screen will cause parts
    # of the robot to look like a flashing LED. So We want to suppress any
    # LED events during this time.
    if calib_frame.has_calibration:
      screen_avg_delta = np.mean(np.abs(calib_frame.screen_space_delta))
      log("screen_avg_delta=%.2f", screen_avg_delta)
      if screen_avg_delta > self.SCREEN_MAX_AVG_DELTA:
        log("Suspending LED detection")
        return []

    # Look for an LED shaped large change in the masked area.
    delta = np.abs(calib_frame.camera_space_delta * off_screen_mask)
    delta = Filter.Median(delta, disk_size=self.LED_MEDIAN_FILTER_STRENGTH)
    binary = delta > self.LED_MIN_DIFF_THRESHOLD

    flashes = []
    for shape in Shape.Shapes(binary):
      draw_color = Canvas.BLUE
      if shape.area > self.LED_MIN_AREA:
        color = np.mean(calib_frame.camera_space_delta[shape.mask])
        flashes.append(Flash(shape.center, color))
        draw_color = Canvas.RED
      if debugger:
        debugger.camera_space_canvas.DrawMask(draw_color, shape.contour)

    return flashes

  def GenerateEvents(self, preprocessed_data, frame_index, debugger):
    flashes = preprocessed_data
    updated = [(flash, time) for flash, time in self.recent_flash_times
                             if time + self.DEBOUNCE_DURATION >= frame_index]
    self.recent_flash_times = updated

    def has_recently_flashed(flash):
      for recent_flash, time in self.recent_flash_times:
        distance = linalg.norm(flash.coords - recent_flash.coords)
        if distance < self.LED_MIN_DISTANCE:
          return True
      return False

    # If a flash happens a frame right after another one, assume it is part of
    # the same LED and add all flashes to the recent flash times but do not
    # generate another event.
    last_frame_flashes = [(flash, time) for flash, time in updated
                                        if frame_index - time <= 1]
    if len(last_frame_flashes):
      for flash in flashes:
        self.recent_flash_times.append((flash, frame_index - 1))
      return []

    events = []
    for flash in flashes:
      if has_recently_flashed(flash):
        continue
      self.recent_flash_times.append((flash, frame_index))

      state = Event.STATE_ON if flash.color > 0 else Event.STATE_OFF
      events.append(LEDEvent(frame_index, state=state))

    # There may be multiple flashes due to reflections, return only one event.
    if len(events) > 1:
      events = [events[0]]
    return events

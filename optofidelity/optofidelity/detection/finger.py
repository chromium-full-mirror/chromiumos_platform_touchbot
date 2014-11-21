# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import numpy as np

from optofidelity.detection.trace import Event
from optofidelity.videoproc import Filter, Shape, Canvas
from optofidelity.detection.detector import Detector


class LEDDetector(Detector):
  """Detects LED events such as led on, led off"""
  name = "led"

  led_test_area_margin = 10
  """Margin around the test area when blacking out the screen for LED
     detection."""

  led_median_filter_kernel_size = 5
  """Kernel size of the minimum rank order filter applied for LED detection."""

  led_diff_strength_treshold = 0.2
  """Pixels that have changed by at least this amount from the last frame are
     candidates for a blinking LED."""

  led_min_size = 100
  """Minimum size of an LED in the min filtered and thresholded picture."""

  led_max_eccentricity = 0.9
  """Maximum eccentricity of an LED object."""

  screen_max_avg_delta = 0.001
  """Maximum average delta of the screen before suppressing LED events."""

  debounce_duration = 5
  """Number of camera frames to ignore after an LED switched."""

  def __init__(self):
    self.led_switching = False
    self.last_flash_time = None

  def Initialize(self, video, debug):
    self.last_flash_time = np.zeros(video.frame_shape)
    return True

  def Preprocess(self, frame, debug):
    """Preprocessing step to process frame into more compact data.

    This method returns data to be passed to GenerateEvents. This method
    is stateless and can be called on any frames out of order.
    """
    # Create mask showing everything outside the active screen.
    if frame.test_area:
      margin = self.led_test_area_margin
      off_screen_mask = ~frame.test_area.shape.WithMargin(margin, margin).mask
    else:
      off_screen_mask = np.ones(frame.original.shape, dtype=np.bool)

    # If the screen is switching, reflections of the screen will cause parts
    # of the robot to look like a flashing LED. So We want to suppress any
    # LED events during this time.
    if frame.test_area:
      screen_delta = frame.test_area.shape * frame.delta
      screen_avg_delta = np.mean(np.abs(screen_delta))
      debug.Print("screen_avg_delta=%.2f", screen_avg_delta)
      if screen_avg_delta > self.screen_max_avg_delta:
        debug.Print("Suspending LED detection")
        return None

    # Mask out previous LED flashes for the duration of debounce_duration. This
    # is required as LEDs might flash multiple times if the mechanical contact
    # activating the LED is not clean.
    ignore_mask = ((frame.index - self.last_flash_time) <
                   self.debounce_duration)

    # Look for an LED shaped large change in the masked area.
    delta = np.abs(frame.delta * off_screen_mask * ~ignore_mask)
    delta = Filter.Median(delta, disk_size=self.led_median_filter_kernel_size)
    binary = delta > self.led_diff_strength_treshold

    if np.sum(binary) < self.led_min_size:
      return None

    self.last_flash_time[binary] = frame.index

    if debug:
      debug.canvas.Draw(Canvas.BLUE, binary)

    # Determine on/off state of the LED.
    led_color = np.mean(frame.delta[binary])
    return led_color

  def GenerateEvents(self, preprocessed_data, timestamp, debug):
    """Search for the current location of the finger.

    This method will return LED_ON and LED_OFF events.
    """
    led_color = preprocessed_data

    if led_color is not None:
      debug.Print("led_color=%.2f", led_color)
      # Use the led_switching flag to prevent multiple events
      if not self.led_switching:
        self.led_switching = True
        if led_color > 0:
          return [Event(timestamp, Event.LED_ON)]
        else:
          return [Event(timestamp, Event.LED_OFF)]
    else:
      self.led_switching = False
    return []


class FingerMove(Detector):
  """Detects FingerMoved events."""
  name = "finger_move"

  finger_min_area = 500
  """Minimal area of the robot finger in square pixels."""

  finger_max_eccentricity = 0.95
  """Maximal eccentricity of the robot finger. The eccentricity is close to 1
     for very elongated objects, and 0 for a square-ish object."""

  finger_max_move_speed = 10
  """Maximum movement speed of the finger in pixels per frame."""

  border_max_touching_distance = 5
  """Any object that's closer to the border than this threshold is considered
     to touch the border."""

  def __init__(self):
    self.found = False
    self.finger_shape = None
    self.location = None

  def Preprocess(self, frame, debug):
    """Preprocessing step to process frame into more compact data.

    This method returns data to be passed to GenerateEvents. This method
    is stateless and can be called on any frames out of order.
    """
    binary = frame.foreground

    # we are looking for a big object that is not very elongated
    # (i.e. not the line). It is also expected to touch the top of the image,
    # but not the bottom of the image.
    shapes = Shape.Shapes(binary)
    max_top = self.border_max_touching_distance
    max_bottom = binary.shape[0] - self.border_max_touching_distance
    shapes = [s for s in shapes
                if (s.area > self.finger_min_area and
                    s.top < max_top and s.bottom < max_bottom)]
    if shapes:
      finger_shape = max(shapes, key=lambda s: s.area)

      # the finger location is the bottom tip of the detected shape
      coords = finger_shape.coords
      bottom_row = coords[coords[:, 0] == max(coords[:, 0]), :]
      location = bottom_row[:, 1].mean()
      debug.Print("location=%.2f", location)
      if debug:
        debug.canvas.DrawContour(Canvas.GREEN, finger_shape)
        debug.canvas.DrawHLine(Canvas.GREEN, location, finger_shape.bottom)
      return location
    return None

  def GenerateEvents(self, preprocessed_data, timestamp, debug):
    """Search for the current location of the finger.

    This method will return a list of FINGER_MOVED events when the finger
    is moving.
    """
    new_location = preprocessed_data
    self.found = new_location is not None

    # Report new location if location has changed but not changed too much.
    if (new_location is not None and self.location != new_location and
        (self.location is None or
         np.abs(self.location - new_location) < self.finger_max_move_speed)):
      self.location = new_location
      return [Event(timestamp, Event.FINGER_MOVED, location=new_location)]
    return []

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import numpy as np

from optofidelity.detection.trace import Event
from optofidelity.videoproc import Filter, Shape, Canvas
from optofidelity.detection.detector import Detector

class Finger(Detector):
  """Represents the OptoFidelity robot finger.

  Finger.found: Is True when the finger has been detected
  Finger.finger_shape: Is the segmented shape of the finger
  Finger.debug_canvas: If Update is called with debug=True, this will
                       contain a canvas object showing debug info.
  """
  name = "finger"

  finger_min_area = 1000
  """Minimal area of the robot finger in square pixels."""

  finger_max_eccentricity = 0.95
  """Maximal eccentricity of the robot finger. The eccentricity is close to 1
     for very elongated objects, and 0 for a square-ish object."""

  finger_max_move_speed = 5
  """Maximum movement speed of the finger in pixels per frame."""

  border_max_touching_distance = 5
  """Any object that's closer to the border than this threshold is considered
     to touch the border."""

  led_test_area_margin = 10
  """Margin around the test area when blacking out the screen for LED
     detection."""

  led_min_filter_kernel_size = 5
  """Kernel size of the minimum rank order filter applied for LED detection."""

  led_diff_strength_treshold = 0.2
  """Pixels that have changed by at least this amount from the last frame are
     candidates for a blinking LED."""

  led_min_size = 50
  """Minimum size of an LED in the min filtered and thresholded picture."""

  led_max_eccentricity = 0.9
  """Maximum eccentricity of an LED object."""

  def __init__(self):
    self.found = False
    self.finger_shape = None
    self.debug_canvas = None
    self.location = None
    self.led_switching = False

  def Preprocess(self, frame, debug=False):
    """Preprocessing step to process frame into more compact data.

    This method returns data to be passed to GenerateEvents. This method
    is stateless and can be called on any frames out of order.
    """
    binary = frame.foreground

    # we are looking for a big object that is not very elongated
    # (i.e. not the line). It is also expected to touch the top of the image,
    # but not the bottom of the image.
    def is_finger(region, labels, debug=False):
      if debug:
        print (region.label, region.area, region.eccentricity, region.bbox[0],
               region.bbox[2])

      top = region.bbox[0]
      bottom = region.bbox[2]
      image_bottom = labels.shape[0]
      return (region.area > self.finger_min_area and
              region.eccentricity < self.finger_max_eccentricity and
              top < self.border_max_touching_distance and
              bottom < image_bottom - self.border_max_touching_distance)
    finger_shape = Shape.Find(binary, is_finger, debug=debug)
    location = None

    # the finger location is the bottom tip of the detected shape
    if finger_shape:
      coords = finger_shape.coords
      bottom_row = coords[coords[:, 0] == max(coords[:, 0]), :]
      location = bottom_row[:, 1].mean()

    # Look for a large amount of change outside of the test area, i.e. a
    # flashing LED:
    margin = self.led_test_area_margin
    mask = ~frame.test_area.shape.WithMargin(margin, margin).mask
    delta = np.abs(frame.delta) * mask
    delta = Filter.Min(delta, disk_size=self.led_min_filter_kernel_size)
    binary = delta > self.led_diff_strength_treshold

    def is_led(region, labels, debug=False):
      if debug:
        print (region.label, region.area, region.eccentricity)
      return (region.area > self.led_min_size and
              region.eccentricity < self.led_max_eccentricity)
    led_shape = Shape.Find(binary, is_led, debug=debug)

    # Determine on/off state of the LED.
    led_color = 0
    if led_shape:
      led_color = np.mean(frame.original[led_shape.mask])
    return (location, finger_shape, led_color, led_shape)

  def GenerateEvents(self, preprocessed_data, timestamp, debug_canvas=None):
    """Search for the current location of the finger.

    This method will return a list of FINGER_MOVED events when the finger
    is moving.
    """
    events = []

    (new_location, self.finger_shape, led_color, led_shape) = preprocessed_data
    self.found = new_location is not None

    # Report new location if location has changed but not changed too much.
    if (new_location is not None and self.location != new_location and
        (self.location is None or
         np.abs(self.location - new_location) < self.finger_max_move_speed)):
      self.location = new_location
      events.append(Event(timestamp, Event.FINGER_MOVED,
                          location=new_location))

    # If there is a strong change we expect it to be the flashing LED
    if led_shape:
      # Use the led_switching flag to prevent multiple events
      if not self.led_switching:
        self.led_switching = True
        if led_color > 0.5:
          events.append(Event(timestamp, Event.FINGER_DOWN))
        else:
          events.append(Event(timestamp, Event.FINGER_UP))
    else:
      self.led_switching = False

    if debug_canvas:
      if self.finger_shape:
        debug_canvas.DrawContour([0, 1, 0], self.finger_shape)
        debug_canvas.DrawContour([1, 0, 0], led_shape)
        debug_canvas.DrawHLine([0, 1, 0], self.location,
                               self.finger_shape.bottom)

    return events

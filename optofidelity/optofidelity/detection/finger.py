# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import numpy as np

from optofidelity.trace import Event
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

  def __init__(self):
    self.found = False
    self.finger_shape = None
    self.debug_canvas = None
    self.location = None
    self.led_switching = False

  def Preprocess(self, frame, debug=False):
    """Preprocessing step to process frame into more compact data.

    This method returns data to be passed to GenerateEvents. This method
    is stateless and can be called on any frames out of order."""
    # extend the target area to view the full finger tip
    binary = (frame.reflectance < 0.95)

    # we are looking for a big object that is not very elongated
    # (i.e. not the line)
    def is_finger(region, labels, debug=False):
      if debug:
        print (region.label, region.area, region.eccentricity, region.bbox[0],
              region.bbox[2])
      return (region.area > 1000 and region.eccentricity < 0.95 and
              region.bbox[0] < 5 and region.bbox[2] < labels.shape[0] - 5)
    finger_shape = Shape.Find(binary, is_finger, debug=debug)
    location = None

    # the finger location is the bottom tip of the detected shape
    if finger_shape:
      coords = finger_shape.coords
      bottom_row = coords[coords[:, 0] == max(coords[:, 0]), :]
      location = bottom_row[:, 1].mean()

    # Look for a large amount of change outside of the test area, i.e. a
    # flashing LED:
    mask = ~frame.test_area.shape.WithMargin(10, 10).mask
    delta = np.abs(frame.delta) * mask
    # Filter out Noise, the flash should be at least 5 pixels big.
    delta = Filter.Min(delta, disk_size=5)
    # Determine on/off state of the LED.
    led_color = np.mean(frame.original[delta > 0.2])
    return (location, finger_shape, np.max(delta), led_color)

  def GenerateEvents(self, preprocessed_data, timestamp, debug_canvas=None):
    """Search for the current location of the finger.

    This method will return a list of FINGER_MOVED events when the finger
    is moving.
    """
    events = []

    (new_location, self.finger_shape, max_delta, led_color) = preprocessed_data
    self.found = new_location is not None

    # Report new location if location has changed but not changed too much.
    if (new_location is not None and self.location != new_location and
        (self.location is None or np.abs(self.location - new_location) < 5)):
      self.location = new_location
      events.append(Event(timestamp, Event.FINGER_MOVED,
                          location=new_location))

    # If there is a strong change we expect it to be the flashing LED
    if max_delta > 0.2:
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
        debug_canvas.DrawHLine([0, 1, 0], self.location,
                               self.finger_shape.bottom)

    return events

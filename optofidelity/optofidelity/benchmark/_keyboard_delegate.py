# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of TapDelegate."""

import numpy as np

from optofidelity.detection import (LEDDetector, LEDEvent, StateChangeDetector,
                                    StateChangeEvent)

from ._delegate import BenchmarkDelegate


class KeyboardDelegate(BenchmarkDelegate):
  """Contains logic to perform tap latency benchmarks."""

  BASE_DURATION = 1000
  """Duration at beginning of each recording (in ms)."""

  PER_TAP_DURATION = 500
  """Duration of each tap in recording (in number of frames)."""

  NUM_MEASUREMENTS = 10
  """Number of tap latency measurements (i.e. number of taps)."""

  CAMERA_FRAMERATE = 300
  """Framerate at which to record, in frames per second."""

  def __init__(self, activity, parameters):
    super(KeyboardDelegate, self).__init__(activity, parameters)
    self._key_location = float(parameters["key-location"])

  def InitializeProcessor(self, processor, video_reader, screen_calibration):
    keyboard_detector = StateChangeDetector.CreateKeyboardPressDetector(
        video_reader, screen_calibration)
    processor.InitializeDetectors(keyboard_detector, LEDDetector())

  def ExecuteOnSubject(self, subject):
    duration = (self.BASE_DURATION +
                self.PER_TAP_DURATION * self.NUM_MEASUREMENTS)
    subject.camera.Prepare(duration, self.CAMERA_FRAMERATE, subject.exposure)

    key_location = subject.height - self._key_location
    subject.MoveOnTestPlane(key_location, 10.0, blocking=True)

    subject.TapOnTestPlane(key_location)
    subject.camera.Trigger()
    subject.StartCollection(duration)
    subject.TapOnTestPlane(key_location, count=self.NUM_MEASUREMENTS)
    subject.StopCollection()
    return subject.camera.ReceiveVideo()

  def ProcessTrace(self, trace, measurements):
    if np.min(trace.led) < 0.0 or np.max(trace.led) > 1.0:
      # An LED turning on will increase trace.led by one and an LED turning off
      # will decrease it by one. If we ever go below zero or above 1 this means
      # that the LED detection either missed an LED or it detected a spurious
      # one.
      raise Exception("LED detection was inconsistent.")
    trace.RequireEventTypes(LEDEvent, StateChangeEvent)

    for segmented_trace in trace.SegmentedByLED():
      segmented_trace.RequireEventTypes(LEDEvent, StateChangeEvent)

      finger_down = segmented_trace.FindStateSwitch(LEDEvent, LEDEvent.STATE_ON)
      finger_up = segmented_trace.FindStateSwitch(LEDEvent, LEDEvent.STATE_OFF)

      screen_black = segmented_trace.FindStateSwitch(StateChangeEvent,
          StateChangeEvent.STATE_BLACK)
      screen_white = segmented_trace.FindStateSwitch(StateChangeEvent,
          StateChangeEvent.STATE_WHITE)

      if finger_down and screen_black:
        measurements.AddDrawEventMeasurement("KeyboardDown", finger_down,
                                             screen_black)
      if finger_up and screen_white:
        measurements.AddDrawEventMeasurement("KeyboardUp", finger_up,
                                             screen_white)

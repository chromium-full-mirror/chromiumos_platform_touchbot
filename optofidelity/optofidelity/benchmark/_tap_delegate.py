# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of TapDelegate."""

import numpy as np

from optofidelity.detection import (LEDDetector, LEDEvent, ScreenDrawDetector,
                                    ScreenDrawEvent)

from ._delegate import BenchmarkDelegate


class TapDelegate(BenchmarkDelegate):
  """Contains logic to perform tap latency benchmarks."""

  BASE_DURATION = 1000
  """Duration at beginning of each recording (in ms)."""

  PER_TAP_DURATION = 500
  """Duration of each tap in recording (in number of frames)."""

  NUM_MEASUREMENTS = 12
  """Number of tap latency measurements (i.e. number of taps)."""

  CAMERA_FRAMERATE = 300
  """Framerate at which to record, in frames per second."""

  def InitializeProcessor(self, processor, video_reader, screen_calibration):
    processor.InitializeDetectors(ScreenDrawDetector(), LEDDetector())

  def ExecuteOnSubject(self, subject):
    duration = (self.BASE_DURATION +
                self.PER_TAP_DURATION * self.NUM_MEASUREMENTS)
    subject.camera.Prepare(duration, self.CAMERA_FRAMERATE, subject.exposure)
    center = subject.height / 2.0

    subject.MoveOnTestPlane(center, 10.0, blocking=True)
    subject.TapOnTestPlane(center)
    subject.StartCollection(duration)
    subject.camera.Trigger()
    subject.TapOnTestPlane(center, count=self.NUM_MEASUREMENTS)

    subject.StopCollection()
    video_reader = subject.camera.ReceiveVideo()
    return video_reader

  def ProcessTrace(self, trace, measurements):
    if np.min(trace.led) < 0.0 or np.max(trace.led) > 1.0:
      # An LED turning on will increase trace.led by one and an LED turning off
      # will decrease it by one. If we ever go below zero or above 1 this means
      # that the LED detection either missed an LED or it detected a spurious
      # one.
      raise Exception("LED detection was inconsistent.")
    trace.RequireEventTypes(LEDEvent, ScreenDrawEvent)

    for segmented_trace in trace.SegmentedByLED():
      segmented_trace.RequireEventTypes(LEDEvent)
      if not segmented_trace.HasEventTypes(ScreenDrawEvent):
        continue

      finger_down = segmented_trace.FindStateSwitch(LEDEvent, LEDEvent.STATE_ON)
      finger_up = segmented_trace.FindStateSwitch(LEDEvent, LEDEvent.STATE_OFF)

      screen_black = segmented_trace.FindStateSwitch(ScreenDrawEvent,
          ScreenDrawEvent.STATE_BLACK)
      screen_white = segmented_trace.FindStateSwitch(ScreenDrawEvent,
          ScreenDrawEvent.STATE_WHITE)

      if finger_down and screen_black:
        measurements.AddDrawEventMeasurement("DownLatency", finger_down,
                                             screen_black)
      if finger_up and screen_white:
        measurements.AddDrawEventMeasurement("UpLatency", finger_up,
                                             screen_white)

# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of TapDelegate."""

from optofidelity.detection import LEDEvent, ScreenDrawEvent

from ._delegate import BenchmarkDelegate


class TapDelegate(BenchmarkDelegate):
  """Contains logic to perform tap latency benchmarks."""

  BASE_DURATION = 200
  """Duration at beginning of each recording (in number of frames)."""

  PER_TAP_DURATION = 160
  """Duration of each tap in recording (in number of frames)."""

  NUM_MEASUREMENTS = 10
  """Number of tap latency measurements (i.e. number of taps)."""

  CAMERA_FRAMERATE = 300
  """Framerate at which to record, in frames per second."""

  def InitializeProcessor(self, processor):
    processor.EnableDetectors(screen_draw=True, led=True)

  def ExecuteOnSubject(self, subject):
    duration = (self.BASE_DURATION +
                self.PER_TAP_DURATION * self.NUM_MEASUREMENTS)
    subject.camera.Prepare(duration, self.CAMERA_FRAMERATE)
    center = subject.height / 2.0

    subject.OpenPage("Tap")
    subject.MoveOnTestPlane(center, 10.0, blocking=True)

    subject.camera.Trigger()
    for i in range(self.NUM_MEASUREMENTS):
      subject.TapOnTestPlane(center)

    video_reader = subject.camera.ReceiveVideo()
    subject.ClosePage()
    return video_reader

  def ProcessTrace(self, trace, results):
    for segmented_trace in trace.SegmentedByLED():
      segmented_trace.RequireEventTypes(LEDEvent, ScreenDrawEvent)

      finger_down = segmented_trace.FindStateSwitch(LEDEvent, LEDEvent.STATE_ON)
      finger_up = segmented_trace.FindStateSwitch(LEDEvent, LEDEvent.STATE_OFF)

      screen_black = segmented_trace.FindStateSwitch(ScreenDrawEvent,
          ScreenDrawEvent.STATE_BLACK)
      screen_white = segmented_trace.FindStateSwitch(ScreenDrawEvent,
          ScreenDrawEvent.STATE_WHITE)

      if finger_down and screen_black:
        results.AddMeasurement("DownLatency", finger_down, screen_black)
      if finger_up and screen_white:
        results.AddMeasurement("UpLatency", finger_up, screen_white)

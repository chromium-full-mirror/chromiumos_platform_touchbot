# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module implements test cases to measure touch latency."""
import time

from optofidelity.test_runner import TestClass
from optofidelity.detection import (Event, FingerLED, FingerMove, Line,
                                    ScreenFlash)


class TouchMoveLatencyTest(TestClass):
  """Calculates latency from a line draw video."""
  name = "TouchMoveLatency"
  required_events = []

  def InitializeProcessor(self, processor):
    processor.AddDetector(Line())
    processor.AddDetector(FingerMove())

  def ExecuteTest(self, app, dut, camera):
    app.EnterPage("Move")
    dut.Move(dut.test_plane, 10, 10)
    camera.Record(300)
    dut.Swipe(dut.test_plane, 30, dut.test_plane, 90)
    camera.WaitUntilReady()
    app.ExitPage()
    return camera.GetVideoReader()

  def ProcessTrace(self, trace):
    # find linear motion range and trim draw events to this range.
    start_event, end_event = trace.FindLinearMotionRange(Event.FINGER_MOVED)

    trace = trace.TrimByLocation(start_event.location, end_event.location)

    # for each draw event, calculate difference to time when the finger
    # moved through the line location.
    finger_loc_time = trace.LocationTimeMap(Event.FINGER_MOVED)
    start_lat = [e.time - finger_loc_time(e.location)
                 for e in trace.Events(Event.LINE_DRAW_START)]
    end_lat = [e.time - finger_loc_time(e.location)
               for e in trace.Events(Event.LINE_DRAW_END)]
    return {
        "StartLatency": start_lat,
        "EndLatency": end_lat
    }


class TapLatencyTest(TestClass):
  """Calculates latency from a line draw video."""
  name = "TapLatency"

  base_record_duration = 300
  """Duration at beginning of each recording (in number of frames)."""

  per_tap_record_duration = 200
  """Duration of each tap in recording (in number of frames)."""

  num_measurements = 6
  """Number of tap latency measurements (i.e. number of taps)."""

  def InitializeProcessor(self, processor):
    processor.AddDetector(ScreenFlash())
    processor.AddDetector(FingerLED())

  def ExecuteTest(self, app, dut, camera):
    duration = (self.base_record_duration +
                self.per_tap_record_duration * self.num_measurements)
    camera.PrepareRecording(duration)
    app.EnterPage("Tap")
    dut.Move(dut.test_plane, dut.height/2, 10)
    camera.Trigger()
    dut.Tap(dut.test_plane, dut.height/2, count=self.num_measurements)
    camera.WaitUntilReady()
    app.ExitPage()
    return camera.GetVideoReader()

  def ProcessTrace(self, trace):
    traces = trace.Split(Event.FINGER_DOWN)

    down_start = []
    down_end = []
    up_start = []
    up_end = []
    for trace in traces:
      finger_down = trace.Time(Event.FINGER_DOWN)
      finger_up = trace.Time(Event.FINGER_UP)

      screen_off_start = trace.Time(Event.SCREEN_DRAW_START, color="Black")
      screen_off_end = trace.Time(Event.SCREEN_DRAW_END, color="Black")

      screen_on_start = trace.Time(Event.SCREEN_DRAW_START, color="White")
      screen_on_end = trace.Time(Event.SCREEN_DRAW_END, color="White")

      down_start.append(screen_off_start - finger_down)
      down_end.append(screen_off_end - finger_down)
      up_start.append(screen_on_start - finger_up)
      up_end.append(screen_on_end - finger_up)

    return {
        "DownStartLatency": down_start,
        "DownEndLatency": down_end,
        "UpStartLatency": up_start,
        "UpEndLatency": up_end,
    }

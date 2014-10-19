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
  required_events = []

  def InitializeProcessor(self, processor):
    processor.AddDetector(ScreenFlash())
    processor.AddDetector(FingerLED())

  def ExecuteTest(self, app, dut, camera):
    app.EnterPage("Tap")
    dut.Move(dut.test_plane, dut.height/2, 10)
    camera.Record(300)
    time.sleep(0.8)
    dut.Tap(dut.test_plane, dut.height/2)
    camera.WaitUntilReady()
    app.ExitPage()
    return camera.GetVideoReader()

  def ProcessTrace(self, trace):
    # find linear motion range and trim draw events to this range.
    finger_down = trace.Time(Event.FINGER_DOWN)
    finger_up = trace.Time(Event.FINGER_UP)

    screen_off_start = trace.Time(Event.SCREEN_DRAW_START, color="Black")
    screen_off_end = trace.Time(Event.SCREEN_DRAW_END, color="Black")

    screen_on_start = trace.Time(Event.SCREEN_DRAW_START, color="White")
    screen_on_end = trace.Time(Event.SCREEN_DRAW_END, color="White")

    return {
        "DownStartLatency": screen_off_start - finger_down,
        "DownEndLatency": screen_off_end - finger_down,
        "UpStartLatency": screen_on_start - finger_up,
        "UpEndLatency": screen_on_end - finger_up,
    }

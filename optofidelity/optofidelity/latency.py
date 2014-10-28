# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module implements test cases to measure touch latency."""
import matplotlib.pyplot as plt
import time

from optofidelity.test_runner import TestClass
from optofidelity.detection import (Event, FingerLED, FingerMove, Line,
                                    ScreenFlash)


class TouchMoveLatencyTest(TestClass):
  """Calculates latency from a line draw video."""
  name = "TouchMoveLatency"

  page = "Move"
  """Name of the page to run this test on."""

  calib_move_distance = 10
  """Distance to move for the calibration movement (in mm)."""

  commands_duration = 2000
  """Duration of the full set of robot commands (in # of camera frames)."""

  repetitions = 1
  """How often to repeat the test."""

  def InitializeProcessor(self, processor):
    processor.AddDetector(Line())
    processor.AddDetector(FingerMove())

  def ExecuteTest(self, app, dut, camera):
    camera.PrepareRecording(self.commands_duration * self.repetitions)
    app.EnterPage(self.page)

    # The robot will draw a line between the 'left' and 'right' location and
    # back. It will pause after the first bit of the line so the video
    # processing can calculate the offset between finger and line location.
    left = 0
    right = app.height
    left_calib_stop = left + self.calib_move_distance
    right_calib_stop = right - self.calib_move_distance

    # Height of finger down and up state in cm
    down = -1
    up = 10

    for i in range(self.repetitions):
      # Tap to reset the screen, then draw from left to right.
      app.Tap(left)
      if i == 0:
        camera.Trigger()
      app.Move(left, down)
      app.Move(left_calib_stop, down)
      app.Move(right, down)
      app.Move(right, up)

      # Tap to reset the screen, then draw from right to left.
      app.Tap(right)
      app.Move(right, down)
      app.Move(right_calib_stop, down)
      app.Move(left, down)
      app.Move(left, up)

    camera.WaitUntilReady()
    app.ExitPage()
    return camera.GetVideoReader()

  def ProcessTrace(self, traces, debug):
    start_lat = []
    end_lat = []

    def PlotEvent(trace, event_type):
      plt.plot(trace.Times(event_type), trace.Locations(event_type))

    if debug:
      plt.figure()
      PlotEvent(traces, Event.FINGER_MOVED)
      plt.title("Finger/Line draw locations")

    for trace in traces.Split(Event.LINE_RESET):
      trace.RequireEvents(Event.FINGER_MOVED,
                          Event.LINE_DRAW_END,
                          Event.LINE_DRAW_END)

      # Find pause after first movement to calibrate the offset between
      # finger and line location.
      calib_start, calib_end = trace.FindStaticMotionRange(Event.FINGER_MOVED)
      finger_at_calib = calib_end.location
      line_at_calib = trace.LocationAt(Event.LINE_DRAW_END, calib_end.time)
      calib_offset = finger_at_calib - line_at_calib

      if debug:
        print "Calibration Offset:", calib_offset

      # Find linear motion range and trim draw events to this range.
      start_event, end_event = trace.FindLinearMotionRange(Event.FINGER_MOVED)
      start_location = start_event.location - calib_offset
      end_location = end_event.location - calib_offset
      trace = trace.TrimByLocation(start_location, end_location,
                                   Event.LINE_DRAW_START)
      trace = trace.TrimByLocation(start_location, end_location,
                                   Event.LINE_DRAW_END)

      # Add trimmed line draw events to plot
      if debug:
        PlotEvent(trace, Event.LINE_DRAW_START)
        PlotEvent(trace, Event.LINE_DRAW_END)

      # For each draw event, calculate difference to time when the finger
      # moved through the line location.
      finger_loc_time = trace.LocationTimeMap(Event.FINGER_MOVED)
      start_lat.extend([e.time - finger_loc_time(e.location + calib_offset)
                        for e in trace.Events(Event.LINE_DRAW_START)])
      end_lat.extend([e.time - finger_loc_time(e.location + calib_offset)
                      for e in trace.Events(Event.LINE_DRAW_END)])

    if debug:
      plt.figure()
      plt.plot(start_lat)
      plt.plot(end_lat)
      plt.title("Start/End Latencies")
      plt.show()

    return {
        "DrawStartLatency": start_lat,
        "DrawEndLatency": end_lat
    }


class ScrollLatencyTest(TouchMoveLatencyTest):
  """Measures scroll latency.

  This latency measurement logic is identical to TouchMoveLatencyTest, but
  is executed on the Scroll page.
  """
  name = "ScrollLatency"
  page = "Scroll"


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
    dut.Move(dut.test_plane, app.height/2, 10)
    camera.Trigger()
    dut.Tap(dut.test_plane, app.height/2, count=self.num_measurements)
    camera.WaitUntilReady()
    app.ExitPage()
    return camera.GetVideoReader()

  def ProcessTrace(self, trace, debug):
    down_start = []
    down_end = []
    up_start = []
    up_end = []

    for trace in trace.Split(Event.FINGER_DOWN):
      if not trace.Events(Event.FINGER_DOWN):
        continue

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

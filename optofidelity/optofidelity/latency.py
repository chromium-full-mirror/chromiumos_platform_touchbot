# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module implements test cases to measure touch latency."""
import matplotlib.pyplot as plt
import time

from optofidelity.test_runner import TestClass
from optofidelity.detection import (Event, LEDDetector, FingerMove, Line,
                                    ScreenFlash)


def PlotEvent(trace, event_type):
  plt.plot(trace.Times(event_type), trace.Locations(event_type))


class TouchMoveLatencyTest(TestClass):
  """Calculates latency from a line draw video."""
  name = "TouchMoveLatency"

  page = "Move"
  """Name of the page to run this test on."""

  calib_move_distance = 10
  """Distance to move for the calibration movement (in mm)."""

  commands_duration = 2000
  """Duration of the full set of robot commands (in # of camera frames)."""

  repetitions = 2
  """How often to repeat the test."""

  def InitializeProcessor(self, processor):
    processor.AddDetector(Line())
    processor.AddDetector(FingerMove())

  def ExecuteTest(self, app, dut, camera):
    camera.PrepareRecording(self.commands_duration)
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


class ScrollStartLatencyTest(TestClass):
  """Calculates latency from a line draw video."""
  name = "ScrollStartLatency"

  page = "Scroll"
  """Name of the page to run this test on."""

  scroll_distance = 10
  """Distance to move for each scroll (in mm)."""

  commands_duration = 2000
  """Duration of the full set of robot commands (in # of camera frames)."""

  finger_min_speed = 0.2
  """Minimum speed for the robot finger to be considered moving."""

  repetitions = 3

  def InitializeProcessor(self, processor):
    processor.AddDetector(Line())
    processor.AddDetector(FingerMove())
    processor.AddDetector(LEDDetector())

  def ExecuteTest(self, app, dut, camera):
    camera.PrepareRecording(self.commands_duration)
    app.EnterPage(self.page)

    # Height of finger down and up state in cm
    down = -1
    up = 10

    # Scroll by scroll_distance, lift finger, then scroll again until
    # the end of the page is reached.
    app.Tap(0)
    camera.Trigger()
    for i in range(self.scroll_distance, int(app.height), self.scroll_distance):
      app.Move(i - self.scroll_distance, down)
      app.Move(i, down)
      app.Move(i, up)

    camera.WaitUntilReady()
    app.ExitPage()
    return camera.GetVideoReader()

  def ProcessTrace(self, trace, debug):
    start_lat = []
    end_lat = []

    finger_moved_events = trace.Events(Event.FINGER_MOVED)
    finger_speed = trace.Speed(Event.FINGER_MOVED)
    current_time = 0

    if debug:
      plt.figure()
      PlotEvent(trace, Event.FINGER_MOVED)
      PlotEvent(trace, Event.LINE_DRAW_START)
      PlotEvent(trace, Event.LINE_DRAW_END)
      plt.title("Finger/Line draw locations")

    while True:
      if debug:
        print "-" * 80

      # Search for finger down event
      (_, finger_down) = trace.Find(Event.LED_ON, current_time)
      if not finger_down:
        break
      if debug:
        print finger_down

      # Find first line draw start after finger_down
      (_, line_draw_start) = trace.Find(Event.LINE_DRAW_START, finger_down.time)
      if not line_draw_start:
        break
      if debug:
        print line_draw_start

      # Find first line draw end after finger_down
      (_, line_draw_end) = trace.Find(Event.LINE_DRAW_END, finger_down.time)
      if not line_draw_end:
        break
      if debug:
        print line_draw_end

      # Search for first significant finger movement after finger down
      (finger_down_idx, _) = trace.Find(Event.FINGER_MOVED, finger_down.time)
      finger_moved = None
      for i in range(finger_down_idx, len(finger_speed)):
        if finger_speed[i] > self.finger_min_speed:
          finger_moved = finger_moved_events[i]
          break
      if not finger_moved:
        break
      if debug:
        print finger_moved

      # Calculate latency
      start_lat.append(line_draw_start.time - finger_moved.time)
      end_lat.append(line_draw_end.time - finger_moved.time)

      # Progress time and repeat until one of the events cannot be found.
      current_time = line_draw_end.time

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


class TapLatencyTest(TestClass):
  """Calculates latency from a line draw video."""
  name = "TapLatency"

  base_record_duration = 300
  """Duration at beginning of each recording (in number of frames)."""

  per_tap_record_duration = 300
  """Duration of each tap in recording (in number of frames)."""

  num_measurements = 6
  """Number of tap latency measurements (i.e. number of taps)."""

  repetitions = 4

  def InitializeProcessor(self, processor):
    processor.AddDetector(ScreenFlash())
    processor.AddDetector(LEDDetector())

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

    for trace in trace.Split(Event.LED_ON):
      if not trace.Events(Event.LED_ON):
        continue

      finger_down = trace.Time(Event.LED_ON)
      finger_up = trace.Time(Event.LED_OFF)

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

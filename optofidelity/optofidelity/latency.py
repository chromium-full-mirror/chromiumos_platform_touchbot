# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module implements test cases to measure touch latency."""
from optofidelity.test_runner import TestClass
from optofidelity.detection import (Event, LEDDetector, FingerMove, Line,
                                    ScreenFlash, FingerEvent, LineDrawEvent,
                                    ScreenDrawEvent, LEDEvent)
from optofidelity.videoproc import MockVideoReader

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
    app.Tap(left, blocking=True)
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

  def ProcessTrace(self, traces, results, debug):
    for pass_num, trace in enumerate(traces.SegmentedByLineReset()):
      trace.RequireEventTypes(FingerEvent, LineDrawEvent)

      # Find pause after first movement to calibrate the offset between
      # finger and line location.
      calib_start, calib_end = trace.FindStationaryFinger()
      line_at_calib = trace.Find(LineDrawEvent, calib_end.time, "before")
      results.AddCalibration(calib_end, line_at_calib, pass_num)
      calib_offset = calib_end.location - line_at_calib.location

      # Find linear motion range and trim draw events to this range.
      start_event, end_event = trace.FindLinearFingerMotion()
      start_location = start_event.location - calib_offset
      end_location = end_event.location - calib_offset
      if start_location > end_location:
        (start_location, end_location) = (end_location, start_location)

      # Filter draw events to only use locations during which the finger was
      # moving linearly.
      draw_events = trace.Events(LineDrawEvent)
      draw_events = [e for e in draw_events if e.location >= start_location and
                                               e.location < end_location]
      for draw_event in draw_events:
        finger_event = trace.FindFingerCrossing(draw_event, offset=calib_offset)
        results.Add("Line Draw Latency", finger_event, draw_event, pass_num)


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

  repetitions = 2

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
    app.Tap(0, blocking=True)
    camera.Trigger()
    for i in range(self.scroll_distance, int(app.height), self.scroll_distance):
      app.Move(i - self.scroll_distance, down)
      app.Move(i, down)
      app.Move(i, up)

    camera.WaitUntilReady()
    app.ExitPage()
    return camera.GetVideoReader()

  def ProcessTrace(self, traces, results, debug):
    for trace in traces.SegmentedByLED():
      debug.Print("-" * 80)

      # Find first line draw start in this segment
      line_draw = trace.Find(LineDrawEvent, 0, "after")
      if not line_draw:
        break
      debug.Print(line_draw)

      # Search for first significant finger movement in this segment
      finger_moved_time = None
      for i, speed in enumerate(trace.finger_speed):
        if speed > self.finger_min_speed:
          finger_moved_time = i
          break
      if finger_moved_time is None:
        break
      debug.Print("finger_moved_time=%d", finger_moved_time)

      finger_moved_event = trace.Find(FingerEvent, finger_moved_time)
      results.Add("ScrollStartLatency", finger_moved_event, line_draw)


class TapLatencyTest(TestClass):
  """Calculates latency from a line draw video."""
  name = "TapLatency"

  base_record_duration = 200
  """Duration at beginning of each recording (in number of frames)."""

  per_tap_record_duration = 160
  """Duration of each tap in recording (in number of frames)."""

  num_measurements = 10
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
    app.Move(app.height / 2, 10, blocking=True)

    camera.Trigger()
    app.Tap(app.height / 2, count=self.num_measurements)
    camera.WaitUntilReady()

    app.ExitPage()
    return camera.GetVideoReader()

  def ProcessTrace(self, traces, results, debug):
    for trace in traces.SegmentedByLED():
      trace.RequireEventTypes(LEDEvent, ScreenDrawEvent)

      finger_down = trace.FindStateSwitch(LEDEvent, Event.STATE_ON)
      finger_up = trace.FindStateSwitch(LEDEvent, Event.STATE_OFF)

      screen_black = trace.FindStateSwitch(ScreenDrawEvent, Event.STATE_BLACK)
      screen_white = trace.FindStateSwitch(ScreenDrawEvent, Event.STATE_WHITE)

      results.Add("DownLatency", finger_down, screen_black)
      results.Add("UpLatency", finger_up, screen_white)


class MockLatencyTest(TestClass):
  """Calculates latency from a line draw video."""
  name = "MockLatency"
  repetitions = 1

  def InitializeProcessor(self, processor):
    pass

  def ExecuteTest(self, app, dut, camera):
    return MockVideoReader(3000, (720, 1280))

  def ProcessTrace(self, traces, results, debug):
    for i in range(20):
      time = i * 100
      results.Add("TapMockLatency", LEDEvent(time, state=Event.STATE_ON),
                  ScreenDrawEvent(time + 20, state=Event.STATE_WHITE,
                                  start_time=time + 10))
      results.Add("LineMockLatency", FingerEvent(time, location=i * 10),
                  LineDrawEvent(time + 20, location=i * 10,
                                start_time=time + 10))

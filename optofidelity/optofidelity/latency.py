# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module implements test cases to measure touch latency."""
from test_runner import TestCase
from detection import Event


class TouchMoveLatencyTest(TestCase):
  """Calculates latency from a line draw video."""
  def __init__(self, app):
    TestCase.__init__(self, app)
    self.name = "TouchMoveLatency"
    self.required_events = [Event.FINGER_MOVED,
                            Event.LINE_DRAW_START,
                            Event.LINE_DRAW_END]

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

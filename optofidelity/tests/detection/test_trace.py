# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import numpy as np
import os
import unittest
from optofidelity.detection.trace import (Trace, Event, FingerEvent,
                                          LineDrawEvent, LEDEvent,
                                          ScreenDrawEvent)

script_dir = os.path.dirname(os.path.realpath(__file__))

class TraceBuilder(object):
  """Helper class to build fake traces.

  Every Add* method will add events at a fixed report rate (1 event every 10
  time units.
  """

  report_rate = 1.0 / 10.0
  def __init__(self, seed, sigma):
    np.random.seed(seed)
    self.events = []
    self.time = 0
    self.noise = lambda: np.random.normal(0, sigma) if sigma > 0 else 0.0

  @property
  def trace(self):
    return Trace(self.events, 1.0)

  def AddLEDEvent(self, state):
    self.time += int(1.0 / self.report_rate)
    self.events.append(LEDEvent(self.time, state=state))

  def AddScreenDraw(self, state):
    self.time += int(1.0 / self.report_rate)
    self.events.append(ScreenDrawEvent(self.time, state=state,
                                       start_time = self.time - 5))

  def AddFingerStationary(self, location, samples):
    location = float(location)
    for i in range(samples):
      self.time += int(1.0 / self.report_rate)
      self.events.append(FingerEvent(self.time, location + self.noise()))

  def AddFingerTransition(self, start, end, samples):
    for i in range(samples):
      self.time += int(1.0 / self.report_rate)
      location = float(start + (end - start) * i / (samples - 1))
      self.events.append(FingerEvent(self.time, location + self.noise()))

  def AddLineDraws(self, start, end, samples):
    for i in range(samples):
      self.time += int(1.0 / self.report_rate)
      location = float(start + (end - start) * i / (samples - 1))
      self.events.append(LineDrawEvent(self.time, location + self.noise(),
                                       start_time = self.time - 5))

  def AddLineReset(self):
    self.time += int(1.0 / self.report_rate)
    self.events.append(LineDrawEvent(self.time, None, start_time = self.time))


def event_time(i):
  """Returns time of event number i."""
  return int((i + 1) / TraceBuilder.report_rate)


class TraceTests(unittest.TestCase):
  def assertArrayAlmostEqual(self, a, b):
    """Checks if all array values are (nearly) equal. Including NaNs."""
    a_nan = np.isnan(a)
    b_nan = np.isnan(b)
    self.assertTrue(np.allclose(a_nan, b_nan))
    self.assertTrue(np.allclose(a[~a_nan], b[~b_nan]))

  def TapTrace(self):
    """Trace that we expect from a tap gesture.

    LED on, Screen to black, LED off, screen to white.
    """
    builder = TraceBuilder(0, 0)
    builder.AddLEDEvent(Event.STATE_ON)
    builder.AddScreenDraw(Event.STATE_BLACK)
    builder.AddLEDEvent(Event.STATE_OFF)
    builder.AddScreenDraw(Event.STATE_WHITE)
    return builder.trace

  def LEDCalibTrace(self):
    """Trace that we expect from an LED calibration.

    LED1 on, LED2 on, LED1 off, LED2 off.
    """
    builder = TraceBuilder(0, 0)
    builder.AddLEDEvent(Event.STATE_ON)
    builder.AddLEDEvent(Event.STATE_ON)
    builder.AddLEDEvent(Event.STATE_OFF)
    builder.AddLEDEvent(Event.STATE_OFF)
    return builder.trace

  def FingerMotionTrace(self, seed, sigma):
    """Simple finger motion trace.

    The finger moves in the following pattern:
    wait at 0
    move from 0 to 200
    wait at 200
    move from 200 to 0
    wait at 0
    """
    start = 0
    end = 200
    builder = TraceBuilder(seed, sigma)
    builder.AddFingerStationary(start, 10)
    builder.AddFingerTransition(start, end, 20)
    builder.AddFingerStationary(end, 10)
    builder.AddFingerTransition(end, start, 20)
    builder.AddFingerStationary(start, 10)
    return builder.trace

  def LineDrawTrace(self, seed, sigma):
    """Simple trace of line draws.

    Line drawing from 0 to 200, a line reset, then drawing from 200 to 0.
    """
    start = 0
    end = 200
    builder = TraceBuilder(seed, sigma)
    builder.AddLineDraws(start, end, 10)
    builder.AddLineReset()
    builder.AddLineDraws(end, start, 10)
    return builder.trace

  def assert_steady_rise_and_fall(self, time_series):
    mid_point = (len(time_series) / 2)

    # The first event always comes at time 10, before the values should
    # be NaN
    self.assertTrue(np.all(np.isnan(time_series[0:4])))

    # Check if the time series is going from 0 to 200 and back to 0 again
    self.assertAlmostEqual(time_series[10], 0)
    self.assertAlmostEqual(time_series[mid_point], 200)
    self.assertAlmostEqual(time_series[-1], 0)

    # Make sure the graph is steadily growing towards the midpoint, then
    # steadily falling
    deriv1 = np.diff(time_series)
    deriv1[np.isnan(deriv1)] = 0
    self.assertTrue(np.all(deriv1[:mid_point] >= 0))
    self.assertTrue(np.all(deriv1[mid_point:] <= 0))

  def test_finger_time_series(self):
    noiseless_finger_trace = self.FingerMotionTrace(0, 0)
    time_series = noiseless_finger_trace.finger
    deriv1 = np.diff(time_series)
    deriv2 = np.diff(deriv1)
    deriv1[np.isnan(deriv1)] = 0
    deriv2[np.isnan(deriv2)] = 0

    self.assert_steady_rise_and_fall(time_series)

    # Make sure there are no sudden jumps, i.e. we are interpolating.
    self.assertTrue(np.all(np.abs(deriv1) < 1.5))

    # Count number of edges in graph, there should only be 4.
    self.assertEqual(np.sum(np.abs(deriv2) > 0.5), 4)

  def test_finger_interpolation(self):
    events = [
      FingerEvent(1, 100.0),
      FingerEvent(5, 200.0),
      FingerEvent(7, 300.0),
    ]

    # Expected time series
    target = np.asarray([np.nan, 100, 125, 150, 175, 200, 250, 300])

    trace = Trace(events, 1.0)
    self.assertArrayAlmostEqual(trace.finger, target)

  def test_calib_finger_interpolation(self):
    events = [
      FingerEvent(1, 100.0),
      FingerEvent(5, 200.0),
      FingerEvent(7, 300.0),
    ]

    # Expected time series. Same as in test_finger_interpolation minus 10.
    target = np.asarray([np.nan, 90, 115, 140, 165, 190, 240, 290])

    trace = Trace(events, 1.0)
    trace.ApplyFingerLocationCalib(-10)
    self.assertArrayAlmostEqual(trace.finger, target)

  def test_line_draw_steps(self):
    events = [
      LineDrawEvent(2, 100.0, start_time=1),
      LineDrawEvent(4, 200.0, start_time=3),
      LineDrawEvent(6, None, start_time=5),
      LineDrawEvent(8, 300.0, start_time=7),
    ]
    trace = Trace(events, 1.0)

    # Expected time series
    nan = np.nan
    start = np.asarray([nan, 100, 100, 200, 200, nan, nan, 300, 300])
    end   = np.asarray([nan, nan, 100, 100, 200, 200, nan, nan, 300])

    self.assertArrayAlmostEqual(trace.line_draw_start, start)
    self.assertArrayAlmostEqual(trace.line_draw_end, end)

  def test_line_draw_time_series(self):
    noiseless_line_trace = self.LineDrawTrace(0, 0)
    start_time_series = noiseless_line_trace.line_draw_start
    end_time_series = noiseless_line_trace.line_draw_end

    # After a line reset, the time series should show NaNs until a new line draw
    # has happened
    self.assertTrue(np.isnan(end_time_series[115]))

    # Before any line draw, the time series should show NaNs.
    self.assertTrue(np.all(np.isnan(end_time_series[0:4])))

    self.assert_steady_rise_and_fall(start_time_series)
    self.assert_steady_rise_and_fall(end_time_series)

    # Derive and get rid of NaNs so we can calculate the number of steps
    start_deriv1 = np.diff(start_time_series)
    end_deriv1 = np.diff(end_time_series)
    start_deriv1[np.isnan(start_deriv1)] = 0
    end_deriv1[np.isnan(end_deriv1)] = 0

    # Make sure we have 18 steps, i.e. non-interpolated values.
    self.assertEqual(np.sum(np.abs(start_deriv1) > 1), 18)
    self.assertEqual(np.sum(np.abs(end_deriv1) > 1), 18)

  def test_led_event_time_series(self):
    time_series = self.LEDCalibTrace().led

    # start condition
    self.assertAlmostEqual(time_series[0], 0)
    # 1st led on
    self.assertAlmostEqual(time_series[event_time(0)], 1)
    # 2nd led on
    self.assertAlmostEqual(time_series[event_time(1)], 2)
    # 1st led off
    self.assertAlmostEqual(time_series[event_time(2)], 1)
    # 2nd led off
    self.assertAlmostEqual(time_series[event_time(3)], 0)

  def test_calib_led_event_time_series(self):
    trace = self.LEDCalibTrace()
    trace.ApplyLEDCalib(2, -2)
    time_series = trace.led

    # start condition
    self.assertAlmostEqual(time_series[0], 0)
    # 1st led on
    self.assertAlmostEqual(time_series[event_time(0) + 2], 1)
    # 2nd led on
    self.assertAlmostEqual(time_series[event_time(1) + 2], 2)
    # 1st led off
    self.assertAlmostEqual(time_series[event_time(2) - 2], 1)
    # 2nd led off
    self.assertAlmostEqual(time_series[event_time(3) - 2], 0)

  def test_tap_event_time_series(self):
    tap_trace = self.TapTrace()
    led_ts = tap_trace.led
    screen_ts = tap_trace.screen_draw_end

    # start condition
    self.assertAlmostEqual(led_ts[0], 0)
    self.assertAlmostEqual(screen_ts[0], 0)

    # led on
    self.assertAlmostEqual(led_ts[event_time(0)], 1)
    self.assertAlmostEqual(screen_ts[event_time(0)], 0)

    # screen draws black
    self.assertAlmostEqual(led_ts[event_time(1)], 1)
    self.assertAlmostEqual(screen_ts[event_time(1)], 1)

    # led off
    self.assertAlmostEqual(led_ts[event_time(2)], 0)
    self.assertAlmostEqual(screen_ts[event_time(2)], 1)

    # screen draws white
    self.assertAlmostEqual(led_ts[event_time(3)], 0)
    self.assertAlmostEqual(screen_ts[event_time(3)], 0)

  def test_find(self):
    trace = self.FingerMotionTrace(0, 0)
    prev_event = trace[0]
    target_event = trace[1]
    next_event = trace[2]
    target_time = target_event.time

    def assert_correct_find(time, algorithm, target):
      result = trace.Find(FingerEvent, time, algorithm)
      self.assertEqual(result, target)

    assert_correct_find(target_time - 6, "closest", prev_event)
    assert_correct_find(target_time - 4, "closest", target_event)
    assert_correct_find(target_time    , "closest", target_event)
    assert_correct_find(target_time + 4, "closest", target_event)
    assert_correct_find(target_time + 6, "closest", next_event)

    assert_correct_find(target_time - 6, "before", prev_event)
    assert_correct_find(target_time - 4, "before", prev_event)
    assert_correct_find(target_time    , "before", target_event)
    assert_correct_find(target_time + 4, "before", target_event)
    assert_correct_find(target_time + 6, "before", target_event)

    assert_correct_find(target_time - 6, "after", target_event)
    assert_correct_find(target_time - 4, "after", target_event)
    assert_correct_find(target_time    , "after", target_event)
    assert_correct_find(target_time + 4, "after", next_event)
    assert_correct_find(target_time + 6, "after", next_event)

  def test_line_reset_segmentation(self):
    trace = self.LineDrawTrace(0, 0)
    segments = list(trace.SegmentedByLineReset())
    self.assertEqual(len(segments), 2)

  def test_linear_finger_motion(self):
    for seed in range(20):
      trace = self.FingerMotionTrace(seed, 0.2)
      trace = trace.Trimmed(0, 350)
      start, end = trace.FindLinearFingerMotion()
      self.assertLessEqual(np.abs(start.time - 115), 10)
      self.assertLessEqual(np.abs(end.time - 295), 10)

  def test_stationary_finger(self):
    for seed in range(20):
      trace = self.FingerMotionTrace(seed, 0.2)
      start, end = trace.FindStationaryFinger(500)
      self.assertLessEqual(np.abs(start.time - 305), 10)
      self.assertLessEqual(np.abs(end.time - 405), 10)

  def test_finger_time_at_location(self):
    trace = self.FingerMotionTrace(0, 0)

    # Find finger crossing on first transition (time 100-300)
    for location in range(0, 200, 5):
      finger_event = trace.FindFingerCrossing(float(location), 200)
      finger_time = finger_event.time

      # check if detected time is during first transition
      self.assertLess(finger_time, 350)

      # check if the location at that time is close to the target location
      self.assertLess(np.abs(trace.finger[finger_time] - location), 2.0)

    # Find finger crossing on second transition (time 400-600)
    for location in range(0, 200, 5):
      finger_event = trace.FindFingerCrossing(float(location), 500)
      finger_time = finger_event.time

      # check if detected time is during second transition
      self.assertGreater(finger_time, 350)

      # check if the location at that time is close to the target location
      self.assertLess(np.abs(trace.finger[finger_time] - location), 2.0)

  def test_empty_trace(self):
    trace = Trace([], 1.0)
    self.assertEqual(len(trace), 0)
    self.assertEqual(len(trace.finger), 0)
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module provides classes for measuring different touch latencies.

This file depends on the detection module to run video processing to generate
traces which are then processed to determine the latencies.
"""
import bisect
import numpy as np
import scipy.interpolate as interpolate
import scipy.signal as signal

class Event(object):
  """Describes an event detected in the camera stream."""
  LINE_DRAW_START = "LineDrawStart"
  LINE_DRAW_END = "LineDrawEnd"
  LINE_RESET = "LineReset"
  SCREEN_DRAW_START = "ScreenDrawStart"
  SCREEN_DRAW_END = "ScreenDrawEnd"
  FINGER_MOVED = "FingerMoved"
  FINGER_DOWN = "FingerDown"
  FINGER_UP = "FingerUp"

  def __init__(self, time, event_type, location=None, color=None):
    self.event_type = event_type
    self.time = time
    self.location = location
    self.color = color

  def __repr__(self):
    optional = []
    if self.location:
      optional.append("location=%.1f" % self.location)
    if self.color:
      optional.append("color=%s" % self.color)

    optional_str = ""
    if optional:
      optional_str = " (%s)" % (",".join(optional))
    return "%d\t%s\t%s" % (self.time, self.event_type, optional_str)


class Trace(object):
  """Contains a list of events ordered by time.

  Allows the trace to be modified or information to be extracted from it.
  """
  def __init__(self, events=None):
    self._events = events or []
    self._times = [event.time for event in self._events]

  def AddAll(self, events):
    for event in events:
      self.Add(event)

  def Add(self, event):
    i = bisect.bisect_left(self._times, event.time)
    self._events.insert(i, event)
    self._times.insert(i, event.time)

  def __str__(self):
    return "\n".join([str(e) for e in self._events])

  def __repr__(self):
    return str(self)

  def Events(self, event_type=None, color=None):
    """Return list of events of event_type."""
    if event_type is None:
      return self._events
    else:
      return [e for e in self._events
              if (not event_type or e.event_type == event_type) and
                 (not color or e.color == color)]

  def Times(self, event_type=None, color=None):
    """Return numpy array of times of event_type."""
    return np.asarray([e.time for e in self.Events(event_type, color)])

  def Time(self, event_type=None, color=None):
    """Return numpy array of times of event_type."""
    times = self.Times(event_type, color)
    if not times:
      raise Exception("No event of type " + event_type)
    if len(times) > 1:
      raise Exception("Multiple events of type " + event_type)
    return times[0]

  def Locations(self, event_type=None):
    """Return numpy array of locations of event_type."""
    return np.asarray([e.location for e in self.Events(event_type)])

  def TrimByLocation(self, loc_min, loc_max):
    """Return a TraceProcessor with events filtered by location.

    The new trace processor contains the same events minus the ones the ones
    with their location outside the [loc_min,loc_max) range.
    """
    if loc_min > loc_max:
      (loc_min, loc_max) = (loc_max, loc_min)
    events = [e for e in self._events
                if e.location >= loc_min and e.location <= loc_max]
    return Trace(events)

  def TrimByTime(self, time_min, time_max):
    """Return a TraceProcessor with events filtered by time.

    The new trace processor contains the same events minus the ones
    with their timestamp outside the [time_min,time_max) range.
    """
    if time_min > time_max:
      (time_min, time_max) = (time_max, time_min)
    events = [e for e in self._events
                if e.time >= time_min and e.time < time_max]
    return Trace(events)

  def LocationTimeMap(self, event_type):
    """Return interp1d object mapping location to time."""
    finger_loc = self.Locations(event_type)
    finger_time = self.Times(event_type)
    return interpolate.interp1d(finger_loc, finger_time)

  def TimeLocationMap(self, event_type):
    """Return interp1d object mapping time to location."""
    finger_loc = self.Locations(event_type)
    finger_time = self.Times(event_type)
    return interpolate.interp1d(finger_time, finger_loc)

  def FindLinearMotionRange(self, event_type):
    """Return (start, end) event of range in which event shows linear motion.

    Searches for the fastest motion of event_type and returns a (start, end)
    tuple of events indicating the range in which this motion is linear
    at this speed.
    """
    SMOOTHING_KERNEL = 9

    events = self.Events(event_type)
    locations = [e.location for e in events]

    # Calculated smoothed first derivative
    def MovingAvg(f, N):
      return signal.convolve(f, np.ones(N,) / N, "valid")
    smoothed = MovingAvg(locations, SMOOTHING_KERNEL)
    speed = np.abs(MovingAvg(np.diff(smoothed), SMOOTHING_KERNEL))

    # Allow 20% variation of the maximum speed in linear range.
    max_speed_idx = np.argmax(speed)
    min_speed = speed[max_speed_idx] * 0.8

    # Find area in which the robot continuously has this speed.
    start = 0
    end = len(speed)
    for i in range(max_speed_idx, 0, -1):
      if speed[i] < min_speed:
        start = i
        break
    for i in range(max_speed_idx, len(speed)):
      if speed[i] < min_speed:
        end = i
        break

    # Smoothing and deriving above reduces the array size, we have to account
    # for the shift in indices.
    start += SMOOTHING_KERNEL
    end += SMOOTHING_KERNEL

    return events[start], events[end]

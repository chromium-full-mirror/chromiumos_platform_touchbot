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

from detection import Frame, Line, Finger, Event
from videoproc import Viewer


class Trace(object):
  """Contains a list of events ordered by time.

  Allows the trace to be modified or information to be extracted from it.
  """
  def __init__(self, events=None):
    if events:
      self._events = events
      self._times = [event.time for event in events]
    else:
      self._events = []
      self._times = []

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

  def Events(self, event_type=None):
    """Return list of events of event_type."""
    if event_type is None:
      return self._events
    else:
      return [e for e in self._events if e.event_type == event_type]

  def Times(self, event_type=None):
    """Return numpy array of times of event_type."""
    return np.asarray([e.time for e in self.Events(event_type)])

  def Locations(self, event_type=None):
    """Return numpy array of locations of event_type."""
    return np.asarray([e.location for e in self.Events(event_type)])

  def TrimByLocation(self, loc_min, loc_max):
    """Return a TraceProcessor with events filtered by location.

    The new trace processor contains the same events minus the ones
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
    start += (SMOOTHING_KERNEL - 1) + 1
    end += (SMOOTHING_KERNEL - 1) + 1

    return events[start], events[end]


class LineDrawLatency(object):
  """Calculates latency from a line draw video."""

  def ProcessVideo(self, screen, video, debug=False):
    """Process the video into a trace of events.

    Returns a trace object with all events generated.
    """
    end_frame = Frame(video.FrameAt(-1), screen.shape)

    finger = Finger()
    line = Line(end_frame, debug=debug)

    trace = Trace()
    for i, im in video.Frames():
      print i, "/", video.num_frames
      frame = Frame(im, screen.shape, i)
      trace.AddAll(line.Update(frame, debug=debug))
      trace.AddAll(finger.Update(frame, debug=debug))
      if debug:
        Viewer.VideoFrame(line.debug_canvas.Scaled(4))
    return trace

  def ProcessTrace(self, trace):
    """Process a trace to extract line draw latencies.

    This trace can be generated by LineDrawLatency.ProcessVideo, this
    method returns two arrays. One containing the latencies measured
    at the start of a line segment draw, the other the latencies measured
    at the end of a line segment draw.
    """
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
    return start_lat, end_lat

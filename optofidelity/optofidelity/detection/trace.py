# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contracts import contract, new_contract
import bisect
import numpy as np
import scipy.interpolate as interpolate
import scipy.signal as signal

from optofidelity.videoproc import VideoException

class Event(object):
  """Describes an event detected in the camera stream."""
  LINE_DRAW_START = "LineDrawStart"
  LINE_DRAW_END = "LineDrawEnd"
  LINE_RESET = "LineReset"
  SCREEN_DRAW_START = "ScreenDrawStart"
  SCREEN_DRAW_END = "ScreenDrawEnd"
  FINGER_MOVED = "FingerMoved"
  LED_OFF = "LEDOff"
  LED_ON = "LEDOn"

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
new_contract('Event', Event)

class Trace(object):
  """Contains a list of events ordered by time.

  Allows the trace to be modified or information to be extracted from it.
  """

  linear_motion_smoothing_kernel = 9
  """Kernel size for smoothing the movement in linear motion detection."""

  linear_motion_max_speed_deviation = 0.2
  """How much can the speed deviate from the target speed to be considered
     part of the linear motion area."""

  @contract(events="list(Event)|None")
  def __init__(self, events=None):
    self._events = events or []
    self._times = [event.time for event in self._events]

  @contract(events="list(Event)")
  def AddAll(self, events):
    for event in events:
      self.Add(event)

  @contract(event=Event)
  def Add(self, event):
    i = bisect.bisect_left(self._times, event.time)
    self._events.insert(i, event)
    self._times.insert(i, event.time)

  def __str__(self):
    return "\n".join([str(e) for e in self._events])

  def __repr__(self):
    return str(self)

  def RequireEvents(self, *event_types):
    for event_type in event_types:
      if len(self.Events(event_type)) == 0:
        raise Exception("Trace does not show the events of type " + event_type)

  @contract(event_type=str, start_time=">=0|None")
  def Find(self, event_type, start_time=None):
    for i, event in enumerate(self.Events(event_type)):
      if start_time is None or event.time >= start_time:
        return i, event
    return -1, None


  @contract(event_type=str)
  def Split(self, event_type):
    """Split trace before each occurence of event_type."""
    events = []
    for event in self._events:
      if event.event_type == event_type:
        if events:
          yield Trace(events)
        events = []
      events.append(event)
    if events:
      yield Trace(events)

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
    return np.asarray([e.time for e in self.Events(event_type, color)], dtype=np.float)

  def Time(self, event_type=None, color=None):
    """Return numpy array of times of event_type."""
    times = self.Times(event_type, color)
    if len(times) == 0:
      raise VideoException("No event of type " + event_type)
    if len(times) > 1:
      raise VideoException("Multiple events of type " + event_type)
    return times[0]

  def Locations(self, event_type=None):
    """Return numpy array of locations of event_type."""
    return np.asarray([e.location for e in self.Events(event_type)], dtype=np.float)

  def LocationAt(self, event_type, time):
    """Return location of an event_type at the specified time."""
    mapping = self.TimeLocationMap(event_type)
    return mapping(time)

  def TrimByLocation(self, loc_min, loc_max, event_type=None):
    """Return a TraceProcessor with events filtered by location.

    The new trace processor contains the same events minus the ones the ones
    with their location outside the [loc_min,loc_max) range.
    With the argument event_type you can limit the trimming to a certain event
    type while retaining all other events.
    """
    if loc_min > loc_max:
      (loc_min, loc_max) = (loc_max, loc_min)
    events = [e for e in self._events
                if (e.event_type != event_type or
                    (e.location >= loc_min and e.location <= loc_max))]
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

  def Speeds(self, event_type):
    events = self.Events(event_type)
    locations = np.asarray([e.location for e in events])
    times = np.asarray([e.time for e in events])

    # Calculated smoothed first derivative
    def MovingAvg(f, N):
      return signal.convolve(f, np.ones(N,) / N, "valid")
    smoothing_kernel = self.linear_motion_smoothing_kernel
    smoothed = MovingAvg(locations, smoothing_kernel)
    speed = np.abs(MovingAvg(np.diff(smoothed), smoothing_kernel))

    delta_t = np.diff(MovingAvg(times, smoothing_kernel))
    delta_l = np.diff(MovingAvg(locations, smoothing_kernel))
    speed = np.abs(delta_l / delta_t)
    speed = MovingAvg(speed, smoothing_kernel)

    # Smoothing and deriving above reduces the array size, we have to account
    # for the shift in indices.
    reshaped = np.zeros((len(events),))
    reshaped[smoothing_kernel-1:-smoothing_kernel] = speed
    return reshaped

  def FindLinearMotionRange(self, event_type):
    """Return (start, end) event of range in which event shows linear motion.

    Searches for the fastest motion of event_type and returns a (start, end)
    tuple of events indicating the range in which this motion is linear
    at this speed.
    """
    events = self.Events(event_type)
    speed = self.Speeds(event_type)

    # Allow 20% variation of the maximum speed in linear range.
    max_speed_idx = np.argmax(speed)
    min_speed_factor = (1 - self.linear_motion_max_speed_deviation)
    min_speed = speed[max_speed_idx] * min_speed_factor

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
    return events[start], events[end]

  def FindStaticMotionRange(self, event_type):
    """Return (start, end) event of range in which event shows no motion.

    The static motion has to be enclosed between motion. No motion at the
    beginning or end of the trace will be ignored.
    """
    events = self.Events(event_type)
    speed = self.Speeds(event_type)

    moved = False
    start = None
    end = None
    for i, speed in enumerate(speed):
      if speed > 1:
        moved = True
        if end is not None:
          break
      if moved and speed < 0.05:
        if start is None:
          start = i
        end = i

    if start is None or end is None:
      raise Exception("Cannot find static motion range")
    return events[start], events[end]

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import numpy as np

from optofidelity.util import const_property
import scipy.signal as signal

from .events import (Event, FingerEvent, LEDEvent, LineDrawEvent,
                     ScreenDrawEvent)


class Trace(list):
  """Contains a list of events ordered by time.

  Allows the trace to be modified or information to be extracted from it.
  It exposes multiple time-series arrays plotting events over time.
  """

  SPEED_SMOOTHING_KERNEL = 8
  """Kernel size for smoothing the movement in linear motion detection."""

  LINEAR_MOTION_MAX_SPEED_DEVIATION = 0.2
  """How much can the speed deviate from the target speed to be considered
     part of the linear motion area."""

  def __str__(self):
    return "\n".join([str(e) for e in self])

  def __repr__(self):
    return str(self)

  @const_property
  def start_time(self):
    """:returns int: start time of first event."""
    if len(self) > 0:
      return self[0].start_time or self[0].time
    return 0

  @const_property
  def end_time(self):
    """:returns int: end time of last event."""
    if len(self) > 0:
      return self[-1].time
    return 0

  @const_property
  def finger(self):
    """:returns np.ndarray: time-series array of the finger location."""
    return self._TimeSeries(FingerEvent, interpolate=True)

  @const_property
  def finger_speed(self):
    """:returns np.ndarray: time-series array of finger speed."""
    return self._CalculateSpeed(self.finger)

  @const_property
  def line_draw_start(self):
    """:returns np.ndarray: time-series array of where line draws start."""
    return self._TimeSeries(LineDrawEvent, True)

  @const_property
  def line_draw_end(self):
    """:returns np.ndarray: time-series array of where line draws end."""
    return self._TimeSeries(LineDrawEvent, False)

  @const_property
  def screen_draw_start(self):
    """:returns np.ndarray: binary time-series of when screen draws start."""
    return self._TimeSeries(ScreenDrawEvent, True)

  @const_property
  def screen_draw_end(self):
    """:returns np.ndarray: binary time-series of when screen draws end."""
    return self._TimeSeries(ScreenDrawEvent, False)

  @const_property
  def led(self):
    """:returns np.ndarray: time-series of how many LEDs are on at any given
                time."""
    return self._TimeSeries(LEDEvent)

  def RequireEventTypes(self, *event_types):
    """Raise an exception if any of the event types is not present.

    :param List[type] event_types
    """
    for event_type in event_types:
      if len(self.FilteredByType(event_type)) == 0:
        raise Exception("Trace does not show the events of type " + event_type)

  def HasEventTypes(self, *event_types):
    """Return True only if all event types are present.

    :param List[type] event_types
    :returns bool
    """
    for event_type in event_types:
      if len(self.FilteredByType(event_type)) == 0:
        return False
    return True

  def Trimmed(self, start, end):
    """Return a copy of the trace trimmed by start and end time.

    :param int start: start time of trim
    :param int end: end time of trim.
    :returns Trace
    """
    return Trace([e for e in self if start <= e.time < end])

  def Find(self, event_type, time, where="closest"):
    """Find first event of event_type around time.

    :param type event_type: event type to find.
    :param int time: target time around which to search.
    :param str where: either "closest", "before" or "after".
    """
    prev_event = None
    for event in self.FilteredByType(event_type):
      if event.time == time:
        return event
      elif event.time > time:
        if where == "closest":
          if prev_event is None:
            return event
          delta_this = event.time - time
          delta_prev = time - prev_event.time
          if delta_this > delta_prev:
            return prev_event
          else:
            return event
        elif where == "before":
          return prev_event
        elif where == "after":
          return event
      prev_event = event
    if where == "before":
      return prev_event
    return None

  def FindStateSwitch(self, event_type, target_state):
    """Return first event at which event_type switches to target_state.

    :param type event_type: Event type to find.
    :param bool target_state: Target state to find.
    """
    for event in self.FilteredByType(event_type):
      if event.state == target_state:
        return event
    return None

  def FindFingerCrossing(self, target_location, target_time):
    """Return time at which the finger crossed the location of target_event.

    :param float target_location: location which the finger should cross
    :param int target_time: time at which to start searching.
    """
    # Shift finger location to be zero at the target location and positive
    # at the target time.
    shifted = self.finger - target_location
    if shifted[target_time] < 0:
      shifted *= -1

    # Find zero crossing of shifted, which is when the finger is crossing.
    for i in range(max(len(shifted) - target_time, target_time)):
      left = target_time - i
      right = target_time + i
      if left > 0 and left < len(shifted) and shifted[left] <= 0:
        return FingerEvent(int(left), target_location)
      if right > 0 and right < len(shifted) and shifted[right] <= 0:
        return FingerEvent(int(right), target_location)

    return None

  def SegmentedByLineReset(self):
    """Segment into multiple traces separated by line reset events."""
    events = []
    for event in self:
      if isinstance(event, LineDrawEvent) and event.location is None:
        if events:
          yield Trace(events)
          events = []
      else:
        events.append(event)
    if events:
      yield Trace(events)

  def SegmentedByLED(self):
    """Segment into traces starting with each LED on event."""
    events = None
    for event in self:
      if isinstance(event, LEDEvent) and event.state == Event.STATE_ON:
        if events:
          yield Trace(events)
        events = []
      if events is not None:
        events.append(event)
    if events:
      yield Trace(events)

  def FilteredByType(self, event_type):
    """
    :param type event_type
    :returns Trace: filtered to only include events of event_type.
    """
    return Trace([e for e in self if isinstance(e, event_type)])

  def FindLinearFingerMotion(self):
    """Return (start, end) event of range in which event shows linear motion.

    Searches for the fastest motion of the finger and returns a (start, end)
    tuple of events indicating the range in which this motion is linear
    at this speed.
    :returns Tuple[Event, Event]
    """
    # Allow 20% variation of the maximum speed in linear range.
    speed = self.finger_speed
    speed[np.isnan(speed)] = 0
    max_speed_idx = np.argmax(speed)
    min_speed_factor = (1 - self.LINEAR_MOTION_MAX_SPEED_DEVIATION)
    min_speed = self.finger_speed[max_speed_idx] * min_speed_factor

    # Find area in which the robot continuously has this speed.
    start = 0
    end = len(self.finger_speed)
    for i in range(max_speed_idx, 0, -1):
      if speed[i] < min_speed:
        start = i
        break
    for i in range(max_speed_idx, len(self.finger_speed)):
      if speed[i] < min_speed:
        end = i
        break
    return self.Find(FingerEvent, start), self.Find(FingerEvent, end)

  def FindStationaryFinger(self):
    """Return (start, end) event of range in which event shows no motion.

    The stationary range has to be enclosed between motion.
    :returns Tuple[Event, Event]
    """
    moved = False
    start = None
    end = None
    for i, speed in enumerate(self.finger_speed):
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
    return self.Find(FingerEvent, start), self.Find(FingerEvent, end)

  def _TimeSeries(self, event_type, start_time=False, interpolate=False):
    """Turn list of events into a time series plot of this event.

    location based events will result in a location over time plot, whereas
    state-based events will be plotted as a step function, increasing by
    one for each positive state and decreasing for each negative state.

    :param type event_type: event type to turn into a time series
    :param bool start_time: Use events start time in plot instead of time.
    :param bool interpolate: Use linear interpolation between events instead of
           a step function.
    """
    if len(self) == 0:
      return np.empty((0,))

    if event_type in (FingerEvent, LineDrawEvent):
      current_value = np.nan
    elif event_type in (LEDEvent, ScreenDrawEvent):
      current_value = 0
    else:
      raise ValueError("Unknown event type: %s" % event_type)

    array = np.empty((self.end_time + 1,))
    array[:] = current_value
    last_time = 0

    for event in self.FilteredByType(event_type):
      time = event.time
      if start_time and event.start_time is not None:
        time = event.start_time

      if event.state is not None:
        current_value += 1 if event.state else -1
      elif event.location is not None:
        current_value = event.location
      else:
        current_value = np.nan

      array[time] = current_value
      last_value = array[last_time]
      if not np.isnan(last_value):
        if interpolate:
          samples = time - last_time + 1
          array[last_time:(time + 1)] = np.linspace(last_value, current_value,
                                                    samples)
        else:
          array[(last_time + 1):time] = last_value
      last_time = time

    array[last_time:] = current_value
    return array

  def _CalculateSpeed(self, time_series):
    """Calculate a low pass filtered derivative of the time series.

    :param np.ndarray time_series
    :returns np.ndarray
    """
    # Calculated smoothed first derivative
    smoothing_kernel = self.SPEED_SMOOTHING_KERNEL
    def LowPass(f, N=smoothing_kernel):
      return signal.convolve(f, np.ones(N,) / N, "valid")

    if len(time_series) < smoothing_kernel * smoothing_kernel:
      # We can't smooth with too few samples
      return np.abs(np.diff(time_series))

    smoothed = LowPass(time_series)
    speed = np.abs(LowPass(np.diff(smoothed)))

    # Smoothing and deriving above reduces the array size, we have to account
    # for the shift in indices.
    reshaped = np.zeros((len(time_series),))
    reshaped[smoothing_kernel-1:-smoothing_kernel] = speed
    return reshaped

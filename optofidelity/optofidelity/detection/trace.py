# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contracts import contract, new_contract
import numpy as np
import scipy.signal as signal


class Event(object):
  """Describes an event detected in the camera stream."""
  type_name = None

  STATE_ON = True
  STATE_OFF = False
  STATE_WHITE = False
  STATE_BLACK = True

  @contract(time=int, location="number|None", start_time="int|None",
            state="bool|None")
  def __init__(self, time, location=None, start_time=None, state=None):
    self.time = time
    self.location = float(location) if location is not None else None
    self.start_time = start_time
    self.state = state

  def __repr__(self):
    optional = []
    if self.location is not None:
      optional.append("location=%.1f" % self.location)
    if self.start_time is not None:
      optional.append("start_time=%d" % self.start_time)
    if self.state is not None:
      optional.append("state=On" if self.state else "state=Off")

    optional_str = ""
    if optional:
      optional_str = " (%s)" % (", ".join(optional))
    return "%d\t%s\t%s" % (self.time, self.type_name, optional_str)
new_contract('Event', Event)


class LineDrawEvent(Event):
  type_name = "LineDraw"

  @contract(time=int, location="number|None", start_time=int)
  def __init__(self, time, location, start_time):
    Event.__init__(self, time, location, start_time)


class FingerEvent(Event):
  type_name = "Finger"

  @contract(time=int, location="number")
  def __init__(self, time, location):
    Event.__init__(self, time, location)


class ScreenDrawEvent(Event):
  type_name = "ScreenDraw"

  @contract(time=int, start_time=int, state=bool)
  def __init__(self, time, start_time, state):
    Event.__init__(self, time, None, start_time, state)


class LEDEvent(Event):
  type_name = "LED"

  @contract(time=int, state=bool)
  def __init__(self, time, state):
    Event.__init__(self, time, None, None, state)


class Trace(object):
  """Contains a list of events ordered by time.

  Allows the trace to be modified or information to be extracted from it.
  It exposes multiple time-series arrays plotting events over time.

  finger: finger location
  finger_speed: low pass filtered first derivative of finger location
  line_draw_start: Location of start of line draws
  line_draw_end: Location of end of line draws
  screen_draw_start: Step function that switches to 1 when the screen starts
                     switching to black, and back to 0 when it starts switching
                     to white.
  screen_draw_end: Step function that switches to 1 when the screen finished
                   switching to black, and back to 0 when it finished switching
                   to white.
  led: Step function that increases by 1 with every LED that turns on, and
       decreases with every LED that turns off.
  """

  speed_smoothing_kernel = 8
  """Kernel size for smoothing the movement in linear motion detection."""

  linear_motion_max_speed_deviation = 0.2
  """How much can the speed deviate from the target speed to be considered
     part of the linear motion area."""

  @contract(events="list(Event)")
  def __init__(self, events):
    """Create a new trace from a list of events.

    The list of events is expected to be sorted by time.
    """
    self._events = events

    if events:
      self.start_time = self._events[0].start_time or self._events[0].time
      self.end_time = self._events[-1].time

      self.finger = self._TimeSeries(FingerEvent, interpolate=True)
      self.finger_speed = self._CalculateSpeed(self.finger)
      self.line_draw_start = self._TimeSeries(LineDrawEvent, True)
      self.line_draw_end = self._TimeSeries(LineDrawEvent, False)
      self.screen_draw_start = self._TimeSeries(ScreenDrawEvent, True)
      self.screen_draw_end = self._TimeSeries(ScreenDrawEvent, False)
      self.led = self._TimeSeries(LEDEvent)

  def __str__(self):
    return "\n".join([str(e) for e in self._events])

  def __repr__(self):
    return str(self)

  @property
  def begin(self):
    return self._events[0].time

  @property
  def end(self):
    return self._events[-1].time

  def RequireEventTypes(self, *event_types):
    """Raise an exception if any of the event types is not present."""
    for event_type in event_types:
      if len(self.Events(event_type)) == 0:
        raise Exception("Trace does not show the events of type " + event_type)

  def HasEventTypes(self, *event_types):
    """Return True only if all event types are present."""
    for event_type in event_types:
      if len(self.Events(event_type)) == 0:
        return False
    return True

  @contract(start=int, end=int)
  def Trimmed(self, start, end):
    """Return a copy of the trace trimmed by start and end time."""
    return Trace([e for e in self._events if e.time >= start and e.time < end])

  @contract(event_type=type, time=">=0", where=str)
  def Find(self, event_type, time, where="closest"):
    """Find first event of event_type around time.

    'where' can be either before, closest or after to determine in which
    direction should be searched.
    """
    prev_event = None
    for event in self.Events(event_type):
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
    return None

  @contract(event_type=type, target_state=bool)
  def FindStateSwitch(self, event_type, target_state):
    """Return first event at which event_type switches to target_state."""
    for event in self.Events(event_type):
      if event.state == target_state:
        return event
    return None

  def FindFingerCrossing(self, target_event, offset=0):
    """Return time at which the finger crossed the location of target_event."""
    target_time = target_event.time

    # Shift finger location to be zero at the target location and positive
    # at the target time.
    shifted = self.finger - target_event.location - offset
    if shifted[target_time] < 0:
      shifted *= -1

    # Find zero crossing of shifted, which is when the finger is crossing.
    for i in range(max(len(shifted) - target_time, target_time)):
      left = target_time - i
      right = target_time + i
      if left > 0 and left < len(shifted) and shifted[left] <= 0:
        return FingerEvent(int(left), target_event.location)
      if right > 0 and right < len(shifted) and shifted[right] <= 0:
        return FingerEvent(int(right), target_event.location)

    return None

  def SegmentedByLineReset(self):
    """Segment into multiple traces separated by line reset events."""
    events = []
    for event in self._events:
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
    for event in self._events:
      if isinstance(event, LEDEvent) and event.state == Event.STATE_ON:
        if events:
          yield Trace(events)
        events = []
      if events is not None:
        events.append(event)
    if events:
      yield Trace(events)

  def Events(self, event_type=None):
    """Return list of events of event_type."""
    if event_type is None:
      return self._events
    else:
      return [e for e in self._events if isinstance(e, event_type)]

  def FindLinearFingerMotion(self):
    """Return (start, end) event of range in which event shows linear motion.

    Searches for the fastest motion of event_type and returns a (start, end)
    tuple of events indicating the range in which this motion is linear
    at this speed.
    """
    # Allow 20% variation of the maximum speed in linear range.
    speed = self.finger_speed
    speed[np.isnan(speed)] = 0
    max_speed_idx = np.argmax(speed)
    min_speed_factor = (1 - self.linear_motion_max_speed_deviation)
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

  @contract(event_type=type, start_time=bool, interpolate=bool)
  def _TimeSeries(self, event_type, start_time=False, interpolate=False):
    """Turn list of events into a time series plot of this event.

    location based events will result in a location over time plot, whereas
    state-based events will be plotted as a step function, increasing by
    one for each positive state and decreasing for each negative state.

    start_time: Use events start time in plot instead of time.
    interpolate: Use linear interpolation between events instead of a step
                 function.
    """
    if event_type in (FingerEvent, LineDrawEvent):
      current_value = np.nan
    elif event_type in (LEDEvent, ScreenDrawEvent):
      current_value = 0
    else:
      raise ValueError("Unknown event type: %s" % event_type)

    array = np.empty((self.end_time + 1,))
    array[:] = current_value
    last_time = 0

    for event in self.Events(event_type):
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

  @contract(time_series="array[N](float),N>0")
  def _CalculateSpeed(self, time_series):
    """Calculate a low pass filtered derivative of the time series."""
    # Calculated smoothed first derivative
    smoothing_kernel = self.speed_smoothing_kernel
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
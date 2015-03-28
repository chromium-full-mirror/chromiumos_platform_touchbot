# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Classes describing events detected in camera stream.

All classes use the same base class Event, which contains all information,
which means that the Event subclasses are mainly for convenience and do not
add any further functionality.
"""
from safetynet import TypecheckMeta, Optional

class Event(object):
  """Describes a generic event detected in the camera stream."""
  __metaclass__ = TypecheckMeta

  EVENT_TYPE_NAME = None

  STATE_ON = True
  STATE_OFF = False
  STATE_WHITE = False
  STATE_BLACK = True

  def __init__(self, time, location=None, start_time=None, state=None):
    """
    :param int time
    :param Optional[float] location
    :param Optional[int] start_time
    :param Optional[bool] state
    """
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
    return "%d\t%s\t%s" % (self.time, self.EVENT_TYPE_NAME, optional_str)


class LineDrawEvent(Event):
  EVENT_TYPE_NAME = "LineDraw"

  def __init__(self, time, location, start_time):
    """
    :param int time
    :param Optional[float] location
    :param int start_time
    """
    Event.__init__(self, time, location, start_time)


class FingerEvent(Event):
  EVENT_TYPE_NAME = "Finger"

  def __init__(self, time, location):
    """
    :param int time
    :param float location
    """
    Event.__init__(self, time, location)


class ScreenDrawEvent(Event):
  EVENT_TYPE_NAME = "ScreenDraw"

  def __init__(self, time, start_time, state):
    """
    :param int time
    :param int start_time
    :param bool state
    """
    Event.__init__(self, time, None, start_time, state)


class LEDEvent(Event):
  EVENT_TYPE_NAME = "LED"

  def __init__(self, time, state):
    """
    :param int time
    :param bool state
    """
    Event.__init__(self, time, None, None, state)


# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of two line draw delegates based on the same logic."""

from optofidelity.detection import (FingerDetector, FingerEvent,
                                    LineDetector, LineDrawEvent)
from optofidelity.system import BenchmarkSubject

from ._delegate import BenchmarkDelegate


class LineDrawDelegate(BenchmarkDelegate):
  """Contains the logic to perform line draw latency benchmarks."""

  CALIB_MOVE_DISTANCE = 10.0
  """Distance to move for the calibration movement (in mm)."""

  COMMANDS_DURATION = 7000
  """Duration of the full set of robot commands (in # of camera frames)."""

  CAMERA_FRAMERATE = 300
  """Framerate at which to record, in frames per second."""

  def InitializeProcessor(self, processor, video_reader, screen_calibration):
    processor.InitializeDetectors(LineDetector(), FingerDetector())

  def ExecuteOnSubject(self, subject):
    """Executes line draw and records the interaction.

    :param BenchmarkSubject subject
    """
    subject.camera.Prepare(self.COMMANDS_DURATION, self.CAMERA_FRAMERATE,
                           subject.exposure)

    # The robot will draw a line between the 'left' and 'right' location and
    # back. It will pause after the first bit of the line so the video
    # processing can calculate the offset between finger and line location.
    left = subject.top
    right = subject.bottom
    left_calib_stop = left + self.CALIB_MOVE_DISTANCE
    right_calib_stop = right - self.CALIB_MOVE_DISTANCE

    # Height of finger down and up state in cm
    down = -1.0
    up = 10.0

    # Tap to reset the screen, then draw from left to right.
    subject.TapOnTestPlane(left)
    subject.MoveOnTestPlane(left, down, blocking=True)

    subject.camera.Trigger()
    subject.StartCollection(self.COMMANDS_DURATION)

    subject.MoveOnTestPlane(left_calib_stop, down)
    subject.MoveOnTestPlane(right, down)
    subject.MoveOnTestPlane(right, up)

    # Tap to reset the screen, then draw from right to left.
    subject.TapOnTestPlane(right)
    subject.MoveOnTestPlane(right, down)
    subject.MoveOnTestPlane(right_calib_stop, down)
    subject.MoveOnTestPlane(left, down)
    subject.MoveOnTestPlane(left, up)

    subject.StopCollection()
    return subject.camera.ReceiveVideo()

  def ProcessTrace(self, trace, measurements):
    for pass_num, pass_trace in enumerate(trace.SegmentedByLineReset()):
      # Find pause after first movement to calibrate the offset between
      # finger and line location.
      if len(pass_trace.FilteredByType(LineDrawEvent)) < 6:
        continue

      # Find linear motion range
      start_event, end_event = pass_trace.FindLinearFingerMotion()
      if start_event is None or end_event is None:
        continue
      calib_start, calib_end = pass_trace.FindStationaryFinger(start_event.time)
      if calib_start is None or calib_end is None:
        continue

      line_at_calib = pass_trace.Find(LineDrawEvent, calib_end.time, "before")
      calib_offset = line_at_calib.uncalib_location - calib_end.uncalib_location
      pass_trace.ApplyFingerLocationCalib(calib_offset)

      # Filter draw events to only use locations during which the finger was
      # moving linearly.
      start_location = start_event.uncalib_location + calib_offset
      end_location = end_event.uncalib_location + calib_offset
      if start_location > end_location:
        (start_location, end_location) = (end_location, start_location)

      draw_events = pass_trace.FilteredByType(LineDrawEvent)
      draw_events = [e for e in draw_events if e.location >= start_location and
                                               e.location < end_location]
      if len(draw_events) < 2:
        continue

      for draw_event in draw_events:
        finger_event = pass_trace.FindFingerCrossing(draw_event.location,
                                                     draw_event.time)
        if finger_event is None:
          continue
        measurements.AddDrawEventMeasurement("LineDrawLatency", finger_event,
                                             draw_event, pass_num=pass_num)
        measurements.AddDroppedFramesMeasurement("DroppedFrameFrequency",
                                                 draw_event, pass_num=pass_num)

      line_location = pass_trace.line_draw_end
      for time in range(draw_events[0].time, draw_events[-1].time + 1):
        finger_event = pass_trace.FindFingerCrossing(line_location[time], time)
        if finger_event is None:
          continue
        measurements.AddTimeValueMeasurement("ContinuousLatency", time,
                                             time - finger_event.time,
                                             pass_num=pass_num)


class LineDrawStartDelegate(BenchmarkDelegate):
  """Contains the logic to perform line draw start latency benchmarks."""

  scroll_distance = 10
  """Distance to move for each scroll (in mm)."""

  COMMANDS_DURATION = 7000
  """Duration of the full set of robot commands (in # of camera frames)."""

  CAMERA_FRAMERATE = 300
  """Framerate at which to record, in frames per second."""

  finger_min_speed = 0.2
  """Minimum speed for the robot finger to be considered moving."""

  def InitializeProcessor(self, processor, video_reader, screen_calibration):
    processor.EnableDetectors(line_draw=True, finger_location=True, led=True)

  def ExecuteOnSubject(self, subject):
    """Executes line draw start benchmark and records the interaction.

    :param BenchmarkSubject subject
    """
    subject.camera.Prepare(self.COMMANDS_DURATION, self.CAMERA_FRAMERATE,
                           subject.exposure)

    # Height of finger down and up state in cm
    down = -1.0
    up = 10.0

    # Scroll by scroll_distance, lift finger, then scroll again until
    # the end of the page is reached.
    subject.TapOnTestPlane(0.0, blocking=True)
    subject.camera.Trigger()
    for i in range(int(subject.top + self.scroll_distance), int(subject.bottom),
                   self.scroll_distance):
      subject.MoveOnTestPlane(float(i - self.scroll_distance), down)
      subject.MoveOnTestPlane(float(i), down)
      subject.MoveOnTestPlane(float(i), up)
    return subject.camera.ReceiveVideo()

  def ProcessTrace(self, trace, measurements):
    for segmented_trace in trace.SegmentedByLED():

      # Find first line draw start in this segment
      line_draw = segmented_trace.Find(LineDrawEvent, 0, "after")
      if not line_draw:
        break

      # Search for first significant finger movement in this segment
      finger_moved_time = None
      for i, speed in enumerate(segmented_trace.finger_speed):
        if speed > self.finger_min_speed:
          finger_moved_time = i
          break
      if finger_moved_time is None:
        break

      finger_moved_event = segmented_trace.Find(FingerEvent, finger_moved_time)
      measurements.AddDrawEventMeasurement("LineDrawStart", finger_moved_event,
                                           line_draw)

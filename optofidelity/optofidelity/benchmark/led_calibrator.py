# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from safetynet import TypecheckMeta
import numpy as np

from optofidelity.detection import (LEDEvent, ScreenCalibration, Trace,
                                    VideoProcessor)
from optofidelity.system import BenchmarkSubject

class LEDCalibrator(object):
  """Service to calibrate the delay between two LEDs.

  This service is used to calibrate the robot finger LED. The robot is tapping
  a calibration plate that lights up as soon as the plate is grounded by the
  robot finger.
  """
  __metaclass__ = TypecheckMeta

  PER_TAP_DURATION = 1000
  """Duration in ms it takes the robot to complete a tap."""

  NUM_TAPS = 5
  """Number of taps to execute for calibration."""

  def __init__(self, video_processor):
    """
    :type video_processor: VideoProcessor
    """
    self._video_processor = video_processor

  def CalibrateLED(self, subject, debug):
    """
    :param BenchmarkSubject subject: Subject identifying the led calibration
           plate.
    :param bool debug: Shows debug information
    """
    video_reader = self._ExecuteCalibration(subject)
    screen_calibration = ScreenCalibration.CreateIdentity(
        video_reader.frame_shape)
    trace = self._video_processor.ProcessVideo(video_reader, screen_calibration,
                                               [])
    return self._ProcessTrace(trace, video_reader.ms_per_frame, debug)

  def _ExecuteCalibration(self, subject):
    """Instruct robot to execute calibration on subject.

    :type subject: BenchmarkSubject
    """
    center = (subject.width / 2.0, subject.height / 2.0)
    subject.camera.Prepare(self.PER_TAP_DURATION * self.NUM_TAPS)
    subject.Move(*center, z=10.0, blocking=True)
    subject.camera.Trigger()
    subject.Tap(*center, count=self.NUM_TAPS)
    return subject.camera.ReceiveVideo()

  def _ProcessTrace(self, trace, ms_per_frame, debug):
    """Calculate latency from trace.

    :type trace: Trace
    :type ms_per_frame: float
    :type debug: bool
    :rtype Tuple[float, float]
    """
    if debug:
      print trace

    down_delays = []
    up_delays = []
    for i in range(0, len(trace), 2):
      if i + 1 >= len(trace):
        break

      first, second = trace[i:(i+2)]
      assert first.state == second.state

      delay = second.time - first.time
      if first.state == LEDEvent.STATE_ON:
        down_delays.append(delay)
      else:
        up_delays.append(delay)

    if debug:
      print down_delays
      print up_delays

    down_delay = np.mean(np.asarray(down_delays))
    up_delay = np.mean(np.asarray(up_delays))
    return down_delay, up_delay

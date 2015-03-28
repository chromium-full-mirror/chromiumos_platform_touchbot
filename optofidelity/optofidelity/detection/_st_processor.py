# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import sys

from safetynet import List, Optional
import numpy as np

from optofidelity.videoproc import VideoReader

from ._calibrated_frame import CalibratedFrame
from ._detector import DetectorDebugger
from ._finger_detector import FingerDetector
from ._led_detector import LEDDetector
from ._line_detector import LineDetector
from ._screen_draw_detector import ScreenDrawDetector
from .processor import VideoProcessor
from .screen_calibration import ScreenCalibration
from .trace import Trace

_log = logging.getLogger(__name__)


class SinglethreadedVideoProcessor(VideoProcessor):
  """Processes video and accumulates generated events."""

  def __init__(self, screen_calibration):
    """
    :param Optional[ScreenCalibration] screen_calibration
    """
    self._screen_calibration = screen_calibration
    self._detectors = []

  @property
  def screen_calibration(self):
    return self._screen_calibration

  def EnableDetectors(self, line_draw=False, led=False, finger_location=False,
                      screen_draw=False):
    if line_draw:
      self._AddDetector(LineDetector())
    if led:
      self._AddDetector(LEDDetector())
    if finger_location:
      self._AddDetector(FingerDetector())
    if screen_draw:
      self._AddDetector(ScreenDrawDetector())

  def ProcessVideo(self, video_reader, debug_flags, print_progress):
    all_events = []
    prev_frame = None
    for i, frame in video_reader.Frames():
      msg = "Processing frame %d/%d" % (i + 1, video_reader.num_frames)
      _log.debug(msg)
      if print_progress:
        sys.stdout.write("\r" + msg)
        sys.stdout.flush()

      events = self._ProcessFrame(i, frame, prev_frame, debug_flags,
                                  video_reader)
      all_events.extend(events)
      prev_frame = frame

    if print_progress:
      print
    return Trace(all_events)

  def ProcessFrame(self, frame_index, frame, prev_frame, debug_flags):
    return self._ProcessFrame(frame_index, frame, prev_frame, debug_flags,
                              None)

  def _ProcessFrame(self, frame_index, frame, prev_frame, debug_flags,
                    video_reader):
    """Process a single frame.

    :param int frame_index
    :param np.ndarray frame
    :param Optional[np.ndarray] prev_frame
    :param List[str] debug_flags
    :param Optional[VideoReader] video_reader
    :returns List[Event]
    """
    calib_frame = CalibratedFrame(frame, prev_frame, self._screen_calibration,
                                  frame_index)
    debugger = None
    all_events = []
    for detector in self._detectors:
      use_debugger = detector.NAME in debug_flags or "all" in debug_flags
      if use_debugger and not debugger:
        debugger = DetectorDebugger(self._screen_calibration, debug_flags)

      detector_debugger = debugger if use_debugger else None
      preprocessed_data = detector.Preprocess(calib_frame, detector_debugger)
      events = detector.GenerateEvents(preprocessed_data, frame_index,
                                       detector_debugger)
      all_events.extend(events)

    if debugger:
      if video_reader:
        debugger.DisplayDebugVideo(calib_frame, video_reader)
      else:
        debugger.DisplayDebugFrame(calib_frame)

    return all_events

  def _AddDetector(self, detector):
    self._detectors.append(detector)

# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import sys

from safetynet import List, Optional
import cv2
import numpy as np
import skimage

from optofidelity.videoproc import InteractiveVideoViewer, VideoReader

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

  def __init__(self, debug_video_file=None):
    self._detector_types = []
    self._debug_video_file = debug_video_file

  @classmethod
  def FromConfig(cls, parameters, children):
    return cls(parameters.get("debug-video"))

  def EnableDetectors(self, line_draw=False, led=False, finger_location=False,
                      screen_draw=False):
    self._detector_types = []
    if line_draw:
      self._AddDetector(LineDetector)
    if led:
      self._AddDetector(LEDDetector)
    if finger_location:
      self._AddDetector(FingerDetector)
    if screen_draw:
      self._AddDetector(ScreenDrawDetector)

  def _InitDetectors(self):
    self._detectors = [dtype() for dtype in self._detector_types]

  def ProcessVideo(self, video_reader, screen_calibration, debug_flags):
    self._InitDetectors()
    all_events = []
    prev_frame = None
    viewer = None
    debug_video = None

    if "viewer" in debug_flags:
      viewer = InteractiveVideoViewer()
      generator = viewer.YieldFrames(video_reader)
    else:
      generator = video_reader.Frames()

    if self._debug_video_file is not None:
      debug_video = cv2.VideoWriter(self._debug_video_file,
                                    cv2.cv.CV_FOURCC(*"mp4v"),
                                    30, video_reader.frame_shape)

    for i, frame in generator:
      msg = "Processing frame %d/%d" % (i + 1, video_reader.num_frames)
      _log.debug(msg)
      sys.stdout.write("\r" + msg)
      sys.stdout.flush()

      events, debug_frame = self._ProcessFrame(i, frame, prev_frame, screen_calibration,
                                               debug_flags)
      all_events.extend(events)
      if debug_frame is not None:
        if viewer is not None:
          viewer.DisplayFrame(debug_frame)
        if debug_video is not None:
          debug_frame = skimage.img_as_ubyte(debug_frame)
          debug_video.write(debug_frame)
      prev_frame = frame

    if debug_video is not None:
      debug_video.release()

    print
    return Trace(all_events, video_reader.ms_per_frame)

  def ProcessFrame(self, frame, prev_frame, screen_calibration, debug_flags):
    self._InitDetectors()
    events, debug_frame =  self._ProcessFrame(0, frame, prev_frame,
                                              screen_calibration, debug_flags)
    return events

  def _ProcessFrame(self, frame_index, frame, prev_frame, screen_calibration,
                    debug_flags):
    """Process a single frame.

    :type frame_index: int
    :type frame: np.ndarray
    :type prev_frame: Optional[np.ndarray]
    :type screen_calibration: ScreenCalibration
    :type debug_flags: List[str]
    :rtype Tuple[List[Event], Optional[np.ndarray]]
    """
    calib_frame = CalibratedFrame(frame, prev_frame, screen_calibration,
                                  frame_index)
    debugger = None
    if "viewer" in debug_flags:
      debugger = DetectorDebugger(screen_calibration, debug_flags)

    all_events = []
    for detector in self._detectors:
      use_debugger = detector.NAME in debug_flags or "all" in debug_flags
      detector_debugger = debugger if use_debugger else None
      preprocessed_data = detector.Preprocess(calib_frame, detector_debugger)
      events = detector.GenerateEvents(preprocessed_data, frame_index,
                                       detector_debugger)
      all_events.extend(events)

    if debugger:
      return all_events, debugger.ComposeDebugFrame(calib_frame)
    return all_events, None

  def _AddDetector(self, detector):
    self._detector_types.append(detector)

  def CreateScreenCalibration(self, video_reader):
    return ScreenCalibration.FromScreenFlashVideo(video_reader)

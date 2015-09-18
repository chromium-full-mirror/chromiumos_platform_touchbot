# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import sys

from safetynet import Any, Dict, List, Optional
import cv2
import numpy as np
import skimage

from optofidelity.videoproc import InteractiveVideoViewer

from ._calibrated_frame import CalibratedFrame
from ._detector import DetectorDebugger
from .processor import VideoProcessor
from .screen_calibration import ScreenCalibration
from .trace import Trace

_log = logging.getLogger(__name__)


class SinglethreadedVideoProcessor(VideoProcessor):
  """Processes video and accumulates generated events."""

  def __init__(self, debug_video_file=None):
    self._detectors = []
    self._debug_video_file = debug_video_file

  @classmethod
  def FromConfig(cls, parameters, children):
    return cls(parameters.get("debug-video"))

  def InitializeDetectors(self, *detectors):
    if not len(detectors):
      raise ValueError("No detectors specified.")
    self._detectors = detectors

  def ProcessVideo(self, video_reader, screen_calibration, debug_flags):
    if not len(self._detectors):
      raise Exception("InitializeDetectors has to be called first.")
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

    data_map = dict()
    for i, frame in generator:
      msg = "Processing frame %d/%d" % (i + 1, video_reader.num_frames)
      _log.debug(msg)
      sys.stdout.write("\r" + msg)
      sys.stdout.flush()

      calib_frame = CalibratedFrame(frame, prev_frame, screen_calibration, i)
      debugger = None
      if "viewer" in debug_flags:
        debugger = DetectorDebugger(screen_calibration, debug_flags)
      preprocessed_data = self._Preprocess(calib_frame, debugger,
                                           debug_flags)
      data_map[i] = preprocessed_data

      # Process debug view
      if debugger is not None:
        debug_frame = debugger.ComposeDebugFrame(calib_frame)
        if viewer is not None:
          viewer.DisplayFrame(debug_frame)
        if debug_video is not None:
          debug_frame = skimage.img_as_ubyte(debug_frame)
          debug_video.write(debug_frame)
      prev_frame = frame

    if debug_video is not None:
      debug_video.release()

    events = self._GenerateEvents(data_map)

    self._detectors = []
    print
    return Trace(events, video_reader.ms_per_frame)

  def _Preprocess(self, calib_frame, debugger, debug_flags):
    """Preprocess a single calibrated frame.

    :param CalibratedFrame calib_frame
    :returns Dict[str, Any]
    """
    preprocessed_data = {}
    for detector in self._detectors:
      use_debugger = detector.NAME in debug_flags or "all" in debug_flags
      detector_debugger = debugger if use_debugger else None

      data = detector.Preprocess(calib_frame, detector_debugger)
      preprocessed_data[detector.NAME] = data
    return preprocessed_data

  def _GenerateEvents(self, data_map):
    """ Generate events from dictionary of preprocessed data

    :param int frame_index
    """
    detector_data_map = {detector.NAME: list() for detector in self._detectors}
    last_frame = max(data_map.keys())
    for i in range(last_frame + 1):
      data = data_map.get(i, dict())
      for detector in self._detectors:
        detector_data = data.get(detector.NAME, None)
        detector_data_map[detector.NAME].append(detector_data)

    all_events = []
    for detector in self._detectors:
      detector_data = detector_data_map[detector.NAME]
      events = detector.GenerateEvents(detector_data)
      all_events.extend(events)
    return sorted(all_events, key=lambda e:e.time)


  def _AddDetector(self, detector):
    self._detector_types.append(detector)

  def CreateScreenCalibration(self, video_reader):
    return ScreenCalibration.FromScreenFlashVideo(video_reader)

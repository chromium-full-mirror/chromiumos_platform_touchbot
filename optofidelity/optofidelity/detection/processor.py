# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Abstract base class and factory method for the processor."""

from abc import abstractmethod, abstractproperty

from safetynet import InterfaceMeta, List
import numpy as np

from optofidelity.videoproc import VideoReader

from .events import Event
from .screen_calibration import ScreenCalibration
from .trace import Trace


class VideoProcessor(object):
  """A video processor is responsible processing video into a steam of events.

  The video processor detects events in the video stream. Which kind of events
  are detected can be specified by calling EnableDetectors.
  It can then be either used by calling ProcessFrame for each video frame to
  be processed, or by passing a VideoReader to ProcessVideo.

  Both methods accept a list of debug_flags with the following options:
     - video: show debug video in camera space
     - normalized: show normalized video instead
     - delta: show inter-frame delta instead
     - line: show debug information from LineDetector
     - led: show debug information from LEDDetector
     - finger: show debug information from FingerDetector
     - screen_draw: show debug information from ScreenDrawDetector
  """

  __metaclass__ = InterfaceMeta

  @abstractproperty
  def screen_calibration(self):
    """:returns ScreenCalibration"""

  @abstractmethod
  def EnableDetectors(self, line_draw=False, led=False, finger_location=False,
                      screen_draw=False):
    """Enable selected detectors.

    :param bool line_draw: Enables line draw detection.
    :param bool led: Enables LED flash detection.
    :param bool finger_location: Enables detection of finger location.
    :param bool screen_draw: Enables detection of full screen draws.
    """

  @abstractmethod
  def ProcessVideo(self, video_reader, debug_flags, print_progress):
    """Process video and return list of detected events.

    :param VideoReader video_reader: Video to process
    :param List[str] debug_flags: List of debug flags
    :returns Trace: List of events generated
    """

  @abstractmethod
  def ProcessFrame(self, frame_index, frame, prev_frame, debug_flags):
    """Process single frame and return list of detected events.

    Note that this method is stateful and requires you to pass in frames in the
    right order.

    :param np.ndarray frame: Frame to process
    :param List[str] debug_flags: List of debug flags
    :returns List[Event]: List of events generated
    """


def CreateVideoProcessor(screen_calibration, multithreaded=False):
  """Factory to create a single or multitthreaded video processor.

  :param ScreenCalibration screen_calibration
  :param bool multitthreaded
  :returns VideoProcessor
  """
  if multithreaded:
    from optofidelity.detection._mt_processor import MultithreadedVideoProcessor
    return MultithreadedVideoProcessor(screen_calibration)
  else:
    from optofidelity.detection._st_processor import SinglethreadedVideoProcessor
    return SinglethreadedVideoProcessor(screen_calibration)

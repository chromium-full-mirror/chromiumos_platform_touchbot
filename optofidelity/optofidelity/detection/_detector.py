# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.from abc import abstractmethod
from abc import abstractmethod

from safetynet import InterfaceMeta, List, Optional
import skimage.color as color

from optofidelity.videoproc import Canvas

from ._calibrated_frame import CalibratedFrame
from .events import Event
from .screen_calibration import ScreenCalibration


class DetectorDebugger(object):
  """Visual debugging tools for Detectors.

  This class provides two canvases, one in screen space and one in camera space,
  and allows these to be overlaid to the current frame and displayed either
  in a detailed debug window for single frames, or as a video.
  """

  def __init__(self, screen_calibration, debug_flags):
    """
    This class supports the following three debug debug_flags:
    - video: Enables on video debugging and per default show camera space video
             with debugging overlays.
    - normalized: Shows normalized screen space view instead.
    - delta: Shows inter-frame camera space view instead.

    :param ScreenCalibration screen_space_normalized.
    :param Iterable[str] debug_flags: list of debug flags.
    """
    self.screen_space_canvas = Canvas.FromShape(
        screen_calibration.screen_space_shape)
    self.camera_space_canvas = Canvas.FromShape(
        screen_calibration.camera_space_shape)
    self.screen_calibration = screen_calibration
    self._debug_flags = debug_flags

  def ComposeDebugFrame(self, calib_frame):
    """Compose image showing calib_frame with canvases overlaid

    :type calib_frame: CalibratedFrame
    :returns np.ndarray: The composed RGB image
    """
    if "delta" in self._debug_flags:
      if "normalized" in self._debug_flags:
        debug_frame = self.ComposeScreenSpace(
            0.5 + calib_frame.screen_space_delta)
      else:
        debug_frame = self.ComposeCameraSpace(
            0.5 + calib_frame.camera_space_delta)
    elif "normalized" in self._debug_flags:
      debug_frame = self.ComposeScreenSpace(calib_frame.screen_space_normalized)
    elif "stabilization" in self._debug_flags:
      delta = (0.5 + self.screen_calibration.black_frame
                   - calib_frame.camera_space_frame)
      debug_frame = self.ComposeCameraSpace(delta)
    else:
      debug_frame = self.ComposeCameraSpace(calib_frame.camera_space_frame)
    return debug_frame

  def ComposeScreenSpace(self, frame):
    """Compose a color image from screen space frame, overlaying debug information.

    :param np.ndarray frame: Has to be a grayscale image in screen space.
    :returns np.ndarray: An RGB image in screen space.
    """
    camera_space_transformed = self.camera_space_canvas.Transformed(
        self.screen_calibration.CameraToScreenSpace)
    debug_frame = color.gray2rgb(frame)
    debug_frame = camera_space_transformed.BlendWithImage(debug_frame)
    debug_frame = self.screen_space_canvas.BlendWithImage(debug_frame)
    return debug_frame

  def ComposeCameraSpace(self, frame):
    """Compose a color image from frame, overlaying debug information.

    :param np.ndarray frame: Has to be a grayscale image in screen space.
    :returns np.ndarray: An RGB image in screen space.
    """
    self.camera_space_canvas.DrawMask(Canvas.GREEN,
                                      self.screen_calibration.shape.contour)
    screen_space_transformed = self.screen_space_canvas.Transformed(
        self.screen_calibration.ScreenToCameraSpace)
    debug_frame = color.gray2rgb(frame)
    debug_frame = screen_space_transformed.BlendWithImage(debug_frame)
    debug_frame = self.camera_space_canvas.BlendWithImage(debug_frame)
    return debug_frame


class Detector(object):
  """Base class for detectors that extract event traces from videos."""
  __metaclass__ = InterfaceMeta

  @abstractmethod
  def Preprocess(self, calib_frame, debugger):
    """Preprocessing step to process frame into more compact data.

    This method returns data to be passed to GenerateEvents. It is
    is stateless and can be called on any frames out of order (i.e. also in
    parallel processes)
    :param CalibratedFrame calib_frame
    :param Optional[DetectorDebugger] debugger
    """

  @abstractmethod
  def GenerateEvents(self, preprocessed_data, frame_index, debugger):
    """Perform detection on the preprocessed data and return events.

    This method has to be called in order, and should offload as much of the
    heavy processing to Preprocess as possible.
    :param CalibratedFrame calib_frame
    :param Optional[DetectorDebugger] debugger
    :returns List[Event]
    """

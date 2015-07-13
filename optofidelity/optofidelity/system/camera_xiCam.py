# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of the HighSpeedCamera class for the XiQ camera."""
try:
  import xiCam
except ImportError:
  xiCam = None
import logging
import numpy as np
import skimage
import threading

from optofidelity.videoproc import VideoReader
from .camera import HighSpeedCamera

_log = logging.getLogger(__name__)


class Thread(threading.Thread):
  def __init__(self, t, *args):
      threading.Thread.__init__(self, target=t, args=args)
      self.start()

class XiCamCamera(HighSpeedCamera):
  MAX_PTFRAMES = 2245
  DEF_FPS = 300
  DEF_EXP = 3200
  DEF_GAIN = 3.5
  def __init__(self, default_fps=None, exposure=None, gain=None):
    if xiCam is None:
      raise Exception('Must compile xiCam module before using camera.')
    self.default_fps = default_fps or self.DEF_FPS
    self.default_exp = exposure or self.DEF_EXP
    self.default_gain = gain or self.DEF_GAIN
    self._triggered = False
    self._prepared =  False
    self.last_frame_set = None
    self.trigger_lock = threading.Lock()

  def Prepare(self, duration, fps=None):
    self._handle = xiCam.initCam(self.default_fps, self.default_exp, self.default_gain)
    self._fps = fps or self.default_fps
    xiCam.setFPS(self._fps, self._handle)
    self._num_frames = duration * self._fps / 1000
    if self._num_frames > self.MAX_PTFRAMES:
      raise ValueError("Cannot record more than %d frames" % self.MAX_PTFRAMES)
    self._prepared = True
    self._triggered = False

  def _TriggerFrames(self):
    self._triggered = True
    with self.trigger_lock:
      self.last_frame_set = xiCam.trigger(self._num_frames, self._handle)

  def Trigger(self):
    if not self._prepared:
      raise Exception("Can't trigger without camera being prepared.")
    Thread(self._TriggerFrames)

  def ReceiveVideo(self):
    if not self._triggered:
      raise Exception("Camera needs to be triggered before receiving video.")
    with self.trigger_lock:
      return XiCamVideoReader(self.last_frame_set, self._num_frames, self._fps, self._handle)


class XiCamVideoReader(VideoReader):
  """Implementation of a VideoReader streaming from a XiQ camera.

  This class works as a fully functional VideoReader, streaming frames
  from an internal buffer of frame data.
  """
  IMG_IDX = 0
  MS_IDX = 2
  GPI_IDX = 3
  def __init__(self, frameSet, num_frames, fps, handle):
    self.frameSet = frameSet
    self.num_frames = num_frames
    self.fps = fps
    self.current_frame = 0
    self._handle = handle
    self._prefetch_enabled = False
    self.perf_enabled = False

  def _SeekTo(self, frame_index):
    if (frame_index >= self.num_frames): return False
    self.current_frame = frame_index
    return True

  def _Read(self):
    data = np.array(self.frameSet.getFrame(self.current_frame)[self.IMG_IDX], np.uint8)
    return skimage.img_as_float(data)

  def _ReadGPIO(self):
    level = self.frameSet.getFrame(self.current_frame)[self.GPI_IDX]

  def Close(self):
    pass

  def Prefetch(self, frame_index):
    pass

  def _ClearPrefetch(self):
    pass


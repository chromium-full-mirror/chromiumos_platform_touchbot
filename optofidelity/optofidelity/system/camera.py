# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Abstract base class for a high speed camera API."""

from abc import abstractmethod, abstractproperty
from safetynet import InterfaceMeta, Optional

from optofidelity.videoproc import VideoReader


class HighSpeedCamera(object):
  """Interface definition for High Speed Camera API."""
  __metaclass__ = InterfaceMeta

  def __init__(self, is_relative):
    self._is_relative = False

  @property
  def is_relative(self):
    return self._is_relative

  @abstractmethod
  def Prepare(self, duration, fps=None, exposure=None):
    """Prepare a recording of duration.

    :param int duration: Duration in ms to record.
    :param Optional[int] fps: How many frames per second to record.
    :param Optional[float] exposure: Exposure time in ms.
    """

  @abstractmethod
  def Trigger(self):
    """Trigger recording.

    This method will block until the recording is actually starting.
    """

  @abstractmethod
  def ReceiveVideo(self):
    """Receive the recorded video from the camera.

    Depending on the implementation, this might stream the video directly
    from the camera instead of copying the full video first.

    :returns VideoReader: A video reader instance to access the recorded video
    """

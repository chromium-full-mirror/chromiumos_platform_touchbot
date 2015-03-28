# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Fake implementation of the camera and robot backend classes."""

import logging

from optofidelity.videoproc import FakeVideoReader

from ._backend import DUTBackend, RobotBackend
from .camera import HighSpeedCamera

_log = logging.getLogger(__name__)


class FakeDUTBackend(DUTBackend):
  """Fake implementation of DUTBackend."""
  def __init__(self, name):
    self.name = name
    self._x, self._y, self._z = 0, 0, 0

  def DetectIcon(self, icon_file):
    _log.info("DetectIcon")
    return (1.0, 1.0)

  def DetectWords(self, words):
    _log.info("DetectIcon")
    return { word: (float(i) + 1.0, float(i) + 1.0)
            for i, word in enumerate(words) }

  def Tap(self, x, y, count=1):
    _log.info("Tap %.2f %.2f count=%d", x, y, count)
    self._x, self._y, self._z = x, y, 10

  def Move(self, x, y, z):
    _log.info("Move %.2f %.2f %.2f", x, y, z)
    self._x, self._y, self._z = x, y, z

  def Jump(self, x, y, z):
    _log.info("Jump %.2f %.2f", x, y)
    self._x, self._y, self._z = x, y, z

  def WaitForGesturesToFinish(self):
    pass

  @property
  def position(self):
    return (self._x, self._y, self._z)

  @property
  def width(self):
    return 500

  @property
  def height(self):
    return 100

  @property
  def orientation(self):
    return 90


class FakeRobotBackend(RobotBackend):
  """Fake implementation of RobotBackend."""
  def Reset(self):
    _log.info("Reset")

  def GetDUTBackend(self, name):
    return FakeDUTBackend(name)


class FakeHighSpeedCamera(HighSpeedCamera):
  """Fake implementation of a HighSpeedCamera."""
  def __init__(self):
    self.num_frames = None
    self.fps = 300
    self.frame_size = (1280, 720)

  def Prepare(self, duration, fps=None):
    self.fps = fps or self.fps
    self.num_frames = duration * self.fps / 1000
    _log.info("Prepare Camera")

  def Trigger(self):
    _log.info("Trigger Camera")

  def ReceiveVideo(self):
    return FakeVideoReader(self.num_frames, self.frame_size, self.fps)

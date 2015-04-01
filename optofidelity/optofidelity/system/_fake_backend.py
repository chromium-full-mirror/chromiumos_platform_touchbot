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
    self._commands = []
    self._width = 500
    self._height = 100
    self._orientation = 90
    self._detect_icon_rval = (1.0, 1.0)
    self._detect_words_rval = (1.0, 1.0)

  def DetectIcon(self, icon_file):
    self._LogCommand("DetectIcon", icon_file)
    return self._detect_icon_rval

  def DetectWords(self, words):
    self._LogCommand("DetectWords", words)
    return { word: self._detect_words_rval for word in words }

  def Tap(self, x, y, count=1):
    self._LogCommand("Tap", (x, y, count))
    self._x, self._y, self._z = x, y, 10

  def Move(self, x, y, z):
    self._LogCommand("Move", (x, y, z))
    self._x, self._y, self._z = x, y, z

  def Jump(self, x, y, z):
    self._LogCommand("Jump", (x, y, z))
    self._x, self._y, self._z = x, y, z

  def WaitForGesturesToFinish(self):
    pass

  @property
  def position(self):
    return (self._x, self._y, self._z)

  @property
  def width(self):
    return self._width

  @property
  def height(self):
    return self._height

  @property
  def orientation(self):
    return self._orientation

  def _LogCommand(self, command, args):
    _log.info("%s(%s)", command, ", ".join(str(args)))
    self._commands.append((command, args))


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

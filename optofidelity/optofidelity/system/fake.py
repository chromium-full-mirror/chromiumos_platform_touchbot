# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import logging

from optofidelity.videoproc import FakeVideoReader

from .backend import DUTBackend, RobotBackend
from .camera import HighSpeedCamera
from .navigator import BaseNavigator
from .subject import BenchmarkSubject
from .system import BenchmarkSystem

_log = logging.getLogger(__name__)


class FakeDUTBackend(DUTBackend):
  """Fake implementation of DUTBackend."""
  def __init__(self, name):
    self.name = name
    self._x, self._y, self._z = 0, 0, 0
    self._commands = []
    self._width = 500.0
    self._height = 100.0
    self._orientation = 90.0
    self._detect_icon_rval = (1.0, 1.0)
    self._detect_words_rval = (1.0, 1.0)

  def DetectIcon(self, icon_file):
    self._LogCommand("DetectIcon", (icon_file,))
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
    _log.info("%s(%s)", command, ", ".join([str(arg) for arg in args]))
    self._commands.append((command, args))


class FakeRobotBackend(RobotBackend):
  """Fake implementation of RobotBackend."""
  @classmethod
  def FromConfig(cls, attributes, children):
    return cls()

  def Reset(self):
    _log.info("Reset")

  def GetDUTBackend(self, name):
    return FakeDUTBackend(name)


class FakeHighSpeedCamera(HighSpeedCamera):
  """Fake implementation of a HighSpeedCamera."""
  def __init__(self, is_relative=False):
    super(FakeHighSpeedCamera, self).__init__(is_relative)
    self.num_frames = None
    self.fps = 300
    self.frame_size = (1280, 720)
    self.fake_videos = dict()
    self.fake_video = None

  @classmethod
  def FromConfig(cls, attributes, children):
    return cls()

  def Prepare(self, duration, fps=None, exposure=None):
    self.fps = fps or self.fps
    self.num_frames = duration * self.fps / 1000
    _log.info("Prepare Camera")

  def Trigger(self):
    _log.info("Trigger Camera")

  def ReceiveVideo(self):
    if self.fake_video:
      return self.fake_video
    return FakeVideoReader(self.num_frames, self.frame_size, self.fps)


class FakeNavigator(BaseNavigator):
  def __init__(self):
    super(FakeNavigator, self).__init__()
    self._activites = ["fake", "calibration"]

  def HasActivity(self, activity_name):
    return activity_name in self._activites


class FakeBenchmarkSystem(BenchmarkSystem):
  """Fake implementation of BenchmarkSystem.

  This class does not require a connection to an optofidelity robot.
  It replaces the Camera and Backend instances with fake versions that log
  all actions.
  If no config file is specified, it will create a single fake subject that
  is available at self.fake_subject.
  """
  def __init__(self):
    super(FakeBenchmarkSystem, self).__init__(FakeRobotBackend(),
                                              FakeHighSpeedCamera())
    self.fake_subject = self._CreateFakeSubject()

  def _CreateFakeSubject(self):
    dut_backend = self.backend.GetDUTBackend("fake_dut")
    subject = BenchmarkSubject("fake_dut/fake_subject", dut_backend,
                               self.camera)
    subject.navigator = FakeNavigator()
    return subject

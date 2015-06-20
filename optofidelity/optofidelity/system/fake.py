# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import logging

from optofidelity.videoproc import FakeVideoReader

from .backend import DUTBackend, RobotBackend
from .camera import HighSpeedCamera
from .navigator import Navigator
from .subject import BenchmarkSubject, Updater
from .system import BenchmarkSystem

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
  def __init__(self):
    self.num_frames = None
    self.fps = 300
    self.frame_size = (1280, 720)
    self.fake_videos = dict()
    self.fake_video = None

  @classmethod
  def FromConfig(cls, attributes, children):
    return cls()

  def Prepare(self, duration, fps=None):
    self.fps = fps or self.fps
    self.num_frames = duration * self.fps / 1000
    _log.info("Prepare Camera")

  def Trigger(self):
    _log.info("Trigger Camera")

  def ReceiveVideo(self):
    if self.fake_video:
      return self.fake_video
    return FakeVideoReader(self.num_frames, self.frame_size, self.fps)


class FakeUpdater(Updater):
  """Updater that returns a constant version.

  This updater is to be used for devices and subjects that require manual
  updating.
  """
  def __init__(self):
    self._available_versions = []
    self._installed_version = None

  @classmethod
  def FromConfig(cls, attributes, children, dut_backend):
    return cls()

  def GetVersionUID(self, version):
    return 0

  @property
  def available_versions(self):
    return self._available_versions

  @property
  def installed_version(self):
    return self._installed_version

  def Install(self, version):
    self._installed_version = version

  def Uninstall(self):
    self._installed_version = None


class FakeBenchmarkSubject(BenchmarkSubject):
  def OpenActivity(self, activity_name):
    self.camera.fake_video = self.camera.fake_videos.get(activity_name, None)
    return super(FakeBenchmarkSubject, self).OpenActivity(activity_name)

  @property
  def fake_videos(self):
    return self.camera.fake_videos

  @fake_videos.setter
  def set_fake_videos(self, value):
    self.camera.fake_videos = value


class FakeNavigator(Navigator):
  def __init__(self):
    self._activites = ["fake"]

  @property
  def activities(self):
    return self._activites

  @property
  def state(self):
    return {}

  def AddActivity(self, activity_name, parameters):
    self._activites.append(activity_name)

  def Open(self, safe):
    pass

  def Close(self):
    pass

  def Reset(self):
    pass

  def OpenActivity(self, activity_name):
    pass

  def CloseActivity(self):
    pass


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
    self.subjects = defaultdict(self._CreateFakeSubject, self.subjects)
    self.fake_subject = None

    self.fake_subject = self._CreateFakeSubject()
    self.subjects[self.fake_subject.name] = self.fake_subject

  def _CreateFakeSubject(self):
    dut_backend = self.backend.GetDUTBackend("fake_dut")
    nav_backend = FakeNavigator()
    nav_backend.AddActivity("Tap", dict(text="Tap"))
    nav_backend.AddActivity("Scroll", dict(text="Scroll"))
    nav_backend.AddActivity("Move", dict(text="Move"))
    nav_backend.AddActivity("Flash", dict(text="Flash"))
    updater = FakeUpdater()
    return FakeBenchmarkSubject("fake_dut", "fake_subject", dut_backend,
                                nav_backend, updater, self.camera, (0.0, 0.0))

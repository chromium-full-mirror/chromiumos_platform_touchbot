# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import logging

from optofidelity.videoproc import FakeVideoReader

from ._fake_backend import FakeRobotBackend
from ._navigators import RobotNavigator
from .camera import HighSpeedCamera
from .subject import BenchmarkSubject, Updater
from .system import BenchmarkSystem

_log = logging.getLogger(__name__)


class FakeHighSpeedCamera(HighSpeedCamera):
  """Fake implementation of a HighSpeedCamera."""
  def __init__(self):
    self.num_frames = None
    self.fps = 300
    self.frame_size = (1280, 720)
    self.fake_videos = dict()
    self.fake_video = None

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

  def GetVersionUID(self, version):
    return 0

  @property
  def available_versions(self):
    return self._available_versions

  @property
  def installed_version(self):
    return self._installed_version

  def Install(self, version, print_progress=False):
    self._installed_version = version

  def Uninstall(self, print_progress=False):
    self._installed_version = None


class FakeBenchmarkSubject(BenchmarkSubject):
  def OpenPage(self, page_name):
    self.camera.fake_video = self.camera.fake_videos.get(page_name, None)
    return super(FakeBenchmarkSubject, self).OpenPage(page_name)

  @property
  def fake_videos(self):
    return self.camera.fake_videos

  @fake_videos.setter
  def set_fake_videos(self, value):
    self.camera.fake_videos = value


class FakeBenchmarkSystem(BenchmarkSystem):
  """Fake implementation of BenchmarkSystem.

  This class does not require a connection to an optofidelity robot.
  It replaces the Camera and Backend instances with fake versions that log
  all actions.
  If no config file is specified, it will create a single fake subject that
  is available at self.fake_subject.
  """
  def __init__(self, config_file=None):
    super(FakeBenchmarkSystem, self).__init__(config_file)
    if not self._backend:
      self._backend = self._CreateBackend(dict())
    if not self.camera:
      self.camera = self._CreateCamera(dict())

    self.subjects = defaultdict(self._CreateFakeSubject, self.subjects)
    self.fake_subject = None

    if not config_file:
      self.fake_subject = self._CreateFakeSubject()
      self.subjects[self.fake_subject.name] = self.fake_subject

  def _CreateCamera(self, attrib):
    return FakeHighSpeedCamera()

  def _CreateBackend(self, attrib):
    return FakeRobotBackend()

  def _CreateUpdater(self, updater_attrib, subject_attrib, dut_attrib):
    return FakeUpdater()

  def _CreateNavigator(self, nav_attrib, subject_attrib, dut_attrib,
                       dut_backend):
    return RobotNavigator(dut_backend, nav_attrib["icon"])

  def _CreateFakeSubject(self):
    dut_backend = self._backend.GetDUTBackend("fake_dut")
    nav_backend = RobotNavigator(dut_backend, "dummy.shp")
    updater = FakeUpdater()
    return FakeBenchmarkSubject("fake_dut", "fake_subject", dut_backend,
                                nav_backend, updater, self.camera, (0.0, 0.0))

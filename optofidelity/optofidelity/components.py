# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from .benchmark import BenchmarkRunner
from .benchmark.fake import FakeBenchmarkRunner
from .detection import (MultithreadedVideoProcessor,
                        SinglethreadedVideoProcessor, VideoProcessor)
from .detection.fake import FakeVideoProcessor
from .orchestrator import Orchestrator
from .orchestrator.access import Access, CambrionixAccess, FakeAccess
from .orchestrator.dashboard import (ChromePerfDashboard, Dashboard,
                                     FakeDashboard, SpreadsheetDashboard)
from .orchestrator.subject_setup import (ADBSettingsSetup, FakeSubjectSetup,
                                         SubjectSetup)
from .orchestrator.updater import (AndroidUpdater, ChromeUpdater, FakeUpdater,
                                   ManualUpdater, Updater)
from .system import HighSpeedCamera, Navigator, RobotBackend
from .system.backend_tnt import TnTRobotBackend
from .system.camera_phantom import PhantomCamera
from .system.camera_xiCam import XiCamCamera
from .system.fake import FakeHighSpeedCamera, FakeRobotBackend
from .system.navigator import (FakeNavigator, ManualNavigator,
                               NativeADBNavigator, RobotNavigator,
                               WebADBNavigator)

COMPONENTS = {
  RobotBackend: {
    "tnt": TnTRobotBackend,
    "fake": FakeRobotBackend
  },
  HighSpeedCamera: {
    "phantom": PhantomCamera,
    "xicam": XiCamCamera,
    "fake": FakeHighSpeedCamera
  },
  Updater: {
    "chrome": ChromeUpdater,
    "android": AndroidUpdater,
    "manual": ManualUpdater,
    "fake": FakeUpdater
  },
  Navigator: {
    "robot": RobotNavigator,
    "web_adb": WebADBNavigator,
    "native_adb": NativeADBNavigator,
    "manual": ManualNavigator,
    "fake": FakeNavigator
  },
  VideoProcessor: {
    "multithreaded": MultithreadedVideoProcessor,
    "singlethreaded": SinglethreadedVideoProcessor,
    "default": MultithreadedVideoProcessor,
    "fake": FakeVideoProcessor
  },
  Dashboard: {
    "chromeperf": ChromePerfDashboard,
    "spreadsheet": SpreadsheetDashboard,
    "fake": FakeDashboard
  },
  Orchestrator: {
    "default": Orchestrator
  },
  BenchmarkRunner: {
    "default": BenchmarkRunner,
    "fake": FakeBenchmarkRunner
  },
  SubjectSetup: {
    "adb_settings": ADBSettingsSetup,
    "fake": FakeSubjectSetup
  },
  Access: {
    "default": FakeAccess,
    "cambrionix": CambrionixAccess,
    "fake": FakeAccess
  }
}

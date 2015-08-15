# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from .benchmark import BenchmarkRunner
from .detection import (MultithreadedVideoProcessor,
                        SinglethreadedVideoProcessor, VideoProcessor)
from .orchestrator import (ADBSettingsSetup,
                           AndroidUpdater, ChromePerfDashboard, ChromeUpdater,
                           Dashboard, FakeUpdater, ManualUpdater, Orchestrator,
                           OrchestratorSubject, SpreadsheetDashboard,
                           SubjectSetup, Updater)
from .system import HighSpeedCamera, Navigator, RobotBackend
from .system.backend_tnt import TnTRobotBackend
from .system.camera_phantom import PhantomCamera
from .system.camera_xiCam import XiCamCamera
from .system.fake import FakeHighSpeedCamera, FakeRobotBackend
from .system.navigator import (ManualNavigator, NativeADBNavigator,
                               RobotNavigator, WebADBNavigator)

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
    "manual": ManualNavigator
  },
  VideoProcessor: {
    "multithreaded": MultithreadedVideoProcessor,
    "singlethreaded": SinglethreadedVideoProcessor,
    "default": MultithreadedVideoProcessor
  },
  Dashboard: {
    "chromeperf": ChromePerfDashboard,
    "spreadsheet": SpreadsheetDashboard
  },
  Orchestrator: {
    "default": Orchestrator
  },
  BenchmarkRunner: {
    "default": BenchmarkRunner
  },
  SubjectSetup: {
    "adb_settings": ADBSettingsSetup
  },
}

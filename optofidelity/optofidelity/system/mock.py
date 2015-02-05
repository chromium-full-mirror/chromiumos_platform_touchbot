# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides mock implementations of the test system.

This allows testing of the test process without accessing the actual robot.
"""
from contracts import contract
import os.path

from optofidelity.system.app import TestApp
from optofidelity.system.calibration import LEDCalibration
from optofidelity.system.dut import DeviceUnderTest
from optofidelity.system.system import OptofidelityTestSystem
from optofidelity.videoproc.io import FileVideoReader


class MockApp(TestApp):
  """Mocks a TestApp while keeping track of which page we navigated to."""
  name = "mock_app"

  @contract(dut=DeviceUnderTest)
  def __init__(self, dut):
    TestApp.__init__(self, dut)
    self.current_page = None

  def DebugLog(self, msg, *args):
    args_str = ", ".join([str(a) for a in args])
    print "MOCK:", str(self), "%s(%s)" % (msg, args_str)

  def LocateButtons(self, force=False):
    self.DebugLog("LocateButtons")

  def EnterPage(self, page):
    self.DebugLog("EnterPage", page)
    self.current_page = page

  def ExitPage(self):
    self.DebugLog("ExitPage")
    self.current_page = None

  def Reset(self):
    self.DebugLog("Reset")
    self.current_page = None


class MockDUT(DeviceUnderTest):
  """Mocks a DUT while keeping track of which app we navigated to."""
  type_name = "mock_dut"

  @contract(name=str)
  def __init__(self, name):
    self.name = name
    self.apps = {}
    self.width = 100
    self.height = 200
    self.test_plane = 0
    self.current_app = None

  def DebugLog(self, msg, *args):
    args_str = ", ".join([str(a) for a in args])
    print "MOCK:", str(self), "%s(%s)" % (msg, args_str)

  def LocateButtons(self, force=True):
    self.DebugLog("LocateButtons")

  def Reset(self):
    self.DebugLog("Reset")
    self.current_app = None

  def EnterApp(self, app):
    self.DebugLog("EnterApp", app)

  def IsHome(self):
    return self.current_app is None

  def FindIcon(self, icon_file):
    raise NotImplementedError()

  def ReadText(self):
    raise NotImplementedError()

  def Tap(self, x, y, count=1, blocking=False):
    self.DebugLog("Tap", x, y, count)

  def Move(self, x, y, z, blocking=False):
    self.DebugLog("Move", x, y, z)

  def JumpToDevice(self, x=None, y=None):
    self.DebugLog("JumpToDevice", x, y)

  def Swipe(self, from_x, from_y, to_x, to_y, blocking=False):
    self.DebugLog("Swipe", from_x, from_y, to_x, to_y)

  def ClearScreen(self, blocking=False):
    self.DebugLog("ClearScreen")

  def Home(self):
    self.DebugLog("Home")
    self.current_app = None

  def ExitApp(self):
    self.DebugLog("ExitApp")
    self.current_app = None


class MockPhantom(object):
  """Mock class for phantom camera API.

  This class will return VideoReader instances reading from files instead of
  reading from the camera. The filename is determined by the page name the
  mock_app is at during the time of recording.
  E.g. if Record is invoked while mock_app is on the "move" page, the
  GetVideoReader() method will return a FileVideoReader pointing to
  data_path/move.avi.
  """
  def __init__(self, data_path, mock_app):
    self.data_path = data_path
    self.mock_app = mock_app
    self.recorded_page = None
    self.fps = 300

  def WaitUntilReady(self, cine_number=None):
    pass

  def Record(self, num_frames=None, cine_number=None):
    self.PrepareRecording(num_frames, cine_number)
    self.Trigger(cine_number)

  def Trigger(self, cine_number=None):
    print "MOCK: Phantom Trigger"
    self.recorded_page = self.mock_app.current_page
    pass

  def PrepareRecording(self, num_frames=None, cine_number=None):
    print "MOCK: Phantom PrepareRecording"
    pass

  def GetVideoReader(self, cine_number=None):
    video_name = self.recorded_page.lower()
    video_path = os.path.join(self.data_path, "%s.avi" % video_name)
    if not os.path.exists(video_path):
      raise Exception("Cannot fine video at %s" % video_path)
    return FileVideoReader(video_path)


class MockTestSystem(OptofidelityTestSystem):
  """A mock test system.

  This test system contains a single mock device with a single mock app and
  a mock phantom camera instance.
  This class can be used to test the testing process when there is not access
  to the actual touch robot.
  """
  is_mock = True

  def __init__(self, data_path):
    self.mock_dut = MockDUT("mock_dut")
    self.mock_app = MockApp(self.mock_dut)
    self.mock_dut.RegisterApp(self.mock_app)

    self.duts = {"mock_dut": self.mock_dut}
    self.calibration_dut = self.mock_dut

    self.camera = MockPhantom(data_path, self.mock_app)
    self.led_calibration = LEDCalibration()

  def SaveState(self, filename):
    pass

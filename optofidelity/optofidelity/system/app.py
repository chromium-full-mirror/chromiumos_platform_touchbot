# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contracts import contract
import time

from optofidelity.system.dut import DeviceUnderTest
from optofidelity.system.calibration import CameraCalibration
from optofidelity.videoproc import VideoWriter


class TestApp(object):
  """Provides functionality to navigate different pages of an app."""
  PAGE_TAP = "Tap"
  PAGE_MOVE = "Move"
  PAGE_CLICK = "Click"
  PAGE_FLASH = "Flash"
  TEST_APP_ICON = None

  @contract(dut=DeviceUnderTest, name=str)
  def __init__(self, dut, name):
    self.dut = dut
    self.name = name
    self.pages = {
        self.PAGE_TAP: (-1, -1),
        self.PAGE_MOVE: (-1, -1),
        self.PAGE_CLICK: (-1, -1),
        self.PAGE_FLASH: (-1, -1),
    }
    self.test_area = None
    self.button_coords = (-1, -1)

  def SaveCalibration(self, hdf5):
    hdf5.create_dataset("button_coords", data=self.button_coords)
    hdf5.create_group("pages")
    for page, coords in self.pages.items():
      hdf5["pages"].create_dataset(page, data=coords)
    self.test_area.Save(hdf5.create_group("screen"))

  def LoadCalibration(self, hdf5):
    button_coords = hdf5["button_coords"]
    self.button_coords = (button_coords[0], button_coords[1])

    for page in self.pages.keys():
      coords = hdf5["pages"][page]
      self.pages[page] = (coords[0], coords[1])
    self.test_area = CameraCalibration.Load(hdf5["screen"])

  def CalibrateButtons(self):
    for text, x, y in self.dut.ReadText():
      if text in self.pages:
        self.pages[text] = (x, y)

    for page, (x, y) in self.pages.items():
      if x < 0 or y < 0:
        raise DUTException(self.dut, "Cannot find button for page " + page)

  def CalibrateScreen(self, camera, dump=False):
    self.EnterPage(self.PAGE_FLASH)
    self.dut.ClearScreen()
    camera.Record(60)
    camera.WaitUntilReady()
    self.ExitPage()

    reader = camera.GetVideoReader()
    self.test_area = CameraCalibration()
    try:
      self.test_area.Detect(reader)
      if not dump:
        return
    except Exception, e:
      print "Error while detecting screen"
      print e
    # Dump screen info
    name = str(self).replace("/", "_") + "_Screen_" + str(int(time.time()))
    writer = VideoWriter(name + ".mov")
    writer.Write(reader)

  def Calibrate(self, x, y, camera, dump=False):
    self.button_coords = (x, y)
    self.CalibrateButtons()
    self.CalibrateScreen(camera, dump)

  def EnterPage(self, page):
    self.dut.Tap(*self.pages[page])

  def ExitPage(self):
    self.dut.Back()

  def Reset(self):
    self.dut.ExitApp()
    self.dut.EnterApp(self.name)

  def __str__(self):
    return "%s/%s" % (str(self.dut), self.name)


class ClankTestApp(TestApp):
  TEST_APP_ICON = "icons/clank_tests.shm"
  def __init__(self, dut):
    TestApp.__init__(self, dut, "Clank")


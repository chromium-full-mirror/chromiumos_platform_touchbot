# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contracts import contract
import time

from optofidelity.system.dut import DeviceUnderTest
from optofidelity.videoproc import VideoWriter


class TestApp(object):
  """Provides functionality to navigate different pages of an app."""
  PAGE_TAP = "Tap"
  PAGE_MOVE = "Move"
  PAGE_SCROLL = "Scroll"
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
        self.PAGE_SCROLL: (-1, -1),
    }
    self.button_coords = (-1, -1)

  def SaveCalibration(self, hdf5):
    hdf5.create_dataset("button_coords", data=self.button_coords)
    hdf5.create_group("pages")
    for page, coords in self.pages.items():
      hdf5["pages"].create_dataset(page, data=coords)

  def LoadCalibration(self, hdf5):
    button_coords = hdf5["button_coords"]
    self.button_coords = (button_coords[0], button_coords[1])

    for page in self.pages.keys():
      coords = hdf5["pages"][page]
      self.pages[page] = (coords[0], coords[1])

  def CalibrateButtons(self):
    for text, x, y in self.dut.ReadText():
      if text in self.pages:
        self.pages[text] = (x, y)

    for page, (x, y) in self.pages.items():
      if x < 0 or y < 0:
        raise DUTException(self.dut, "Cannot find button for page " + page)

  def Calibrate(self, x, y, camera, dump=False):
    self.button_coords = (x, y)
    self.CalibrateButtons()

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


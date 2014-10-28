# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contracts import contract
import time

from optofidelity.system.dut import DeviceUnderTest
from optofidelity.system.util import DUTException
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
    self.top = 0
    self.bottom = dut.height

  @property
  def height(self):
    return self.bottom - self.top

  def LocateButtons(self):
    for text, x, y in self.dut.ReadText():
      if text in self.pages:
        self.pages[text] = (x, y)

    for page, (x, y) in self.pages.items():
      if x < 0 or y < 0:
        raise DUTException(self.dut, "Cannot find button for page " + page)

  def EnterPage(self, page):
    self.dut.Tap(*self.pages[page])

  def ExitPage(self):
    self.dut.Back()

  def Reset(self):
    # Back once to exit any page we might be in.
    self.dut.Back()
    # Back another time to go back to the home screen.
    # If we are on the home screen already, this will just not do anything.
    self.dut.Back()
    # Go back into the app.
    self.dut.EnterApp(self.name)

  def Tap(self, y, count=1):
    x = self.dut.test_plane
    y += self.top
    self.dut.Tap(x, y, count)

  def Move(self, y, z):
    x = self.dut.test_plane
    y += self.top
    self.dut.Move(x, y, z)

  def __str__(self):
    return "%s/%s" % (str(self.dut), self.name)


class ClankTestApp(TestApp):
  TEST_APP_ICON = "icons/clank_tests.shm"
  def __init__(self, dut):
    TestApp.__init__(self, dut, "Clank")


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
  name = "undefined"

  @contract(dut=DeviceUnderTest)
  def __init__(self, dut):
    self.dut = dut
    self.pages = {
        self.PAGE_TAP: None,
        self.PAGE_MOVE: None,
        self.PAGE_CLICK: None,
        self.PAGE_FLASH: None,
        self.PAGE_SCROLL: None,
    }
    self.button_coords = None
    self.top = 0
    self.bottom = dut.height
    self.calibration = None

  @property
  def height(self):
    return self.bottom - self.top

  def ApplyMargin(self, margin):
    self.top += margin[0]
    self.bottom -= margin[1]

  def LocateButtons(self, force=False):
    if [coords for coords in self.pages.values() if not coords]:
      force = True

    if not force:
      return

    for text, x, y in self.dut.ReadText():
      if text in self.pages:
        self.pages[text] = (x, y)

    for page, coords in self.pages.items():
      if not coords:
        raise DUTException(self.dut, "Cannot find button for page " + page)

  def EnterPage(self, page):
    if not self.pages[page]:
      raise Exception("Did not locate button for page: %s" % page)
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
    self.dut.EnterApp(self)

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
  name = "clank"

  def __init__(self, dut):
    TestApp.__init__(self, dut)


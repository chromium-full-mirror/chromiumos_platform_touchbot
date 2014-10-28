# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contracts import contract

from optofidelity.system.util import DUTException
from optofidelity.tnt.TnTClient import TnTClient
from optofidelity.videoproc import VideoException, VideoWriter

class DeviceUnderTest(object):
  """Functionality to operate a DUT.

  It provides methods to navigate different apps on the device and execute
  basic movements and robot commands.
  """
  @contract(tnt=TnTClient, name=str)
  def __init__(self, tnt, name):
    self.name = name
    self.apps = {}
    self.client = tnt.dut(self.name)
    self.width = self.client.panel_width
    self.height = self.client.panel_height
    self.test_plane = 20

  def RegisterApp(self, app):
    self.apps[app.name] = app

  def LocateButtons(self):
    """Locate buttons for all apps."""
    for app in self.apps.values():
      x, y = self.FindIcon(app.TEST_APP_ICON)
      if x < 0 or y < 0:
        raise DUTException(self, "Cannot find icon " + app.TEST_APP_ICON)
      app.button_coords = (x, y)

  def Reset(self):
    self.ExitApp()
    self.ExitApp()

  def EnterApp(self, app_name):
    self.Tap(*self.apps[app_name].button_coords)

  def IsHome(self):
    for app in self.apps.values():
      x, y = self.FindIcon(app.TEST_APP_ICON)
      if x < 0 or y < 0:
        return False
    return True

  def FindIcon(self, icon_file):
    """Return the coordinates of the icon described by icon_file."""
    ret = self.client.find_objects(icon_file)
    if not ret["success"]:
      return -1, -1
    best_match = max(ret["results"], key=lambda r: r["score"])
    if best_match["score"] < 0.5:
      return -1, -1
    x = (best_match["topLeftX"] + best_match["bottomRightX"]) / 2.0
    y = (best_match["topLeftY"] + best_match["bottomRightY"]) / 2.0
    return x, y

  def ReadText(self):
    """Yield (text, x, y) tuples describing all text detected on the screen.

    For each detected piece of text a tuple is returned including the
    center coordinates of the text.
    """
    ret = self.client.read_text()
    if not ret["success"]:
      return
    for match in ret["results"]:
      x = (match["topLeftX"] + match["bottomRightX"]) / 2.0
      y = (match["topLeftY"] + match["bottomRightY"]) / 2.0
      yield match["text"], x, y

  def Tap(self, x, y, count=1):
    if count == 1:
      self.client.tap(x, y)
    else:
      self.client.multi_tap([[x, y]] * count)

  def Move(self, x, y, z):
    self.client.move(x, y, z)

  def Swipe(self, from_x, from_y, to_x, to_y):
    self.client.swipe(from_x, from_y, to_x, to_y)

  def ClearScreen(self):
    """Move finger to a position that does not obstruct the screen."""
    self.client.move(self.test_plane, -50, 50)

  def Back(self):
    raise NotImplementedError()

  def ExitApp(self):
    raise NotImplementedError()

  def __getitem__(self, key):
    if isinstance(key, int):
      return self.apps.values().__getitem__(key)
    else:
      return self.apps.__getitem__(key)

  def __str__(self):
    return self.name


class AndroidDUT(DeviceUnderTest):
  """Implementation of a DUT for Android devices."""
  def __init__(self, tnt, name):
    DeviceUnderTest.__init__(self, tnt, name)
    self.home_coords = (self.width / 2, self.height - 3)
    self.back_coords = (self.width / 2 - 20, self.height - 3)

  def Back(self):
    self.Tap(*self.back_coords)

  def ExitApp(self):
    self.Tap(*self.home_coords)


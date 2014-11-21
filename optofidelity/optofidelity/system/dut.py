# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contracts import contract

from optofidelity.system.util import DUTException
from optofidelity.tnt.TnTDUTClient import TnTDUTClient
from optofidelity.videoproc import VideoException, VideoWriter

class DeviceUnderTest(object):
  """Functionality to operate a DUT.

  It provides methods to navigate different apps on the device and execute
  basic movements and robot commands.
  """
  test_plane_margin = 10
  type_name = "undefined"

  @contract(client=TnTDUTClient, name=str)
  def __init__(self, client, name, flip):
    self.name = name
    self.apps = {}
    self.client = client
    self.width = self.client.panel_width
    self.height = self.client.panel_height
    if flip:
      self.test_plane = self.width - self.test_plane_margin
    else:
      self.test_plane = self.test_plane_margin

  def RegisterApp(self, app):
    self.apps[app.name] = app

  def LocateButtons(self, force=True):
    """Locate buttons for all apps."""
    if [app for app in self.apps.values() if not app.button_coords]:
      force = True

    if not force:
      return
    for app in self.apps.values():
      coords = self.FindIcon(app.TEST_APP_ICON)
      if not coords:
        raise DUTException(self, "Cannot find icon " + app.TEST_APP_ICON)
      app.button_coords = coords

  def Reset(self):
    self.ExitApp()
    self.ExitApp()

  def EnterApp(self, app):
    if not app.button_coords:
      raise Exception("Did not detect button location for app: %s" % (str(app)))
    self.Tap(*app.button_coords)

  def IsHome(self):
    for app in self.apps.values():
      if not self.FindIcon(app.TEST_APP_ICON):
        return False
    return True

  def FindIcon(self, icon_file):
    """Return the coordinates of the icon described by icon_file."""
    ret = self.client.find_objects(icon_file)
    if not ret["success"]:
      return None
    best_match = max(ret["results"], key=lambda r: r["score"])
    if best_match["score"] < 0.5:
      return None
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

  def Tap(self, x, y, count=1, blocking=False):
    self.JumpToDevice(x, y)
    if count == 1:
      self.client.tap(x, y)
    else:
      self.client.multi_tap([[x, y]] * count)
    if blocking:
      self.client.complete_requests()

  def Move(self, x, y, z, blocking=False):
    self.JumpToDevice(x, y)
    self.client.move(x, y, z)
    if blocking:
      self.client.complete_requests()

  def JumpToDevice(self, x=None, y=None):
    if x is None:
      x = self.width / 2
    if y is None:
      y = self.height / 2
    coords = self.client.get_position()
    if (coords.x < 0 or coords.x > self.width or
        coords.y < 0 or coords.y > self.height):
      self.client.jump(x, y, 10, height=40)

  def Swipe(self, from_x, from_y, to_x, to_y, blocking=False):
    self.JumpToDevice(from_x, from_y)
    self.client.swipe(from_x, from_y, to_x, to_y)
    if blocking:
      self.client.complete_requests()

  def ClearScreen(self, blocking=False):
    """Move finger to a position that does not obstruct the screen."""
    self.client.move(self.test_plane, -50, 50)
    if blocking:
      self.client.complete_requests()

  def Home(self):
    raise NotImplementedError()

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
  type_name = "android"

  def __init__(self, tnt, name, flip):
    DeviceUnderTest.__init__(self, tnt, name, flip)

    screen_min_width = 50
    button_distance_scale_factor = 0.75
    button_min_distance = 10
    button_max_distance = 20


    back_location = (button_min_distance + (self.width - screen_min_width) *
                     button_distance_scale_factor)
    back_location = min((back_location, button_max_distance))

    print self.width, back_location
    self.home_coords = (self.width / 2, self.height - 3)
    self.back_coords = (self.width / 2 - back_location, self.height - 3)

  def Back(self):
    self.Tap(*self.back_coords)

  def ExitApp(self):
    self.Tap(*self.home_coords)

  def Home(self):
    self.Tap(*self.home_coords)

class CalibrationDUT(DeviceUnderTest):
  """Represents the led calibration device."""
  type_name = "calibration"

  def __init__(self, tnt, name, flip):
    DeviceUnderTest.__init__(self, tnt, name, flip)

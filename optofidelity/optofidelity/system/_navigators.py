# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementations of the Navigator interface."""

import os

from safetynet import Any, Dict

from optofidelity.util import const_property
from pyadb import ADB

from ._backend import DUTBackend
from .subject import BenchmarkSubject, Navigator

_script_dir = os.path.dirname(os.path.realpath(__file__))


class RobotNavigator(Navigator):
  """A navigation backend that uses the robot and OCR/Icon Detection.

  This backend will use icon detection and OCR to navigate a device.
  """
  def __init__(self, dut_backend, icon_shape_file):
    """
    :type dut_backend: DUTBackend
    :param str icon_shape_file: path to icon shape file of the subject.
    """
    self._app_icon_shape_file = icon_shape_file
    self._dut_backend = dut_backend
    self._page_button_coords = {}
    self._app_icon_coords = None

  @property
  def state(self):
    return {
      "page_button_coords": self._page_button_coords,
      "app_icon_coords": self._app_icon_coords
    }

  @state.setter
  def state(self, value):
    self._page_button_coords = value["page_button_coords"]
    self._app_icon_coords = value["app_icon_coords"]

  def Open(self, safe):
    if safe:
      self.Reset()
      self._page_button_coords = {}
    else:
      self._dut_backend.Tap(*self._home_button_coords)

    if safe or self._app_icon_coords is None:
      self._app_icon_coords = self._DetectAppIconCoords()
    if self._app_icon_coords is None:
      return False

    self._dut_backend.Tap(*self._app_icon_coords)
    return True

  def Close(self):
    self._dut_backend.Tap(*self._back_button_coords)

  def Reset(self):
    if self._app_icon_coords:
      self._dut_backend.Tap(*self._app_icon_coords)
    self._dut_backend.Tap(*self._back_button_coords)
    self._dut_backend.Tap(*self._back_button_coords)
    self._dut_backend.Tap(*self._home_button_coords)

  def OpenPage(self, page_name):
    coords = self._page_button_coords.get(page_name, None)
    if not coords:
      self._page_button_coords = self._DetectPageButtonCoords()
      coords = self._page_button_coords[page_name]
    if not coords:
      return False

    self._dut_backend.Tap(*coords)
    return True

  def ClosePage(self):
    self._dut_backend.Tap(*self._back_button_coords)

  @const_property
  def _back_button_coords(self):
    screen_min_width = 50
    button_distance_scale_factor = 0.75
    button_min_distance = 10
    button_max_distance = 20

    back_location = (button_min_distance +
                     (self._dut_backend.width - screen_min_width) *
                     button_distance_scale_factor)
    back_location = min((back_location, button_max_distance))

    return (float(self._dut_backend.width / 2 - back_location),
            float(self._dut_backend.height - 3))

  @const_property
  def _home_button_coords(self):
    return (float(self._dut_backend.width / 2),
            float(self._dut_backend.height - 3))

  def _DetectAppIconCoords(self):
    return self._dut_backend.DetectIcon(self._app_icon_shape_file)

  def _DetectPageButtonCoords(self):
    return self._dut_backend.DetectWords(BenchmarkSubject.PAGE_NAMES)


class ADBNavigator(Navigator):
  """Navigation backend that uses ADB.

  This backend will use the ADB command line tool to communicate with a device.
  It will upload the HTML files needed and open them in Chrome.
  """

  REMOTE_DIR = "/sdcard/crostouch"
  HTML_DIR = os.path.join(_script_dir, "..", "..", "html")
  ADB_PATH = None
  MAIN_ACTION = "android.intent.action.MAIN"
  VIEW_ACTION = "android.intent.action.VIEW"
  HOME_COMPONENT = "android.intent.category.HOME"

  def __init__(self, adb_device, component):
    """
    :param str adb_device: Serial number of the adb device.
    """
    self._adb_device = adb_device
    self._adb = None
    self._component = component
    ADBNavigator._FindADBBinary()

  @property
  def state(self):
    return {}

  @state.setter
  def state(self, value):
    pass

  def Open(self, safe):
    if not self._adb:
      self._adb = ADB(self.ADB_PATH)
      self._adb.get_devices()
      self._adb.set_target_device(self._adb_device)
      self._UploadFiles()
    self.Reset()

  def Close(self):
    self._StartActivity(self.MAIN_ACTION, self.HOME_COMPONENT, None)

  def OpenPage(self, page_name):
    self._OpenFile("%s.html" % page_name.lower())

  def ClosePage(self):
    self.Close()

  def Reset(self):
    self.Close()
    self._UploadFiles()

  def _CheckErrors(self):
    error = self._adb.get_error()
    if error:
      raise Exception(error)

  def _UploadFiles(self):
    self._adb.shell_command("mkdir -p %s" % self.REMOTE_DIR)

    filenames = ["jquery.min.js"]
    filenames += ["%s.html" % page.lower()
                  for page in BenchmarkSubject.PAGE_NAMES]

    for filename in filenames:
      self._adb.push_local_file(os.path.join(self.HTML_DIR, filename),
                                os.path.join(self.REMOTE_DIR, filename))

  def _OpenFile(self, filename):
    remote_file = os.path.join(self.REMOTE_DIR, filename)
    uri = "file://%s" % remote_file
    self._StartActivity(self.VIEW_ACTION, self._component, uri)

  def _StartActivity(self, action, component, uri):
    cmd = ["am start"]
    for flag, value in [("-a", action), ("-n", component), ("-d", uri)]:
      if value:
        cmd.append("%s %s" % (flag, value))
    self._adb.shell_command(" ".join(cmd))

  @classmethod
  def _FindADBBinary(cls):
    if not cls.ADB_PATH:
      for path in os.environ["PATH"].split(os.pathsep):
        adb_path = os.path.join(path, "adb")
        if os.path.exists(adb_path):
          cls.ADB_PATH = adb_path
    if not cls.ADB_PATH:
      raise Exception("Please install adb and make it available on PATH.")


# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementations of the Navigator interface."""

import os
import time

from safetynet import Any, Dict

from optofidelity.util import const_property

from .adb import ADB
from .backend import DUTBackend
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
      raise Exception("Cannot detect app icon")

    self._dut_backend.Tap(*self._app_icon_coords)

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
      raise Exception("Cannot detect page button '%s'" % page_name)

    self._dut_backend.Tap(*coords)

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


class BaseADBNavigator(Navigator):
  """Navigation backend that uses ADB.

  This backend will use the ADB command line tool to communicate with a device
  to invoke intents to navigate to test pages.
  """
  REMOTE_DIR = "/sdcard/crostouch"

  def __init__(self, adb_device, stay_alive=False):
    """
    :param str adb_device: Serial number of the adb device.
    """
    self._adb = ADB(adb_device)
    self._stay_alive = stay_alive

  @property
  def state(self):
    return {}

  @state.setter
  def state(self, value):
    pass

  def Open(self, safe):
    if not self._stay_alive:
      self._adb.PowerOn()

  def Close(self):
    if not self._stay_alive:
      self._adb.PowerOff()

  def ClosePage(self):
    self._adb.SendKey("KEYCODE_HOME")

  def Reset(self):
    self._adb.SendKey("KEYCODE_HOME")
    if not self._stay_alive:
      self._adb.PowerOff()


class WebADBNavigator(BaseADBNavigator):
  """Navigation backend that uses ADB to navigate to websites.

  This backend will use the ADB command line tool to communicate with a device.
  It will upload the HTML files needed and open them in Chrome.
  """
  HTML_DIR = os.path.join(_script_dir, "..", "..", "html")
  VIEW_ACTION = "android.intent.action.VIEW"

  def __init__(self, adb_device, component, stay_alive=False):
    """
    :param str adb_device: Serial number of the adb device.
    """
    super(WebADBNavigator, self).__init__(adb_device, stay_alive)
    self._component = component

  def Open(self, safe):
    super(WebADBNavigator, self).Open(safe)
    self._UploadFiles()

  def OpenPage(self, page_name):
    self._adb.SendKey("KEYCODE_HOME")  # Wake up screen sending home key
    self._OpenFile("%s.html" % page_name.lower())
    time.sleep(1.0)  # Wait for chrome to load the page

  def _UploadFiles(self):
    self._adb.ExecuteShell(["mkdir", "-p", self.REMOTE_DIR])
    filenames = ["jquery.min.js"]
    filenames += ["%s.html" % page.lower()
                  for page in BenchmarkSubject.PAGE_NAMES]

    for filename in filenames:
      self._adb.PushFile(os.path.join(self.HTML_DIR, filename),
                         os.path.join(self.REMOTE_DIR, filename))

  def _OpenFile(self, filename):
    remote_file = os.path.join(self.REMOTE_DIR, filename)
    uri = "file://%s" % remote_file
    self._adb.StartActivity(self.VIEW_ACTION, component=self._component,
                            uri=uri)


class NativeADBNavigator(BaseADBNavigator):
  """Navigation backend that uses ADB to navigate to websites.

  This backend will use the ADB command line tool to communicate with a device.
  It will upload the HTML files needed and open them in Chrome.
  """
  APK_DIR = os.path.join(_script_dir, "..", "..", "apks")

  PAGE_TO_ACTIVITY_MAP = {
    "flash": "FlashActivity",
    "scroll": "ScrollActivity",
    "tap": "TapActivity"
  }

  def __init__(self, adb_device, apk_file, package_name, stay_alive=False):
    """
    :param str adb_device: Serial number of the adb device.
    """
    super(NativeADBNavigator, self).__init__(adb_device, stay_alive)
    self._apk_file = apk_file
    self._package_name = package_name

  def Open(self, safe):
    super(NativeADBNavigator, self).Open(safe)
    self._adb.InstallAPK(os.path.join(self.APK_DIR, self._apk_file))

  def OpenPage(self, page_name):
    page_name = page_name.lower()

    self._adb.SendKey("KEYCODE_HOME")  # Wake up screen sending home key
    component = self._package_name + "/." + self.PAGE_TO_ACTIVITY_MAP[page_name]
    self._adb.StartActivity(component=component)
    time.sleep(1.0)  # Wait for activity to open

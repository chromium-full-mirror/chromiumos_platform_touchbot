# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementations of the Navigator interface."""

from abc import abstractmethod, abstractproperty
import os
import time

from safetynet import Any, Dict, InterfaceMeta, List

from optofidelity.util import const_property

from .adb import ADB
from .backend import DUTBackend

_script_dir = os.path.dirname(os.path.realpath(__file__))


class Navigator(object):
  """Backend class to navigate a device to open subjects and pages."""
  __metaclass__ = InterfaceMeta

  @abstractproperty
  def activities(self):
    """List of supported activity names.

    :rtype List[str]
    """

  @abstractproperty
  def state(self):
    """State information. (e.g. coordinates of detected buttons)"""

  @abstractmethod
  def AddActivity(self, activity_name, parameters):
    """Register an activity with sub-class specific parameters."""

  @abstractmethod
  def Open(self, safe):
    """Open the subject.

    :param bool safe: True instructs the backend to take extra precautions. At
           the expense of more time to complete the task.
    """

  @abstractmethod
  def Close(self):
    """Close the subject."""

  @abstractmethod
  def Reset(self):
    """Reset the underlying DUT.

    This is a last resort after issues with opening the subject. This 'should'
    return the DUT into a state where the subject can be opened again.
    """

  @abstractmethod
  def OpenActivity(self, activity_name):
    """Open activity.

    :type activity_name: str
    """

  @abstractmethod
  def CloseActivity(self):
    """Close previously opened activity."""


class RobotNavigator(Navigator):
  """A navigation backend that uses the robot and OCR/Icon Detection.

  This backend will use icon detection and OCR to navigate a device.
  """
  def __init__(self, dut_backend, icon_shape_file):
    """
    :type dut_backend: DUTBackend
    :param str icon_shape_file: path to icon shape file of the subject.
    """
    self._dut_backend = dut_backend
    self._app_icon_shape_file = icon_shape_file
    self._app_icon_coords = None
    self._activity_button_names = {}
    self._activity_button_coords = {}

  @classmethod
  def FromConfig(cls, attributes, children, dut_backend):
    self = cls(dut_backend, attributes.get("icon", ""))
    for child_name, child_attrib in children:
      if child_name == "activity":
        self.AddActivity(child_attrib["name"], child_attrib)
    return self

  @property
  def activities(self):
    return self._activity_button_names.keys()

  @property
  def state(self):
    return {
      "page_button_coords": self._activity_button_coords,
      "app_icon_coords": self._app_icon_coords
    }

  @state.setter
  def state(self, value):
    self._activity_button_coords = value["page_button_coords"]
    self._app_icon_coords = value["app_icon_coords"]

  def AddActivity(self, activity_name, parameters):
    self._activity_button_names[activity_name] = parameters["text"]

  def Open(self, safe):
    if safe:
      self.Reset()
    else:
      self._dut_backend.Tap(*self._home_button_coords)

    if safe or self._app_icon_coords is None:
      self._app_icon_coords = self._DetectAppIconCoords()

    self._dut_backend.Tap(*self._app_icon_coords)
    if safe or not self._activity_button_coords:
      self._activity_button_coords = self._DetectActivityButtonCoords()

  def Close(self):
    self._dut_backend.Tap(*self._back_button_coords)

  def Reset(self):
    if self._app_icon_coords:
      self._dut_backend.Tap(*self._app_icon_coords)
    self._dut_backend.Tap(*self._back_button_coords)
    self._dut_backend.Tap(*self._back_button_coords)
    self._dut_backend.Tap(*self._home_button_coords)

  def OpenActivity(self, activity_name):
    coords = self._activity_button_coords[activity_name]
    self._dut_backend.Tap(*coords)

  def CloseActivity(self):
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
    coords = self._dut_backend.DetectIcon(self._app_icon_shape_file)
    if coords is None:
      raise Exception("Cannot detect app icon")
    return coords

  def _DetectActivityButtonCoords(self):
    button_names = self._activity_button_names.values()
    button_coords = self._dut_backend.DetectWords(button_names)
    activity_coords = dict()
    for activity_name, button_name in self._activity_button_names.iteritems():
      coords = button_coords[button_name]
      if coords is None:
        raise Exception("Cannot find button '%s' for activity '%s" %
                        (button_name, activity_name))
      activity_coords[activity_name] = coords
    return activity_coords


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
    self._activity_intents = {}

  @classmethod
  def FromConfig(cls, attributes, children, dut_backend):
    return cls(attributes.get("adb"))

  @property
  def state(self):
    return {}

  @state.setter
  def state(self, value):
    pass

  def Open(self, safe):
    if not self._stay_alive:
      self._adb.PowerOn()

  def OpenActivity(self, activity_name):
    self._adb.SendKey("KEYCODE_HOME")  # Wake up screen sending home key
    intent_params = self._activity_intents[activity_name]
    self._adb.StartActivity(**intent_params)
    time.sleep(1.0)  # Wait for activity to load

  def Close(self):
    if not self._stay_alive:
      self._adb.PowerOff()

  def CloseActivity(self):
    self._adb.SendKey("KEYCODE_HOME")

  def Reset(self):
    self._adb.SendKey("KEYCODE_HOME")
    if not self._stay_alive:
      self._adb.PowerOff()

  def AddActivity(self, activity_name, parameters):
    self._activity_intents[activity_name] = parameters


class WebADBNavigator(BaseADBNavigator):
  """Navigation backend that uses ADB to navigate to websites.

  This backend will use the ADB command line tool to communicate with a device.
  It will upload the HTML files needed and open them in Chrome.
  """
  VIEW_ACTION = "android.intent.action.VIEW"

  def __init__(self, adb_device, component, stay_alive=False):
    """
    :param str adb_device: Serial number of the adb device.
    """
    super(WebADBNavigator, self).__init__(adb_device, stay_alive)
    self._component = component
    self._activity_files = {}
    self._resources = []

  @classmethod
  def FromConfig(cls, attributes, children, dut_backend):
    self = cls(attributes["adb"], attributes["component"])
    for child_name, child_attrib in children:
      if child_name == "activity":
        self.AddActivity(child_attrib["name"], child_attrib)
      if child_name == "resource":
        self._resources.append(child_attrib["file"])
    return self

  def Open(self, safe):
    super(WebADBNavigator, self).Open(safe)

    self._adb.ExecuteShell(["mkdir", "-p", self.REMOTE_DIR])
    for filename in (self._resources + self._activity_files.values()):
      basename = os.path.basename(filename)
      remote_file = os.path.join(self.REMOTE_DIR, basename)
      self._adb.PushFile(filename, remote_file)

  def AddActivity(self, activity_name, parameters):
    html_file = parameters["file"]
    self._activity_files[activity_name] = html_file
    basename = os.path.basename(html_file)

    remote_file = os.path.join(self.REMOTE_DIR, basename)
    uri = "file://%s" % remote_file
    intent_params = dict(component=self._component, uri=uri)
    super(WebADBNavigator, self).AddActivity(activity_name, intent_params)


class NativeADBNavigator(BaseADBNavigator):
  """Navigation backend that uses ADB to navigate to websites.

  This backend will use the ADB command line tool to communicate with a device.
  It will upload the HTML files needed and open them in Chrome.
  """

  def __init__(self, adb_device, apk_file, package_name, stay_alive=False):
    """
    :param str adb_device: Serial number of the adb device.
    """
    super(NativeADBNavigator, self).__init__(adb_device, stay_alive)
    self._apk_file = apk_file
    self._package_name = package_name

  @classmethod
  def FromConfig(cls, attributes, children, dut_backend):
    self = cls(attributes["adb"], attributes["apk"], attributes["package"])
    for child_name, child_attrib in children:
      if child_name == "activity":
        self.AddActivity(child_attrib["name"], child_attrib)
    return self

  def Open(self, safe):
    super(NativeADBNavigator, self).Open(safe)
    self._adb.InstallAPK(self._apk_file)

  def AddActivity(self, activity_name, parameters):
    component = self._package_name + "/." + parameters["intent"]
    intent_params = dict(component=component)
    super(NativeADBNavigator, self).AddActivity(activity_name, intent_params)

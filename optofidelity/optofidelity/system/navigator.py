# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementations of the Navigator interface."""

from abc import abstractmethod, abstractproperty
import os
import time

from safetynet import Any, Dict, TypecheckMeta, List

from optofidelity.util import ADB, AskUserContinue, const_property

from .backend import DUTBackend

_script_dir = os.path.dirname(os.path.realpath(__file__))


class Navigator(object):
  """Backend class to navigate a device to open subjects and pages."""
  __metaclass__ = TypecheckMeta

  @property
  def state(self):
    """State information. (e.g. coordinates of detected buttons)"""
    return {}

  def SetUp(self):
    """SetUp the navigator to run on a device."""

  def Prepare(self):
    """Prepare the underlying device for a benchmark run."""

  def Verify(self):
    """Verify that the device is accessible for a benchmark run."""

  @abstractmethod
  def Open(self):
    """Open the subject."""

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
  def Cleanup(self):
    """Get device back into a clean state."""

  @abstractmethod
  def HasActivity(self, activity_name):
    """:returns bool: True if the activity can be opened."""

  @abstractmethod
  def OpenActivity(self, activity_name):
    """Open activity.

    :type activity_name: str
    """

  @abstractmethod
  def CloseActivity(self):
    """Close previously opened activity."""


class BaseNavigator(Navigator):
  """Basic implementation to keep track of the device state."""

  def __init__(self):
    self._is_open = False
    self._current_activity = None

  def Open(self):
    if self._is_open:
      raise Exception("Subject already open.")
    self._Open()
    self._is_open = True

  def Close(self):
    if not self._is_open:
      raise Exception("Subject has not been opened.")
    if self._current_activity:
      raise Exception("Activity still open.")
    self._Close()
    self._is_open = False

  def Reset(self):
    self._Reset()
    self._is_open = False
    self._current_activity = None

  def Cleanup(self):
    if self._current_activity:
      self.CloseActivity()
    if self._is_open:
      self.Close()

  def OpenActivity(self, activity_name):
    if not self._is_open:
      raise Exception("Can't open activity if subject has not been opened.")
    if self._current_activity:
      raise Exception("Another activity is already open.")
    if not self.HasActivity(activity_name):
      raise ValueError("Unknown activity name '%s'" % activity_name)

    self._OpenActivity(activity_name)
    self._current_activity = activity_name

  def CloseActivity(self):
    """Close previously opened activity."""
    if not self._current_activity:
      raise Exception("No activity open.")
    self._CloseActivity()
    self._current_activity = None

  def _Open(self):
    """Private implementation of Open"""

  def _Close(self):
    """Private implementation of Close"""

  def _Reset(self):
    """Private implementation of Reset"""

  def _OpenActivity(self, activity_name):
    """Private implementation of OpenActivity"""

  def _CloseActivity(self):
    """Private implementation of CloseActivity"""


class ManualNavigator(BaseNavigator):
  @classmethod
  def FromConfig(cls, attributes, children, dut_backend):
    return cls()

  def HasActivity(self, activity_name):
    return True

  def _OpenActivity(self, activity_name):
    if self._current_activity != activity_name:
      AskUserContinue("Open the '%s' activity" % activity_name)
      self._current_activity = activity_name


class RobotNavigator(BaseNavigator):
  """A navigation backend that uses the robot and OCR/Icon Detection.

  This backend will use icon detection and OCR to navigate a device.
  The device is expected to be in a kiosk mode always running the benchmark app.
  """

  NEUTRAL_ACTIVITY = "neutral"
  """Name of neutral activity to go back to after benchmark."""

  def __init__(self, dut_backend):
    """
    :type dut_backend: DUTBackend
    """
    super(RobotNavigator, self).__init__()
    self._dut_backend = dut_backend
    self._activity_targets = {}
    self._activity_coords = {}

  @classmethod
  def FromConfig(cls, attributes, children, dut_backend):
    self = cls(dut_backend)
    for child_name, parameters in children:
      if child_name == "activity":
        self.AddActivity(parameters["name"], parameters.get("text"),
                         parameters.get("icon"))
    return self

  @property
  def state(self):
    return {
      "activity_coords": self._activity_coords
    }

  @state.setter
  def state(self, value):
    self._activity_coords = value["activity_coords"]

  def AddActivity(self, name, text=None, icon=None):
    if text is None and icon is None:
      raise ValueError("Specify either 'text' or 'icon'")
    self._activity_targets[name] = (text, icon)

  def HasActivity(self, activity_name):
    return activity_name in self._activity_targets

  def SetUp(self):
    icons = {i: a for a, (w, i) in self._activity_targets.iteritems()
                  if i is not None}
    words = {w: a for a, (w, i) in self._activity_targets.iteritems()
                  if w is not None}

    word_coords = self._dut_backend.DetectWords(words.keys())
    for word, coords in word_coords.iteritems():
      if coords is None:
        raise Exception("Cannot detect word '%s'" % (word,))
      self._activity_coords[words[word]] = coords

    for icon_file, activity in icons.iteritems():
      coords = self._dut_backend.DetectIcon(icon_file)
      if coords is None:
        raise Exception("Cannot detect icon '%s'" % (icon_file,))
      self._activity_coords[activity] = coords

  def Prepare(self):
    self._CloseActivity()

  def _Open(self):
    if len(self._activity_targets) != len(self._activity_coords):
      raise Exception("You need to run --setup before using this navigator.")

  def _Reset(self):
    self._CloseActivity()

  def _OpenActivity(self, activity_name):
    coords = self._activity_coords[activity_name]
    self._dut_backend.Tap(*coords)

  def _CloseActivity(self):
    if self.NEUTRAL_ACTIVITY  in self._activity_coords:
      coords = self._activity_coords[self.NEUTRAL_ACTIVITY]
      self._dut_backend.Tap(*coords)


class BaseADBNavigator(BaseNavigator):
  """Navigation backend that uses ADB.

  This backend will use the ADB command line tool to communicate with a device
  to invoke intents to navigate to test pages.
  """
  REMOTE_DIR = "/sdcard/crostouch"

  def __init__(self, adb_device, stay_alive=False):
    """
    :param str adb_device: Serial number of the adb device.
    """
    super(BaseADBNavigator, self).__init__()
    self._adb = ADB(adb_device)
    self._stay_alive = stay_alive
    self._activity_intents = {}

  def AddActivity(self, activity_name, intent_params):
    self._activity_intents[activity_name] = intent_params

  def HasActivity(self, activity_name):
    return activity_name in self._activity_intents

  def Verify(self):
    self.Open()
    self.Close()

  def _Open(self):
    if not self._stay_alive:
      self._adb.PowerOn()

  def _OpenActivity(self, activity_name):
    self._adb.SendKey("KEYCODE_HOME")  # Wake up screen sending home key
    intent_params = self._activity_intents[activity_name]
    self._adb.StartActivity(**intent_params)
    time.sleep(1.0)  # Wait for activity to load

  def _Close(self):
    if not self._stay_alive:
      self._adb.PowerOff()

  def _CloseActivity(self):
    self._adb.SendKey("KEYCODE_HOME")

  def _Reset(self):
    self._adb.SendKey("KEYCODE_HOME")
    if not self._stay_alive:
      self._adb.PowerOff()


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
    self._resources = []

  @classmethod
  def FromConfig(cls, attributes, children, dut_backend):
    self = cls(attributes["adb"], attributes["component"],
               attributes.get("stay-alive", False))
    for child_name, parameters in children:
      if child_name == "activity":
        activity_name = parameters["name"]
        html_file = parameters["file"]
        self.AddHTMLActivity(activity_name, html_file)
      if child_name == "resource":
        self._resources.append(parameters["file"])
    return self

  def SetUp(self):
    self._adb.ExecuteShell(["mkdir", "-p", self.REMOTE_DIR])
    for filename in self._resources:
      basename = os.path.basename(filename)
      remote_file = os.path.join(self.REMOTE_DIR, basename)
      self._adb.PushFile(filename, remote_file)

  def AddHTMLActivity(self, activity_name, html_file):
    self._resources.append(html_file)
    basename = os.path.basename(html_file)
    remote_file = os.path.join(self.REMOTE_DIR, basename)
    uri = "file://%s" % remote_file
    intent_params = dict(component=self._component, uri=uri)
    self.AddActivity(activity_name, intent_params)


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
    self = cls(attributes["adb"], attributes["apk"], attributes["package"],
               attributes.get("stay-alive", False))
    for child_name, parameters in children:
      if child_name == "activity":
        if "class-name" in parameters:
          component = self._package_name + "/." + parameters["class-name"]
          intent_params = dict(component=component, force_stop=True)
        else:
          intent_params = dict()
          for key in ("action", "component", "uri", "category"):
            if key in parameters:
              intent_params[key] = parameters[key]
          for flag in ("wait", "force_stop"):
            attrib = parameters.get(flag.replace("_", "-"))
            if attrib  in ("True", "true"):
              intent_params[flag] = True
            if attrib  in ("False", "false"):
              intent_params[flag] = False
        self.AddActivity(parameters["name"], intent_params)
    return self

  def SetUp(self):
    if self._adb.GetPackageVersion(self._package_name):
      self._adb.UninstallPackage(self._package_name)
    self._adb.InstallAPK(self._apk_file)

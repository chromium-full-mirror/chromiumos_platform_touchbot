# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementations of the Navigator interface."""

from abc import abstractmethod, abstractproperty
import os
import time

from safetynet import Any, Dict, InterfaceMeta, List

from optofidelity.util import ADB, AskUserContinue, const_property

from .backend import DUTBackend

_script_dir = os.path.dirname(os.path.realpath(__file__))


class Navigator(object):
  """Backend class to navigate a device to open subjects and pages."""
  __metaclass__ = InterfaceMeta

  def __init__(self):
    self._is_open = False
    self._current_activity = None

  def SetUp(self):
    pass

  def Prepare(self):
    pass

  def Verify(self):
    pass

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

  def Open(self, safe):
    """Open the subject.

    :param bool safe: True instructs the backend to take extra precautions. At
           the expense of more time to complete the task.
    """
    if self._is_open:
      raise Exception("Subject already open.")
    self._Open(safe)
    self._is_open = True

  def Close(self):
    """Close the subject."""
    if not self._is_open:
      raise Exception("Subject has not been opened.")
    self._Close()
    self._is_open = False

  def Reset(self):
    """Reset the underlying DUT.

    This is a last resort after issues with opening the subject. This 'should'
    return the DUT into a state where the subject can be opened again.
    """
    self._Reset()
    self._is_open = False
    self._current_activity = None

  def Cleanup(self):
    if self._current_activity:
      self.CloseActivity()
    if self._is_open:
      self.Close()

  def OpenActivity(self, activity_name):
    """Open activity.

    :type activity_name: str
    """
    if not self._is_open:
      raise Exception("Can't open activity if subject has not been opened.")
    if self._current_activity:
      raise Exception("Another activity is already open.")
    if activity_name not in self.activities:
      raise ValueError("Unknown activity name '%s'" % activity_name)

    self._OpenActivity(activity_name)
    self._current_activity = activity_name

  def CloseActivity(self):
    """Close previously opened activity."""
    if not self._current_activity:
      raise Exception("No activity open.")
    self._CloseActivity()
    self._current_activity = None

  def _Open(safe=False):
    pass

  def _Close(self):
    pass

  def _Reset(self):
    pass

  def _OpenActivity(self):
    pass

  def _CloseActivity(self):
    pass


class ManualNavigator(Navigator):
  @classmethod
  def FromConfig(cls, attributes, children, dut_backend):
    return cls()

  @property
  def activities(self):
    return []

  @property
  def state(self):
    return {}

  def AddActivity(self, activity_name, parameters):
    pass

  def Open(self, safe):
    pass

  def Close(self):
    pass

  def Reset(self):
    pass

  def Cleanup(self):
    pass

  def OpenActivity(self, activity_name):
    if self._current_activity != activity_name:
      AskUserContinue("Open the '%s' activity" % activity_name)
      self._current_activity = activity_name

  def CloseActivity(self):
    pass


class RobotNavigator(Navigator):
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

  @classmethod
  def FromConfig(cls, attributes, children, dut_backend):
    self = cls(dut_backend)
    for child_name, child_attrib in children:
      if child_name == "activity":
        self.AddActivity(child_attrib["name"], child_attrib)
    return self

  @property
  def activities(self):
    return self._activity_targets.keys()

  @property
  def state(self):
    return {
      "activity_coords": self._activity_coords
    }

  @state.setter
  def state(self, value):
    self._activity_coords = value["activity_coords"]

  def AddActivity(self, activity_name, parameters):
    self._activity_targets[activity_name] = (parameters.get("text"),
                                             parameters.get("icon"))

  def _Open(self, safe):
    if len(self._activity_targets) != len(self._activity_coords):
      raise Exception("You need to run --setup before using this navigator.")

  def _Close(self):
    pass

  def _Reset(self):
    self._CloseActivity()

  def _OpenActivity(self, activity_name):
    if activity_name not in self._activity_coords:
      raise Exception("Unknown activity %s" % activity_name)
    coords = self._activity_coords[activity_name]
    self._dut_backend.Tap(*coords)

  def _CloseActivity(self):
    if self.NEUTRAL_ACTIVITY  in self._activity_coords:
      coords = self._activity_coords[self.NEUTRAL_ACTIVITY]
      self._dut_backend.Tap(*coords)


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
    super(BaseADBNavigator, self).__init__()
    self._adb = ADB(adb_device)
    self._stay_alive = stay_alive
    self._activity_intents = {}

  @property
  def activities(self):
    return self._activity_intents.keys()

  @classmethod
  def FromConfig(cls, attributes, children, dut_backend):
    return cls(attributes.get("adb"))

  @property
  def state(self):
    return {}

  @state.setter
  def state(self, value):
    pass

  def Verify(self):
    self.Open(False)
    self.Close()

  def _Open(self, safe):
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

  def SetUp(self):
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

  def SetUp(self):
    if self._adb.GetPackageVersion(self._package_name):
      self._adb.UninstallPackage(self._package_name)
    self._adb.InstallAPK(self._apk_file)

  def AddActivity(self, activity_name, parameters):
    if "class-name" in parameters:
      component = self._package_name + "/." + parameters["class-name"]
      intent_params = dict(component=component)
    else:
      intent_params = {k: v for k, v in parameters.iteritems()
                            if k in ("action", "component", "uri", "category")}
    super(NativeADBNavigator, self).AddActivity(activity_name, intent_params)

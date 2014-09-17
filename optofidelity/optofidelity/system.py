# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Classes to manage and operate multiple OptoFidelity robots.

The classes in this module build a tree with a root of OptofidelityTestSystem,
which contains DeviceUnderTests. Whereas each DeviceUnderTest contains
multiple TestApps and a TestApp can have multiple pages.

During the calibration phase, the robot will automatically detect how to access
all those apps and pages, and access the high speed camera to calibrate the
screen location in the camera space. All this calibration data can then be
stored and read from a file to skip the lengthy calibration process.
"""
from ConfigParser import SafeConfigParser
import h5py

from tnt.TnTClient import TnTClient
from detection import Screen
from phantom import Phantom

class DUTException(Exception):
  """Exceptions in handling a device under test.

  Usually these Exceptions can be recovered from by resetting the App or DUT.
  """
  def __init__(self, dut, error):
    Exception.__init__(self)
    self.dut = dut
    self.error = error

  def __str__(self):
    return str(self.dut) + ": " + str(self.error)


def RetryFunction(function, recover_function, title, max_attempts=3):
  """Try to runs function() recover from possible DUTExceptions.

  function: The function to execute
  recover_function: A function executed when a DUTException is thrown
  title: For debug prints
  max_attempts: How often to try.
  """
  for i in range(max_attempts):
    try:
      print "%s (Attempt %d)" % (title, i+1)
      function()
      return
    except DUTException as e:
      print "%s: FAILED" % title
      print "%s: Exception: %s" % (title, e)
      print "%s: Trying to recover." % title
      recover_function()


class OptofidelityTestSystem(object):
  """Robot system which manages multiple DUTs.

  The system is setup using ReadConfig, followed by either a call to
  Calibrate to run the calibration process, or LoadCalibration to load
  calibration data previously saved using SaveCalibration.

  After the calibration you can access devices by name and execute commands on
  them such as:
    >>> system["Nexus7"].Reset()
    >>> system["Nexus7"].EnterApp("Clank")
  """
  def __init__(self, config_file):
    self.duts = {}
    self.tnt = None
    self.camera = None
    self.ReadConfig(config_file)

  def __getitem__(self, key):
    if isinstance(key, int):
      return self.duts.values().__getitem__(key)
    else:
      return self.duts.__getitem__(key)

  def ReadConfig(self, config_file):
    """Read robot configuration from file.

    The configuration contains a list of DUTs and their properties as follows:
    [DUTName]
    type=Android
    apps=Clank

    The DUTName has to be the name of the DUT on the OptoFidelity system,
    whereas the only supported type at this time is Android, and the only
    supported app is Clank.
    """
    config = SafeConfigParser()
    config.read([config_file])

    host = config.get("robot", "host")
    port = config.get("robot", "port")
    self.tnt = TnTClient(host, port)

    camera_host = config.get("camera", "host")
    self.camera = Phantom(camera_host)

    for dut_name in config.sections():
      if dut_name in ("robot", "camera"):
        continue
      dut_type = config.get(dut_name, "type")
      dut_apps = config.get(dut_name, "apps").split(",")
      dut_apps = [a.strip() for a in dut_apps]
      if dut_type.lower() == "android":
        dut = AndroidDUT(self.tnt, dut_name)
      else:
        raise Exception("Unknown device type %s" % dut_type)

      for app_name in dut_apps:
        if app_name.lower() == "clank":
          app = ClankTestApp(dut)
        else:
          raise Exception("Unknown device type %s" % dut_type)
        dut.RegisterApp(app)
      self.duts[dut.name] = dut

  def Calibrate(self):
    """Run calibration on all DUTs."""
    for dut in self.duts.values():
      RetryFunction(lambda: dut.Calibrate(self.camera),
                    lambda: dut.Reset(),
                    "Calibrate %s" % dut)

  def SaveCalibration(self, filename):
    """Store calibration information into an hdf5 file."""
    hdf5 = h5py.File(filename, "w")
    for dut in self.duts.values():
      dut.SaveCalibration(hdf5.create_group(dut.name))
    hdf5.close()

  def LoadCalibration(self, filename):
    """Load calibration information from an hdf5 file."""
    hdf5 = h5py.File(filename, "r")
    for dut in self.duts.values():
      dut.LoadCalibration(hdf5[dut.name])
    hdf5.close()

class DeviceUnderTest(object):
  """Functionality to operate a DUT.

  It provides methods to navigate different apps on the device and execute
  basic movements and robot commands.
  """
  def __init__(self, tnt, name):
    self.name = name
    self.apps = {}
    self.client = tnt.dut(self.name)
    self.width = self.client.panel_width
    self.height = self.client.panel_height
    self.test_plane = self.width / 2

  def SaveCalibration(self, hdf5):
    for app in self.apps.values():
      app.SaveCalibration(hdf5.create_group(app.name))

  def LoadCalibration(self, hdf5):
    for app in self.apps.values():
      app.LoadCalibration(hdf5[app.name])

  def RegisterApp(self, app):
    self.apps[app.name] = app

  def Calibrate(self, camera):
    """Calibrate this DUT and all it's apps."""
    self.ExitApp()

    for app in self.apps.values():
      x, y = self.FindIcon(app.TEST_APP_ICON)
      if x < 0 or y < 0:
        raise DUTException(self, "Cannot find icon " + app.TEST_APP_ICON)
      self.Tap(x, y)
      app.Calibrate(x, y, camera)
      self.ExitApp()

  def Reset(self):
    self.ExitApp()
    self.ExitApp()
    return self.IsHome()

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

  def Tap(self, x, y):
    self.client.tap(x, y)

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


class TestApp(object):
  """Provides functionality to navigate different pages of an app."""
  PAGE_TAP = "Tap"
  PAGE_MOVE = "Move"
  PAGE_CLICK = "Click"
  PAGE_FLASH = "Flash"
  TEST_APP_ICON = None

  def __init__(self, dut, name):
    self.dut = dut
    self.name = name
    self.pages = {
        self.PAGE_TAP: (-1, -1),
        self.PAGE_MOVE: (-1, -1),
        self.PAGE_CLICK: (-1, -1),
        self.PAGE_FLASH: (-1, -1),
    }
    self.screen = None
    self.button_coords = (-1, -1)

  def SaveCalibration(self, hdf5):
    hdf5.create_dataset("button_coords", data=self.button_coords)
    hdf5.create_group("pages")
    for page, coords in self.pages.items():
      hdf5["pages"].create_dataset(page, data=coords)
    self.screen.Save(hdf5.create_group("screen"))

  def LoadCalibration(self, hdf5):
    button_coords = hdf5["button_coords"]
    self.button_coords = (button_coords[0], button_coords[1])

    for page in self.pages.keys():
      coords = hdf5["pages"][page]
      self.pages[page] = (coords[0], coords[1])
    self.screen = Screen.Load(hdf5["screen"])

  def CalibrateButtons(self):
    for text, x, y in self.dut.ReadText():
      if text in self.pages:
        self.pages[text] = (x, y)

    for page, (x, y) in self.pages.items():
      if x < 0 or y < 0:
        raise DUTException(self.dut, "Cannot find button for page " + page)

  def CalibrateScreen(self, camera):
    self.EnterPage(self.PAGE_FLASH)
    self.dut.ClearScreen()
    camera.Record(300)
    camera.WaitUntilReady()
    self.ExitPage()

    reader = camera.GetVideoReader()
    self.screen = Screen()
    self.screen.DetectScreen(reader.Frames(step=10))

  def Calibrate(self, x, y, camera):
    self.button_coords = (x, y)
    self.CalibrateButtons()
    self.CalibrateScreen(camera)

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


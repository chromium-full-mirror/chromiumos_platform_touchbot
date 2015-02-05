# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contracts import contract

import cPickle as pickle
import re
import xml.etree.ElementTree as ElementTree

from optofidelity.phantom import Phantom
from optofidelity.system.dut import CalibrationDUT
from optofidelity.tnt.TnTClient import TnTClient

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
  dut_classes = {}
  app_classes = {}
  is_mock = False

  def __init__(self, config_file):
    self.duts = {}
    self.tnt = None
    self.camera = None
    self.led_calibration = None
    self.calibration_dut = None
    self.ReadConfig(config_file)

  @classmethod
  @contract(dut_class=type)
  def RegisterDUTClass(cls, dut_class):
    cls.dut_classes[dut_class.type_name] = dut_class

  @classmethod
  @contract(app_class=type)
  def RegisterAppClass(cls, app_class):
    cls.app_classes[app_class.name] = app_class

  def __getitem__(self, key):
    if isinstance(key, int):
      return self.duts.values().__getitem__(key)
    else:
      return self.duts.__getitem__(key)

  def SaveState(self, filename):
    pickle.dump(self, open(filename, "w"), protocol=-1)

  @staticmethod
  def LoadState(filename):
    return pickle.load(open(filename, "r"))

  def ReadConfig(self, config_file):
    """Read robot configuration from file."""
    root = ElementTree.parse(config_file).getroot()

    def ParseCoord(element, attrib_name, default=None):
      if attrib_name in element.attrib:
        string = element.attrib[attrib_name]
        match = re.match("\(\s*([0-9.]+)\s*\,\s*([0-9.]+)\)", string)
        return int(match.group(1)), int(match.group(2))
      return default

    def ParseFlip(element):
      orientation = element.get("orientation", "right")
      if orientation == "right":
        return False
      elif orientation == "left":
        return True
      raise Exception("Orientation must be left or right")

    app_variants = {}
    for name, cls in self.app_classes.iteritems():
      app_variants[name] = (cls, None)
    for variant_elem in root.iter("app-variant"):
      name = variant_elem.attrib["name"]
      cls = self.app_classes[variant_elem.attrib["type"]]
      margin = ParseCoord(variant_elem, "margin")
      app_variants[name] = (cls, margin)

    robot = root.find("robot")
    self.tnt = TnTClient(robot.attrib["host"], robot.attrib["port"])

    camera = root.find("camera")
    self.camera = Phantom(camera.attrib["host"])

    calib_elem = root.find("calibration-device")
    if calib_elem is not None:
      tnt_name = calib_elem.get("tnt_name", "calibration")
      self.calibration_dut = CalibrationDUT(self.tnt.dut(tnt_name), name, False)

    for dut_elem in root.iter("dut"):
      name = dut_elem.attrib["name"]
      dut_type = self.dut_classes[dut_elem.attrib["type"]]
      tnt_name = dut_elem.get("tnt_name", name)
      flip = ParseFlip(dut_elem)
      dut = dut_type(self.tnt.dut(tnt_name), name, flip)

      for app_elem in dut_elem.iter("app"):
        (app_type, predef_margin) = app_variants[app_elem.attrib["type"]]
        margin = ParseCoord(app_elem, "margin", predef_margin)
        app = app_type(dut)
        if margin:
          app.ApplyMargin(margin)
        dut.RegisterApp(app)

      self.duts[dut.name] = dut

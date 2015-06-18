# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of the BenchmarkSystem class."""

from collections import namedtuple
import cPickle as pickle
import re
import xml.etree.ElementTree as ElementTree

from safetynet import Optional, TypecheckMeta

from ._navigators import NativeADBNavigator, RobotNavigator, WebADBNavigator
from ._phantom import PhantomCamera
from ._tnt_backend import TnTRobotBackend
from ._updater import ChromeUpdater, ManualUpdater
from .subject import BenchmarkSubject
from .system import BenchmarkSystem, FingerCalibDelay

class BenchmarkSystemConfig(object):
  __metaclass__ = TypecheckMeta

  def __init__(self, config_file):
    self._subject_types = {}
    self.benchmark_system = self._ReadConfig()

  def _ReadConfig(self, config_file):
    system = BenchmarkSystem()

    root = ElementTree.parse(config_file).getroot()

    self._subject_types = {}
    for type_elem in root.iter("subject-type"):
      type_name = type_elem.attrib["type-name"]
      self._subject_types[type_name] = type_elem

    finger_calib = root.find("finger-calibration")
    if finger_calib is not None:
      down = float(finger_calib.get("down-delay", 0.0))
      up = float(finger_calib.get("up-delay", 0.0))
      system.finger_calib_delay = FingerCalibDelay(down, up)

    robot = root.find("robot")
    camera = root.find("camera")

    system.backend = self._CreateBackend(robot.attrib if robot is not None
                                                      else {})
    system.camera = self._CreateCamera(camera.attrib if camera is not None
                                                     else {})

    calib_elem = root.find("led-calibration-subject")
    if calib_elem is not None:
      backend_name = calib_elem.get("backend-name", "calibration")
      dut_backend = system.backend.GetDUTBackend(backend_name)
      nav_backend = RobotNavigator(dut_backend, "")
      subject = BenchmarkSubject("calibration", "calibration", dut_backend,
                                 nav_backend, None, self.camera, (0.0, 0.0))
      system.led_calibration_subject = subject

    for dut_elem in root.iter("dut"):
      self._ReadDUTConfig(system, dut_elem)
    return system

  def _ReadDUTConfig(self, system, dut_elem):
    dut_name = dut_elem.attrib["name"]
    tnt_name = dut_elem.get("backend-name", dut_name)
    dut_backend = system.backend.GetDUTBackend(tnt_name)

    for subject_elem in dut_elem.iter("subject"):
      self._ReadSubjectConfig(system, subject_elem, dut_elem.attrib,
                              dut_backend)

  def _ReadSubjectConfig(self, system, subject_elem, dut_attrib, dut_backend):
    type_name = subject_elem.attrib.get("type", None)
    subject_type = self._subject_types.get(type_name)

    subject_attrib = self._CollectSubjectAttrib(subject_elem, None)

    nav_attrib = self._CollectSubjectAttrib(subject_elem, "navigator")
    navigator = self._CreateNavigator(nav_attrib, subject_attrib, dut_attrib,
                                      dut_backend)

    updater_attrib = self._CollectSubjectAttrib(subject_elem, "updater")
    updater = self._CreateUpdater(updater_attrib, subject_attrib, dut_attrib)

    dut_name = dut_attrib.get("name")
    subject_name = subject_attrib.get("name")
    margin = self._ParseCoord(subject_attrib.get("margin"))

    subject = BenchmarkSubject(dut_name, subject_name, dut_backend, navigator,
                               updater, self.camera, margin)
    system.subjects[subject.name] = subject

  def _CollectSubjectAttrib(self, subject_elem, child_name):
    type_name = subject_elem.attrib.get("type", None)
    subject_type_elem = self._subject_types.get(type_name)

    # First find attributes from subject-type definition
    attrib = {}
    if subject_type_elem is not None:
      if child_name:
        element = subject_type_elem.find(child_name)
        if element is not None:
          attrib.update(element.attrib)
      else:
        attrib.update(subject_type_elem.attrib)

    # Then from subject element itself
    if child_name:
      element = subject_elem.find(child_name)
      if element is not None:
        attrib.update(element.attrib)
    else:
      attrib.update(subject_elem.attrib)
    return attrib

  def _CreateCamera(self, attrib):
    return PhantomCamera(attrib["host"], attrib.get("port"))

  def _CreateBackend(self, attrib):
    return TnTRobotBackend(attrib["host"], attrib.get("port"))

  def _CreateNavigator(self, nav_attrib, subject_attrib, dut_attrib,
                       dut_backend):
    nav_type_name = nav_attrib.get("type", "robot")
    if nav_type_name == "robot":
      return RobotNavigator(dut_backend, nav_attrib["icon"])
    elif nav_type_name == "web_adb":
      return WebADBNavigator(dut_attrib["adb"], nav_attrib["component"])
    elif nav_type_name == "native_adb":
      return NativeADBNavigator(dut_attrib["adb"], nav_attrib["apk"],
                                nav_attrib["package"])
    else:
      raise ValueError("Unknown navigator type name '%s'" % nav_type_name)

  def _CreateUpdater(self, updater_attrib, subject_attrib, dut_attrib):
    updater_type_name = updater_attrib.get("type", "manual")
    if updater_type_name == "manual":
      return ManualUpdater(updater_attrib.get("version"))
    elif updater_type_name == "chrome":
      return ChromeUpdater(dut_attrib["adb"], updater_attrib["channel"])
    else:
      raise ValueError("Unknown updater type name '%s'" % updater_type_name)

  def _ParseCoord(self, string):
    if string:
      match = re.match("\(\s*([0-9.]+)\s*\,\s*([0-9.]+)\)", string)
      return float(match.group(1)), float(match.group(2))
    return (0.0, 0.0)

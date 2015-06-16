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

FingerCalibDelay = namedtuple("FingerCalibDelay", ("down", "up"))

class BenchmarkSystem(object):
  """Robot system which manages multiple DUTs.

  This provides the following properties:
    subjects: A dictionary mapping subject names to BenchmarkSubject instances.
    camera: A HighSpeedCamera instance
    led_calibration_subject: A BenchmarkSubject for the LED calibration plate.
  """
  __metaclass__ = TypecheckMeta

  def __init__(self, config_file):
    """Creates new system from configuration file:

    The configuration file should look like this:

    <optofidelity>
      <robot host="192.168.0.5" />
      <camera host="192.168.0.4" />

      <led-calibration-subject backend-name="calibration" />

      <subject-type type-name="clank_tablet" name="clank" margin="(100, 0)">
        <navigator type="robot" icon="icon.shp" />
      </subject-type>
      <subject-type type-name="clank_phone" name="clank" margin="(0, 50)">
        <navigator type="robot" icon="icon.shp" />
      </subject-type>

      <dut name="some_phone" backend-name="tnt_id">
        <subject type="clank_phone" />
      </dut>

      <dut name="some_tablet">
        <subject type="clank_tablet" />
      </dut>

    </optofidelity>

    Explanation of tags in configuration file:

    <robot host="" port="" />
    Defines the host/port of the machine running the Optofidelity server.

    <camera host="" port="" />
    Defines the host/port of the phantom high speed camera.

    <led-calibration-subject backend-name="" />
    Defines a subject for the LED calibration plate.

    <subject-type type-name="" * />
    Defines a type of subject to reduce duplicate configuration values. All
    attributes from this element are copied to the <subject> elements that
    specify using this type. Same goes for any child elements.

    <subject type="" name="" margin=(top, bottom)" />
    Defines a test subject:
      type: Optional. Name of <subject-type> element to copy attributes from.
      name: Descriptional name of this subject.
      margin: Margin at top and bottom of the screen to account for potential
              UI bars obstructing the testable area.

    <dut name="" backend-name="" [adb=""]/>
    Defines a device under test and can contain any number of <subject>s.
      name: Descriptional name..
      backend-name: Name of the device in the backend (on the Optofidelity
                    robot).
      adb: Optional ADB serial number that connects to this device.

    <navigator type="robot" icon="" />
    Use the robot OCR and icon detection to navigate this subject:
      icon: Path to icon file that descibes this apps icon.

    <navigator type="adb" component="" />
    Use adb to navigate this subject. Requires adb attribute on the <dut>
    element.
      component: Which component to send the VIEW action to.

    :param Optional[str] config_file: Path to configuration file.
    :param bool fake_backend: Use fake backend for robot and camera for testing.
    """
    self.subjects = {}
    self.camera = None
    self.led_calibration_subject = None
    self.finger_calib_delay = FingerCalibDelay(0.0, 0.0)

    self._subject_types = {}
    self._backend = None
    if config_file:
      self._ReadConfig(config_file)

  def SaveState(self, state_file):
    """Save current state to file.

    This mostly includes locations of buttons and icons on devices.
    :param str state_file: File to save into.
    """
    subject_states = {k: s.state for k, s in self.subjects.items()}
    state = {"subjects": subject_states}
    pickle.dump(state, open(state_file, "w"), protocol=-1)

  def LoadState(self, state_file):
    """Load state from file.

    This mostly includes locations of buttons and icons on devices.
    :param str state_file: File to load from.
    """
    state = pickle.load(open(state_file, "r"))
    subject_states = state["subjects"]
    for key, subject in self.subjects.items():
      state = subject_states.get(key, None)
      if state:
        subject.state = state

  def Reset(self):
    """Reset system.

    Moves the robot to it's home location and closes any potentially still
    open subjects.
    """
    self._backend.Reset()

  def Cleanup(self):
    """Cleanup after any subjects that might still be open.

    This method should be called any time the program exits unexpectedly.
    It will try to get all devices back into a neutral state.
    """
    for subject in self.subjects.values():
      subject.Cleanup()

  def _ReadConfig(self, config_file):
    root = ElementTree.parse(config_file).getroot()

    self._subject_types = {}
    for type_elem in root.iter("subject-type"):
      type_name = type_elem.attrib["type-name"]
      self._subject_types[type_name] = type_elem

    finger_calib = root.find("finger-calibration")
    if finger_calib is not None:
      down = float(finger_calib.get("down-delay", 0.0))
      up = float(finger_calib.get("up-delay", 0.0))
      self.finger_calib_delay = FingerCalibDelay(down, up)

    robot = root.find("robot")
    camera = root.find("camera")

    self._backend = self._CreateBackend(robot.attrib if robot is not None
                                                     else {})
    self.camera = self._CreateCamera(camera.attrib if camera is not None
                                                   else {})

    calib_elem = root.find("led-calibration-subject")
    if calib_elem is not None:
      backend_name = calib_elem.get("backend-name", "calibration")
      dut_backend = self._backend.GetDUTBackend(backend_name)
      nav_backend = RobotNavigator(dut_backend, "")
      subject = BenchmarkSubject("calibration", "calibration", dut_backend,
                                 nav_backend, None, self.camera, (0.0, 0.0))
      self.led_calibration_subject = subject

    for dut_elem in root.iter("dut"):
      self._ReadDUTConfig(dut_elem)

  def _ReadDUTConfig(self, dut_elem):
    dut_name = dut_elem.attrib["name"]
    tnt_name = dut_elem.get("backend-name", dut_name)
    dut_backend = self._backend.GetDUTBackend(tnt_name)

    for subject_elem in dut_elem.iter("subject"):
      self._ReadSubjectConfig(subject_elem, dut_elem.attrib, dut_backend)

  def _ReadSubjectConfig(self, subject_elem, dut_attrib, dut_backend):
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
    self.subjects[subject.name] = subject

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

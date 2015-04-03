# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of the BenchmarkSystem class."""

import cPickle as pickle
import re
import xml.etree.ElementTree as ElementTree

from safetynet import TypecheckMeta, Optional

from ._phantom import PhantomCamera
from ._tnt_backend import TnTRobotBackend
from .subject import BenchmarkSubject
from ._navigators import RobotNavigator, ADBNavigator

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

      <subject-type type-name="clank_tablet" name="clank" margin="(100, 0)" />
      <subject-type type-name="clank_phone" name="clank" margin="(0, 50)" />

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
    specify using this type.

    <subject type="" name="" margin=(top, bottom)" icon="" />
    Defines a test subject:
      type: Optional. Name of <subject-type> element to copy attributes from.
      name: Descriptional name of this subject.
      margin: Margin at top and bottom of the screen to account for potential
              UI bars obstructing the testable area.
      icon: Path to icon file that descibes this apps icon.

    <dut name="" backend-name="" />
    Defines a device under test and can contain any number of <subject>s.
      name: Descriptional name..
      backend-name: Name of the device in the backend (on the Optofidelity
                    robot).

    :param Optional[str] config_file: Path to configuration file.
    :param bool fake_backend: Use fake backend for robot and camera for testing.
    """
    self.subjects = {}
    self.camera = None
    self.led_calibration_subject = None

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

    subject_types = {}
    for type_elem in root.iter("subject-type"):
      type_name = type_elem.attrib["type-name"]
      subject_types[type_name] = type_elem.attrib

    robot = root.find("robot")
    camera = root.find("camera")
    self._backend = self._CreateBackend(robot.attrib if robot else {})
    self.camera = self._CreateCamera(camera.attrib if camera else {})

    calib_elem = root.find("led-calibration-subject")
    if calib_elem is not None:
      backend_name = calib_elem.get("backend-name", "calibration")
      dut_backend = self._backend.GetDUTBackend(backend_name)
      nav_backend = RobotNavigator(dut_backend, {})
      subject = BenchmarkSubject("calibration", "calibration", dut_backend,
                                 nav_backend, self.camera, (0.0, 0.0))
      self.led_calibration_subject = subject

    for dut_elem in root.iter("dut"):
      self._ReadDUTConfig(dut_elem, subject_types)

  def _ReadDUTConfig(self, dut_elem, subject_types):
    dut_name = dut_elem.attrib["name"]
    tnt_name = dut_elem.get("backend-name", dut_name)
    dut_backend = self._backend.GetDUTBackend(tnt_name)

    for subject_elem in dut_elem.iter("subject"):
      type_name = subject_elem.attrib.get("type", None)
      attrib = {}
      if type_name in subject_types:
        attrib.update(subject_types[type_name])
      attrib.update(subject_elem.attrib)
      subject = self._CreateSubject(dut_name, dut_backend, attrib)
      self.subjects[subject.name] = subject

  def _CreateCamera(self, attrib):
    return PhantomCamera(attrib["host"], attrib.get("port", None))

  def _CreateBackend(self, attrib):
    return TnTRobotBackend(attrib["host"], attrib.get("port", None))

  def _CreateSubject(self, dut_name, dut_backend, attrib):
    subject_name = attrib["name"]
    adb_id = attrib.get("adb", None)
    margin = self._ParseCoord(attrib.get("margin", None), (0.0, 0.0))
    if adb_id:
      nav_backend = ADBNavigator(adb_id)
    else:
      icon = attrib.get("icon", None)
      nav_backend = RobotNavigator(dut_backend, icon)
    return BenchmarkSubject(dut_name, subject_name, dut_backend,
                            nav_backend, self.camera, margin)

  def _ParseCoord(self, string, default=None):
    if string:
      match = re.match("\(\s*([0-9.]+)\s*\,\s*([0-9.]+)\)", string)
      return float(match.group(1)), float(match.group(2))
    return default
# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of the BenchmarkSystem class."""

from collections import namedtuple
import cPickle as pickle
import re
import xml.etree.ElementTree as ElementTree

from safetynet import Optional, TypecheckMeta

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

  def __init__(self, backend, camera):
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
    self.backend = backend
    self.camera = camera
    self.led_calibration_subject = None
    self.finger_calib_delay = FingerCalibDelay(0.0, 0.0)

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
    self.backend.Reset()

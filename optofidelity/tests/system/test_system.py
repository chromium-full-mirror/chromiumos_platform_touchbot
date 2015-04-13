# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for BenchmarkSystem."""

from tempfile import NamedTemporaryFile
import unittest

from optofidelity.system._fake_backend import FakeDUTBackend
from optofidelity.system.fake import FakeBenchmarkSystem
from optofidelity.system.system import BenchmarkSystem


simple_config = """\
<optofidelity>
  <dut name="device1">
    <subject name="clank" margin="(0, 50)">
      <navigator type="robot" icon="dummy.shp" />
    </subject>
  </dut>
  <dut name="device2" tnt_name="tnt_name">
    <subject name="clank" margin="(50, 0)">
      <navigator type="robot" icon="dummy.shp" />
    </subject>
  </dut>
</optofidelity>
"""

subject_type_config = """\
<optofidelity>
  <subject-type type-name="clank_tablet" name="clank" margin="(100, 0)" >
      <navigator type="robot" icon="dummy.shp" />
  </subject-type>
  <subject-type type-name="clank_phone" name="clank" margin="(0, 50)" >
      <navigator type="robot" icon="dummy.shp" />
  </subject-type>

  <dut name="some_phone" backend-name="tnt_id">
    <subject type="clank_phone" />
  </dut>

  <dut name="some_tablet">
    <subject type="clank_tablet" />
  </dut>
</optofidelity>
"""

calibration_config = """\
<optofidelity>
  <led-calibration-subject backend-name="backend_name" />
</optofidelity>
"""


def TemporaryFileWithData(data):
  tempfile = NamedTemporaryFile()
  tempfile.write(data)
  tempfile.flush()
  return tempfile


class RobotTests(unittest.TestCase):

  def testSimpleConfig(self):
    with TemporaryFileWithData(simple_config) as tempfile:
      system = FakeBenchmarkSystem(tempfile.name)

      self.assertIn("device1/clank", system.subjects)
      self.assertIn("device2/clank", system.subjects)
      subject1 = system.subjects["device1/clank"]
      subject2 = system.subjects["device2/clank"]

      height = subject1._dut_backend.height
      margin = 50
      self.assertAlmostEqual(subject1.top, 0)
      self.assertAlmostEqual(subject1.bottom, height - margin)
      self.assertAlmostEqual(subject2.top, margin)
      self.assertAlmostEqual(subject2.bottom, height)

  def testSubjectTypeConfig(self):
    with TemporaryFileWithData(subject_type_config) as tempfile:
      system = FakeBenchmarkSystem(tempfile.name)

      self.assertIn("some_phone/clank", system.subjects)
      self.assertIn("some_tablet/clank", system.subjects)
      phone_subject = system.subjects["some_phone/clank"]
      tablet_subject = system.subjects["some_tablet/clank"]

      height = phone_subject._dut_backend.height
      phone_margin = 50
      tablet_margin = 100
      self.assertAlmostEqual(phone_subject.top, 0)
      self.assertAlmostEqual(phone_subject.bottom, height - phone_margin)
      self.assertAlmostEqual(tablet_subject.top, tablet_margin)
      self.assertAlmostEqual(tablet_subject.bottom, height)

      self.assertEqual(phone_subject._dut_backend.name, "tnt_id")
      self.assertEqual(tablet_subject._dut_backend.name, tablet_subject.dut_name)

  def testCalibrationConfig(self):
    with TemporaryFileWithData(calibration_config) as tempfile:
      system = FakeBenchmarkSystem(tempfile.name)

      self.assertFalse(system.subjects)
      self.assertTrue(system.led_calibration_subject)
      self.assertEqual(system.led_calibration_subject._dut_backend.name,
                       "backend_name")

  def testOpenSubjectReset(self):
    with TemporaryFileWithData(simple_config) as tempfile:
      system = FakeBenchmarkSystem(tempfile.name)

      subject = system.subjects["device1/clank"]
      subject.Open(safe=False)
      subject.OpenPage("Tap")

      self.assertTrue(subject._is_open)
      self.assertEqual(subject._current_page, "Tap")

      system.Cleanup()

      self.assertFalse(subject._is_open)
      self.assertEqual(subject._current_page, None)

  def testFakeSystem(self):
    fake_system = FakeBenchmarkSystem(None)
    self.assertTrue(fake_system.fake_subject)
    self.assertTrue(fake_system.subjects["any_dut_name/any_subject_name"])

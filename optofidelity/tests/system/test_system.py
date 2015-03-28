# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for BenchmarkSystem."""

from mock import patch
from tempfile import NamedTemporaryFile
import unittest2

from optofidelity.system._fake_backend import FakeDUTBackend
from optofidelity.system.system import BenchmarkSystem
from optofidelity.system.fake import FakeBenchmarkSystem

simple_config = """\
<optofidelity>
  <dut name="device1">
    <subject name="clank" margin="(0, 50)" icon="dummy.shp" />
  </dut>
  <dut name="device2" tnt_name="tnt_name">
    <subject name="clank" margin="(50, 0)"  icon="dummy.shp" />
  </dut>
</optofidelity>
"""

subject_type_config = """\
<optofidelity>
  <subject-type type-name="clank_tablet" name="clank" margin="(100, 0)" />
  <subject-type type-name="clank_phone" name="clank" margin="(0, 50)" />

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


class RobotTests(unittest2.TestCase):

  def test_simple_config(self):
    with TemporaryFileWithData(simple_config) as tempfile:
      system = BenchmarkSystem(tempfile.name, fake_backend=True)

      self.assertIn("device1/clank", system.subjects)
      self.assertIn("device2/clank", system.subjects)
      subject1 = system.subjects["device1/clank"]
      subject2 = system.subjects["device2/clank"]

      height = subject1._backend.height
      margin = 50
      self.assertAlmostEqual(subject1.top, 0)
      self.assertAlmostEqual(subject1.bottom, height - margin)
      self.assertAlmostEqual(subject2.top, margin)
      self.assertAlmostEqual(subject2.bottom, height)

  def test_subject_type_config(self):
    with TemporaryFileWithData(subject_type_config) as tempfile:
      system = BenchmarkSystem(tempfile.name, fake_backend=True)

      self.assertIn("some_phone/clank", system.subjects)
      self.assertIn("some_tablet/clank", system.subjects)
      phone_subject = system.subjects["some_phone/clank"]
      tablet_subject = system.subjects["some_tablet/clank"]

      height = phone_subject._backend.height
      phone_margin = 50
      tablet_margin = 100
      self.assertAlmostEqual(phone_subject.top, 0)
      self.assertAlmostEqual(phone_subject.bottom, height - phone_margin)
      self.assertAlmostEqual(tablet_subject.top, tablet_margin)
      self.assertAlmostEqual(tablet_subject.bottom, height)

      self.assertEqual(phone_subject._backend.name, "tnt_id")
      self.assertEqual(tablet_subject._backend.name, tablet_subject.dut_name)

  def test_calibration_config(self):
    with TemporaryFileWithData(calibration_config) as tempfile:
      system = BenchmarkSystem(tempfile.name, fake_backend=True)

      self.assertFalse(system.subjects)
      self.assertTrue(system.led_calibration_subject)
      self.assertEqual(system.led_calibration_subject._backend.name,
                       "backend_name")

  def test_open_subject_reset(self):
    with TemporaryFileWithData(simple_config) as tempfile:
      system = BenchmarkSystem(tempfile.name, fake_backend=True)

      subject = system.subjects["device1/clank"]
      subject.Open(safe=False)
      subject.OpenPage("Tap")

      self.assertTrue(subject._is_open)
      self.assertEqual(subject._current_page, "Tap")

      system.Cleanup()

      self.assertFalse(subject._is_open)
      self.assertEqual(subject._current_page, None)

  @patch.object(FakeDUTBackend, "DetectWords")
  @patch.object(FakeDUTBackend, "DetectIcon")
  def test_state_restoration(self, icon_mock, words_mock):
    icon_mock.return_value = (1.0, 1.0)
    words_mock.return_value = {"Tap": (1.0, 1.0)}

    with TemporaryFileWithData(simple_config) as tempfile:
      system = BenchmarkSystem(tempfile.name, fake_backend=True)

      # Open subject and a page once to invoke detection.
      subject = system.subjects["device1/clank"]
      subject.Open(safe=False)
      subject.OpenPage("Tap")
      system.Cleanup()

      # DetectIcon and DetectWords on the backend should have been called once.
      self.assertEqual(icon_mock.call_count, 1)
      self.assertEqual(words_mock.call_count, 1)
      icon_mock.reset_mock()
      words_mock.reset_mock()

      # Save state, then re-create BenchmarkSystem
      with NamedTemporaryFile() as state_tempfile:
        system.SaveState(state_tempfile.name)

        system = BenchmarkSystem(tempfile.name, fake_backend=True)
        system.LoadState(state_tempfile.name)

      # Open subject and a page again. Detection should be skipped.
      subject = system.subjects["device1/clank"]
      subject.Open(safe=False)
      subject.OpenPage("Tap")

      self.assertEqual(icon_mock.call_count, 0)
      self.assertEqual(words_mock.call_count, 0)

  def test_fake_system(self):
    fake_system = FakeBenchmarkSystem()
    self.assertEqual(len(fake_system.subjects), 1)
    self.assertTrue(fake_system.subjects["fake_dut/fake_subject"])

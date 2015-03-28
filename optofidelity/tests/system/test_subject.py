# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for BenchmarkSubject."""

from unittest import TestCase

import numpy as np

from mock import PropertyMock, patch
from optofidelity.system._fake_backend import (FakeDUTBackend,
                                               FakeHighSpeedCamera,
                                               FakeRobotBackend)
from optofidelity.system.subject import BenchmarkSubject


class SubjectTests(TestCase):
  def create_subject(self):
    robot_backend = FakeRobotBackend()
    dut_backend = robot_backend.GetDUTBackend("test")
    camera = FakeHighSpeedCamera()
    config = dict(icon="test.shp", margin=(0, 0))
    return BenchmarkSubject("test", "test", dut_backend, camera, config)

  def assert_series_of_taps(self, tap_mock, *args):
    arguments = [(coords,) for coords in args]
    self.assertEqual(tap_mock.call_args_list, arguments)
    tap_mock.reset_mock()

  @patch.object(FakeDUTBackend, "DetectIcon")
  @patch.object(FakeDUTBackend, "Tap")
  def test_opening_closing(self, tap_mock, detect_icon_mock):
    def assert_series_of_taps(*args):
      self.assert_series_of_taps(tap_mock, *args)
    def assert_called_icon_detection():
      detect_icon_mock.assert_called_with("test.shp")
      detect_icon_mock.reset_mock()
    def assert_did_not_call_icon_detection():
      self.assertEqual(detect_icon_mock.call_count, 0)

    subject = self.create_subject()

    home = subject._home_button_coords
    back = subject._back_button_coords
    app_icon = (42.0, 42.0)
    detect_icon_mock.return_value = app_icon

    # Open and close app. Should detect icon.
    subject.Open(safe=False)
    assert_series_of_taps(home, app_icon)
    assert_called_icon_detection()
    subject.Close()
    assert_series_of_taps(back)

    # Open again. Should not detect icon.
    subject.Open(safe=False)
    assert_series_of_taps(home, app_icon)
    assert_did_not_call_icon_detection()
    subject.Close()
    assert_series_of_taps(back)

    # Open in safe mode. Forces icon detection and reset
    subject.Open(safe=True)
    assert_series_of_taps(app_icon, back, back, home, app_icon)
    assert_called_icon_detection()

  def test_open_close_state(self):
    subject = self.create_subject()

    # Can't close without opening first.
    self.assertRaises(Exception, lambda: subject.Close())

    subject.Open(safe=False)

    # Can't open app without closing first.
    self.assertRaises(Exception, lambda: subject.Open(safe=False))

    subject.Reset()

    # Can open again.
    subject.Open(safe=False)

  @patch.object(FakeDUTBackend, "DetectIcon")
  def test_failing_icon_detection(self, detect_icon_mock):
    # Make icon detection fail. Open should fail.
    detect_icon_mock.return_value = None
    subject = self.create_subject()
    ret = subject.Open(safe=False)
    self.assertEqual(ret, False)

    ret = subject.Open(safe=True)
    self.assertEqual(ret, False)

  @patch.object(FakeDUTBackend, "DetectWords")
  @patch.object(FakeDUTBackend, "Tap")
  def test_page_open_close(self, tap_mock, detect_words_mock):
    def assert_series_of_taps(*args):
      self.assert_series_of_taps(tap_mock, *args)
    def assert_called_word_detection():
      self.assertEqual(detect_words_mock.call_count, 1)
      detect_words_mock.reset_mock()
    def assert_did_not_call_word_detection():
      self.assertEqual(detect_words_mock.call_count, 0)

    subject = self.create_subject()
    back = subject._back_button_coords
    tap_button = (1.0, 1.0)

    detect_words_mock.return_value = {"Tap": tap_button}

    subject.Open(safe=False)
    tap_mock.reset_mock()

    subject.OpenPage("Tap")
    assert_series_of_taps(tap_button)
    assert_called_word_detection()
    subject.ClosePage()
    assert_series_of_taps(back)
    subject.Close()

    subject.Open(safe=False)
    subject.OpenPage("Tap")
    assert_did_not_call_word_detection()
    subject.ClosePage()
    subject.Close()

    subject.Open(safe=True)
    subject.OpenPage("Tap")
    assert_called_word_detection()
    subject.ClosePage()

  @patch.object(FakeDUTBackend, "DetectWords")
  def test_failing_word_detection(self, detect_words_mock):
    subject = self.create_subject()
    tap_button = (1.0, 1.0)
    detect_words_mock.return_value = {"Tap": tap_button, "Scroll": None}

    # Make word detection fail on "Scroll". Should return False
    subject = self.create_subject()
    subject.Open(safe=False)
    self.assertEqual(subject.OpenPage("Scroll"), False)
    self.assertEqual(subject.OpenPage("Tap"), True)

  def test_page_open_close_state(self):
    subject = self.create_subject()

    self.assertRaises(Exception, lambda: subject.OpenPage())
    self.assertRaises(Exception, lambda: subject.ClosePage())

    subject.Open(safe=False)
    subject.OpenPage("Tap")
    self.assertRaises(Exception, lambda: subject.OpenPage("Scroll"))
    subject.ClosePage()
    self.assertRaises(Exception, lambda: subject.ClosePage())
    subject.OpenPage("Tap")
    subject.Reset()

    self.assertRaises(Exception, lambda: subject.OpenPage())
    self.assertRaises(Exception, lambda: subject.ClosePage())

  @patch.object(FakeDUTBackend, "orientation", new_callable=PropertyMock)
  def test_plane_calculation(self, orientation_mock):
    orientation_mock.return_value = np.pi / 2 + 0.1
    subject = self.create_subject()
    self.assertLess(subject._test_plane, subject.width / 2)

    orientation_mock.return_value = np.pi / 2 * 3 - 0.1
    subject = self.create_subject()
    self.assertGreater(subject._test_plane, subject.width / 2)

    orientation_mock.return_value = 0
    self.assertRaises(Exception, lambda: self.create_subject())

  @patch.object(FakeDUTBackend, "Jump")
  def test_safe_movement_via_jumping(self, jump_mock):
    def assert_jump_called_once():
      self.assertEqual(jump_mock.call_count, 1)
      jump_mock.reset_mock()
    def assert_jump_not_called():
      self.assertEqual(jump_mock.call_count, 0)

    # Move to a location outside of the DUT.
    subject = self.create_subject()
    subject.Move(-10.0, -10.0, 10.0)
    assert_jump_not_called()

    # Tap should savely move to device by jumping there.
    subject.Tap(10.0, 10.0)
    assert_jump_called_once()

    # No jumping since we are already over the device.
    subject.Tap(20.0, 20.0)
    assert_jump_not_called()

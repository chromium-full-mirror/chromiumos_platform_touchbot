# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for BenchmarkSubject."""

from unittest import TestCase

import numpy as np

from optofidelity.system._fake_backend import FakeRobotBackend
from optofidelity.system._navigators import RobotNavigator
from optofidelity.system.fake import FakeHighSpeedCamera
from optofidelity.system.subject import BenchmarkSubject

class SubjectTests(TestCase):
  def setUp(self):
    self.robot_backend = FakeRobotBackend()
    self.dut_backend = self.robot_backend.GetDUTBackend("test")
    self.camera = FakeHighSpeedCamera()
    self.nav_backend = RobotNavigator(self.dut_backend, "test.shp")

  def createSubject(self):
    return BenchmarkSubject("test", "test", self.dut_backend, self.nav_backend,
                            None, self.camera, (0.0, 0.0))

  def assertSeriesOfTaps(self, *expected_taps):
    taps = [(args[0], args[1]) for cmd, args in self.dut_backend._commands
                               if cmd == "Tap"]
    self.assertEqual(list(expected_taps), taps)

  def assertCommandExecuted(self, command):
    commands = [cmd for cmd, args in self.dut_backend._commands]
    self.assertIn(command, commands)

  def assertCommandNotExecuted(self, command):
    commands = [cmd for cmd, args in self.dut_backend._commands]
    self.assertNotIn(command, commands)

  def resetCommands(self):
    self.dut_backend._commands = []

  def testOpeningClosing(self):
    subject = self.createSubject()

    home = self.nav_backend._home_button_coords
    back = self.nav_backend._back_button_coords
    app_icon = (42.0, 42.0)
    self.dut_backend._detect_icon_rval = app_icon

    # Open and close app. Should detect icon.
    subject.Open(safe=False)
    subject.Close()
    self.assertSeriesOfTaps(home, app_icon, back)
    self.assertCommandExecuted("DetectIcon")
    self.resetCommands()

    # Open again. Should not detect icon.
    subject.Open(safe=False)
    subject.Close()
    self.assertSeriesOfTaps(home, app_icon, back)
    self.assertCommandNotExecuted("DetectIcon")
    self.resetCommands()

    # Open in safe mode. Forces icon detection and reset
    subject.Open(safe=True)
    self.assertSeriesOfTaps(app_icon, back, back, home, app_icon)
    self.assertCommandExecuted("DetectIcon")
    self.resetCommands()

  def testOpenCloseState(self):
    subject = self.createSubject()

    # Can't close without opening first.
    self.assertRaises(Exception, lambda: subject.Close())

    subject.Open(safe=False)

    # Can't open app without closing first.
    self.assertRaises(Exception, lambda: subject.Open(safe=False))

    subject.Reset()

    # Can open again.
    subject.Open(safe=False)

  def testFailingIconDetection(self):
    # Make icon detection fail. Open should fail.
    self.dut_backend._detect_icon_rval = None

    subject = self.createSubject()
    self.assertRaises(Exception, lambda: subject.Open(safe=False))
    self.assertRaises(Exception, lambda: subject.Open(safe=True))

  def testPageOpenClose(self):
    subject = self.createSubject()
    back = self.nav_backend._back_button_coords
    tap_button = (1.0, 1.0)
    self.dut_backend._detect_words_rval = tap_button

    subject.Open(safe=False)
    self.resetCommands()

    subject.OpenPage("Tap")
    subject.ClosePage()
    self.assertSeriesOfTaps(tap_button, back)
    self.assertCommandExecuted("DetectWords")
    self.resetCommands()

    subject.OpenPage("Tap")
    subject.ClosePage()
    subject.Close()
    self.assertCommandNotExecuted("DetectWords")
    self.resetCommands()

    subject.Open(safe=True)
    subject.OpenPage("Tap")
    subject.ClosePage()
    self.assertCommandExecuted("DetectWords")
    self.resetCommands()

  def testFailingWordDetection(self):
    subject = self.createSubject()
    self.dut_backend._detect_words_rval = None

    subject = self.createSubject()
    subject.Open(safe=False)
    self.assertRaises(Exception, lambda: subject.OpenPage("Scroll"))
    self.assertRaises(Exception, lambda: subject.OpenPage("Tap"))

  def testPageOpenCloseState(self):
    subject = self.createSubject()

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

  def testPlaneCalculation(self):
    self.dut_backend._orientation = np.pi / 2 + 0.1
    subject = self.createSubject()
    self.assertLess(subject._test_plane, subject.width / 2)

    self.dut_backend._orientation = np.pi / 2 * 3 - 0.1
    subject = self.createSubject()
    self.assertGreater(subject._test_plane, subject.width / 2)

    self.dut_backend._orientation = 0
    self.assertRaises(Exception, lambda: self.createSubject())


  def testSafeMovementViaJumping(self):
    # Move to a location outside of the DUT.
    subject = self.createSubject()
    subject.Move(-10.0, -10.0, 10.0)
    self.resetCommands()

    # Tap should savely move to device by jumping there.
    subject.Tap(10.0, 10.0)
    self.assertCommandExecuted("Jump")
    self.resetCommands()

    # No jumping since we are already over the device.
    subject.Tap(20.0, 20.0)
    self.assertCommandNotExecuted("Jump")
    self.resetCommands()

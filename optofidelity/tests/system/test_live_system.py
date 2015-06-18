# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for BenchmarkSystem using a live connection to the robot."""

from tempfile import NamedTemporaryFile
import unittest

from optofidelity.system import BenchmarkSystem

ROBOT_IP = None

class SystemTests(unittest.TestCase):

  def setUp(self):
    if ROBOT_IP is None:
      self.skipTest("This test requires ROBOT_IP to be set.")

  def createSystem(self):
    system = BenchmarkSystem()
    system.backend = TnTRobotBackend(ROBOT_IP)
    dut_backend = system.backend.GetDUTBackend("nexus5")
    system.subjects["nexus5"] = BenchmarkSubject("nexus5", "test", dut_backend,
                                                 None, None, None, (0.0, 0.0))
    return system

  def test_simple_interaction(self):
    print "The robot should tap the corners of the device."
    system = self.createSystem()
    subject = system.subjects["nexus5/clank"]

    subject.Tap(subject.left, subject.top)
    subject.Tap(subject.right, subject.top)
    subject.Tap(subject.right, subject.bottom)
    subject.Tap(subject.left, subject.bottom)

  def test_reset(self):
    print "The robot should perform a reset to the homescreen."
    system = self.createSystem()
    system = BenchmarkSystem(tempfile.name)
    system.Reset()

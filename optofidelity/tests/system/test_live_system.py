# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for BenchmarkSystem using a live connection to the robot."""

from tempfile import NamedTemporaryFile
import unittest

from optofidelity.system.system import BenchmarkSystem


ROBOT_IP = None
CAMERA_IP = None

simple_config = """\
<optofidelity>
  <robot host="%s" />
  <camera host="%s" />

  <dut name="nexus5">
    <subject name="clank" margin="(0, 0)" icon="icons/clank_tests.shm" />
  </dut>
</optofidelity>
""" % (ROBOT_IP, CAMERA_IP)


def TemporaryFileWithData(data):
  tempfile = NamedTemporaryFile()
  tempfile.write(data)
  tempfile.flush()
  return tempfile


class SystemTests(unittest.TestCase):

  def setUp(self):
    if CAMERA_IP is None or ROBOT_IP is None:
      self.skipTest("This test requires CAMERA_IP and ROBOT_IP to be set.")

  def test_simple_interaction(self):
    print "The robot should tap the corners of the device."
    with TemporaryFileWithData(simple_config) as tempfile:
      system = BenchmarkSystem(tempfile.name)
      subject = system.subjects["nexus5/clank"]

      subject.Tap(subject.left, subject.top)
      subject.Tap(subject.right, subject.top)
      subject.Tap(subject.right, subject.bottom)
      subject.Tap(subject.left, subject.bottom)

  def test_navigation(self):
    print "The robot should open the tap page then close chrome."
    with TemporaryFileWithData(simple_config) as tempfile:
      system = BenchmarkSystem(tempfile.name)
      subject = system.subjects["nexus5/clank"]

      subject.Open(safe=False)
      subject.OpenPage("Tap")
      subject.ClosePage()
      subject.Close()

  def test_reset(self):
    print "The robot should perform a reset to the homescreen."
    with TemporaryFileWithData(simple_config) as tempfile:
      system = BenchmarkSystem(tempfile.name)
      system.Reset()

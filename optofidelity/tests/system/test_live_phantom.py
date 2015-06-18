# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for Phantom camera using a live connection to the camera."""

import unittest

from optofidelity.system.camera_phantom import PhantomCamera


class PhantomTests(unittest.TestCase):
  CAMERA_IP = None
  CAMERA_PORT = 7115

  def setUp(self):
    if self.CAMERA_IP is None:
      self.skipTest("This test requires CAMERA_IP to be set.")

  def test_recording(self):
    camera = PhantomCamera(self.CAMERA_IP, self.CAMERA_PORT, 300)
    camera.Prepare(1000, 100)
    camera.Trigger()
    video = camera.ReceiveVideo()
    self.assertEqual(video.num_frames, 100)
    self.assertEqual(video.fps, 100)

    print "Please verify that the recorded video is correct"
    video.DebugView()

  def test_state_checking(self):
    camera = PhantomCamera(self.CAMERA_IP, self.CAMERA_PORT, 300)
    self.assertRaises(Exception, lambda: camera.Trigger())
    self.assertRaises(Exception, lambda: camera.ReceiveVideo())

    # Too many frames
    self.assertRaises(Exception, lambda: camera.Prepare(10000))

    # Can't receive video without triggering
    camera.Prepare(1000)
    self.assertRaises(Exception, lambda: camera.ReceiveVideo())

    # Can trigger multiple times or prepare multiple times
    camera.Trigger()
    camera.Trigger()
    camera.Prepare(1000)
    camera.Prepare(1000)

    # Still can't receive video before trigger.
    self.assertRaises(Exception, lambda: camera.ReceiveVideo())

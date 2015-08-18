# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for Phantom and XiCam cameras using a live connection to the
cameras. Tests will be skipped if no cameras are present."""

import unittest

import cv2

from optofidelity.system.camera_phantom import PhantomCamera
from optofidelity.system.camera_xiCam import XiCamCamera
from tests.config import CONFIG

try:
  import optofidelity.system.xiCam as xiCam
except ImportError:
  xiCam = None

class CameraTester(object):
  TEST_DUR = 1000
  TEST_FPS = 100
  BAD_FPS = 10000

  def recording(self, test, camera):
    camera.Prepare(self.TEST_DUR, self.TEST_FPS)
    camera.Trigger()
    video = camera.ReceiveVideo()
    test.assertEqual(video.num_frames, (self.TEST_DUR / 1000) * self.TEST_FPS)
    test.assertEqual(video.fps, self.TEST_FPS)
    return video

  def state_check(self, test, camera):
    test.assertRaises(Exception, lambda: camera.Trigger())
    test.assertRaises(Exception, lambda: camera.ReceiveVideo())

    # Too many frames
    test.assertRaises(Exception, lambda: camera.Prepare(self.BAD_FPS))

    # Can't receive video without triggering
    camera.Prepare(self.TEST_DUR)
    test.assertRaises(Exception, lambda: camera.ReceiveVideo())

    # Can trigger multiple times or prepare multiple times
    camera.Trigger()
    camera.Trigger()
    camera.Prepare(self.TEST_DUR)


class PhantomTests(unittest.TestCase):
  CAMERA_PORT = 7115
  TEST_FPS = 300

  def setUp(self):
    self.camera = PhantomCamera(CONFIG["phantom_ip"], self.CAMERA_PORT,
                                self.TEST_FPS)
    self.tester = CameraTester()

  def test_recording(self):
    video = self.tester.recording(self, self.camera)
    if CONFIG.get("user_interaction"):
      for i, img in video.Frames():
        cv2.imshow("Phantom Unit Test", img)
        cv2.waitKey(1)

  def test_state_checking(self):
    self.tester.state_check(self, self.camera)


class XiCamTests(unittest.TestCase):
  TEST_FPS = 300
  TEST_EXP = 3200
  TEST_GAIN = 3.5

  def setUp(self):
    if xiCam is None or xiCam.cameras() < 1:
      self.skipTest("This test requires a conected xiCam camera.")
    else:
      self.camera = XiCamCamera(self.TEST_FPS, self.TEST_EXP, self.TEST_GAIN)
      self.tester = CameraTester()

  def test_recording(self):
    video = self.tester.recording(self, self.camera)
    if CONFIG.get("user_interaction"):
      for i, img in video.Frames():
        cv2.imshow("XiCam Unit Test", img)
        cv2.waitKey(1)

  def test_state_checking(self):
    self.tester.state_check(self, self.camera)

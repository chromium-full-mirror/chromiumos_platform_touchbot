# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Abstract base class for all detector tests."""

from unittest import TestCase

import numpy as np

from optofidelity.detection._calibrated_frame import CalibratedFrame
from optofidelity.detection._detector import DetectorDebugger
from optofidelity.detection.screen_calibration import ScreenCalibration
from optofidelity.videoproc import Canvas, ImageMatches

from . import test_data


class DetectorTest(TestCase):
  @property
  def calibration(self):
    return ScreenCalibration(test_data.CalibrationBlackImage(),
                             test_data.CalibrationWhiteImage())

  def calibratedFrame(self, image_name, prev_image_name=None, calibration=None):
    image = test_data.LoadImage(image_name)
    prev_image = None
    if prev_image_name:
      prev_image = test_data.LoadImage(prev_image_name)
    calibration = calibration or self.calibration
    return CalibratedFrame(image, prev_image, calibration, 0)

  def uncalibratedFrame(self, image_name, prev_image_name=None):
    image = test_data.LoadImage(image_name)
    prev_image = None
    if prev_image_name:
        prev_image = test_data.LoadImage(prev_image_name)
    return CalibratedFrame(image, prev_image, None, 0)

  def assertExpectedEventsGenerated(self, detector, data_sequence,
                                    expected_events, print_only=False):
    events = list(detector.GenerateEvents(data_sequence))
    if print_only:
      print events
      return

    self.assertEqual(len(events), len(expected_events))
    for event in events:
      expected = next((e for e in expected_events
                         if e.time == event.time), None)
      if expected is None:
        self.fail("Did not expect event: %s" % event)
      self.assertAlmostEqual(event.location, expected.location)
      self.assertEqual(event.time, expected.time)
      self.assertEqual(event.start_time, expected.start_time)
      self.assertEqual(event.state, expected.state)


class DebuggerTests(DetectorTest):
  def composeExampleDebugView(self, debug_flags):
    debugger = DetectorDebugger(self.calibration, debug_flags)
    frame = self.calibratedFrame("finger.png")

    mask = (frame.screen_space_normalized < 0.5)
    debugger.screen_space_canvas.DrawMask(Canvas.GREEN, mask)

    half_height = frame.camera_space_shape[0] / 2
    half_width = frame.camera_space_shape[1] / 2
    debugger.camera_space_canvas.DrawHLine(Canvas.BLUE, half_height)
    debugger.camera_space_canvas.DrawVLine(Canvas.BLUE, half_width)

    profile = np.mean(frame.screen_space_normalized, 0)
    debugger.screen_space_canvas.PlotProfile(Canvas.RED, profile)

    return debugger.ComposeDebugFrame(frame)

  def testDebuggerNormalizedCompose(self):
    expected_image_path = test_data.Path("debugger_normalized.png")
    actual = self.composeExampleDebugView(["normalized"])
    self.assertTrue(ImageMatches(actual, expected_image_path))

  def testDebuggerCameraSpaceCompose(self):
    expected_image_path = test_data.Path("debugger_camera_space.png")
    actual = self.composeExampleDebugView([])
    self.assertTrue(ImageMatches(actual, expected_image_path))
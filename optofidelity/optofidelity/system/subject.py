# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of the BenchmarkSubject class."""

from abc import abstractmethod, abstractproperty

from safetynet import (Any, Dict, InterfaceMeta, List, Optional, Tuple,
                       TypecheckMeta)
import numpy as np

from optofidelity.util import const_property
from optofidelity.videoproc import VideoReader

from .backend import DUTBackend
from .camera import HighSpeedCamera
from .navigator import Navigator


class BenchmarkSubject(object):
  """A BenchmarkSubject is the robot systems view of an app running on a DUT.

  This class provides the functionality to navigate this app, to Open it and
  to navigate to it's activities.

  It provides a way to perform gestures on this app. All gesture methods have a
  variant that operates on a plane in the X-Axis. This plane will intersect
  the device along the edge that is facing away from the high speed camera.

  The subject also provides access to the HighspeedCamera that is responsible for
  recording this device.
  """
  __metaclass__ = TypecheckMeta

  ORIENTATION_THRESHOLD = 0.5
  """Threshold by how much a devices orientation is allowed to deviate from
     right angles."""

  HOVER_HEIGHT = 10.0
  """Height on the Z-axis at which to hover between gestures."""

  CALIBRATION_ACTIVITY = "calibration"
  """Name of activity to use for screen calibration."""

  def __init__(self, name, dut_backend, camera):
    """
    :type name: str
    :type dut_backend: DUTBackend
    :type camera: HighSpeedCamera
    :param Tuple[float, float] margin: margin at top and bottom of the device.
    """
    self.name = name
    self.camera = camera
    self.exposure = None
    self.navigator = None
    self.access = None
    self.margin = (0.0, 0.0)
    self.test_plane_location = 0.2
    self._dut_backend = dut_backend

  @const_property
  def test_plane(self):
    def is_oriented(orientation, target):
      dist = np.abs(orientation - target)
      dist = min(dist, (2 * np.pi) - dist)
      return dist < self.ORIENTATION_THRESHOLD

    abs_test_plane_location = self.test_plane_location * self.width
    orientation = self._dut_backend.orientation
    if is_oriented(orientation, np.pi / 2):
      return abs_test_plane_location
    elif is_oriented(orientation, np.pi / 2 * 3):
      return self.width - abs_test_plane_location
    else:
      raise Exception("DUTs need to be oriented at 90 or 270 degrees.")

  @const_property
  def top(self):
    return self.margin[0]

  @const_property
  def left(self):
    return 0

  @const_property
  def bottom(self):
    return self._dut_backend.height - self.margin[1]

  @const_property
  def right(self):
    return self._dut_backend.width

  @property
  def state(self):
    return {
      "navigator": self.navigator.state if self.navigator else {}
    }

  @state.setter
  def state(self, value):
    if self.navigator:
      self.navigator.state = value["navigator"]

  @property
  def width(self):
    """Width of the subjects area along the devices X-Axis."""
    return self.right - self.left

  @property
  def height(self):
    """Height of the subjects area along the devices Y-Axis."""
    return self.bottom - self.top

  def WaitForGesturesToFinish(self):
    """Blocks until all gestures are finished."""
    self._dut_backend.WaitForGesturesToFinish()

  def Tap(self, x, y, count=1, blocking=True):
    """Tap at location (x, y).

    :param float x
    :param float y
    :param bool blocking: Block until the gesture is finished (default).
    """
    self._SavelyMoveToDevice(x, y, self.HOVER_HEIGHT)
    self._dut_backend.Tap(x, y, count=count)
    if blocking:
      self._dut_backend.WaitForGesturesToFinish()

  def TapOnTestPlane(self, y, count=1, blocking=True):
    """Tap on test-plane to location y

    :param float y
    :param bool blocking: Block until the gesture is finished (default).
    """
    self.Tap(self.test_plane, y, count, blocking)

  def Move(self, x, y, z, blocking=True):
    """Move to location (x, y, z).

    :param float x
    :param float y
    :param float z
    :param bool blocking: Block until the gesture is finished (default).
    """
    self._SavelyMoveToDevice(x, y, z)
    self._dut_backend.Move(x, y, z)
    if blocking:
      self._dut_backend.WaitForGesturesToFinish()

  def MoveOnTestPlane(self, y, z, blocking=True):
    """Move on test-plane to location (y, z).

    :param float y
    :param float z
    :param bool blocking: Block until the gesture is finished (default).
    """
    self.Move(self.test_plane, y, z)

  def MoveRobotOutOfCameraView(self, blocking=True):
    self.MoveOnTestPlane(-10.0, self.HOVER_HEIGHT, blocking)

  def Jump(self, x, y, z, blocking=True):
    """Jump to location (x, y, z).

    A jump will lift the finger before moving to a new location. This is
    necessary for moving safely between devices.

    :param float x
    :param float y
    :param float z
    :param bool blocking: Block until the gesture is finished (default).
    """
    self._dut_backend.Jump(x, y, z)
    if blocking:
      self._dut_backend.WaitForGesturesToFinish()

  def JumpOnTestPlane(self, y, z, blocking=True):
    """Jump on test-plane to location (y, z).

    A jump will lift the finger before moving to a new location. This is
    necessary for moving safely between devices.

    :param float y
    :param float z
    :param bool blocking: Block until the gesture is finished (default).
    """
    self.Jump(self.test_plane, y, z)

  def RecordCalibrationVideo(self):
    """Records a video of the screen flashing, used for calibration.

    The subject has to be opened before using this method.

    :returns VideoReader: A video reader containing the calibration video.
    """
    self.camera.Prepare(1000, exposure=self.exposure)
    self.navigator.OpenActivity(self.CALIBRATION_ACTIVITY)
    try:
      self.MoveRobotOutOfCameraView()
      self.camera.Trigger()
      video = self.camera.ReceiveVideo()
      return video
    finally:
      self.navigator.CloseActivity()

  def _SavelyMoveToDevice(self, target_x, target_y, target_z):
    x, y, _ = self._dut_backend.position
    if (x < 0 or x > self._dut_backend.width or y < 0 or y > self._dut_backend.height):
      self.Jump(target_x, target_y, target_z)

  def _RequireAccess(self):
    if self.access and not self.access.active:
      raise Exception("Access needs to be activated before usage.")

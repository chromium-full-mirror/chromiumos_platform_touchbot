# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of the BenchmarkSubject class."""

from safetynet import Any, Dict, Optional, TypecheckMeta
import numpy as np

from optofidelity.util import const_property
from optofidelity.videoproc import VideoReader

from ._backend import DUTBackend
from .camera import HighSpeedCamera


class BenchmarkSubject(object):
  """A BenchmarkSubject is the robot systems view of an app running on a DUT.

  This class provides the functionality to navigate this app, to Open it and
  to navigate to it's pages.

  It provides a way to perform gestures on this app. All gesture methods have a
  variant that operates on a plane in the X-Axis. This plane will intersect
  the device along the edge that is facing away from the high speed camera.

  The subject also provides access to the HighspeedCamera that is responsible for
  recording this device.
  """
  __metaclass__ = TypecheckMeta
  PAGE_TAP = "Tap"
  PAGE_MOVE = "Move"
  PAGE_SCROLL = "Scroll"
  PAGE_CLICK = "Click"
  PAGE_FLASH = "Flash"

  PAGE_NAMES = [
    PAGE_TAP,
    PAGE_MOVE,
    PAGE_SCROLL,
    PAGE_CLICK,
    PAGE_FLASH
  ]
  """Names of supported pages."""

  TEST_PLANE_MARGIN = 10.0
  """Margin from the edge to keep for 1D line gestures."""

  ORIENTATION_THRESHOLD = 0.5
  """Threshold by how much a devices orientation is allowed to deviate from
     right angles."""

  HOVER_HEIGHT = 10.0
  """Height on the Z-axis at which to hover between gestures."""

  def __init__(self, dut_name, subject_name, dut_backend, camera, config):
    """
    :param str dut_name
    :param str subject_name
    :param DUTBackend dut_backend
    :param HighSpeedCamera camera
    :param Dict[str, Optional[Any]] config: dictionary with additional config
           values taken from the XML file.
    """
    self.name = "{}/{}".format(dut_name, subject_name)
    self.dut_name = dut_name
    self.subject_name = subject_name
    self.camera = camera
    margin = config.get("margin", (0, 0))
    self.app_icon_shape_file = config.get("icon", None)

    self.top = float(margin[0])
    self.left = float(0)
    self.bottom = dut_backend.height - float(margin[1])
    self.right = dut_backend.width

    def is_oriented(orientation, target):
      dist = np.abs(orientation - target)
      dist = min(dist, (2 * np.pi) - dist)
      return dist < self.ORIENTATION_THRESHOLD

    orientation = dut_backend.orientation
    if is_oriented(orientation, np.pi / 2):
      self._test_plane = self.TEST_PLANE_MARGIN
    elif is_oriented(orientation, np.pi / 2 * 3):
      self._test_plane = self.right - self.TEST_PLANE_MARGIN
    else:
      raise Exception("DUTs need to be oriented at 90 or 270 degrees.")

    self._backend = dut_backend

    self._page_button_coords = {}
    self._app_icon_coords = None

    self._is_open = False
    self._current_page = None

  @property
  def state(self):
    return {
      "page_button_coords": self._page_button_coords,
      "app_icon_coords": self._app_icon_coords
    }

  @state.setter
  def state(self, value):
    self._page_button_coords = value["page_button_coords"]
    self._app_icon_coords = value["app_icon_coords"]

  @property
  def width(self):
    """Width of the subjects area along the devices X-Axis."""
    return self.right - self.left

  @property
  def height(self):
    """Height of the subjects area along the devices Y-Axis."""
    return self.bottom - self.top

  def Open(self, safe):
    """Instruct robot to open this subject.

    If the subject has not been opened before, it will use the robots
    integrated camera to detect the application icon. Otherwise it will
    re-use the icon location last detected.

    :param bool safe: Without the safe flag, this interaction is done pretty
           much in the blind, without any error checking.
           Use the safe flag to add additional safety measures and force the
           icon to location to be re-detected.
    """
    if self._is_open:
      raise Exception("Subject already open.")

    if safe:
      self.Reset()
      self._page_button_coords = {}
    else:
      self._backend.Tap(*self._home_button_coords)

    if safe or self._app_icon_coords is None:
      self._app_icon_coords = self._DetectAppIconCoords()
    if self._app_icon_coords is None:
      return False

    self._backend.Tap(*self._app_icon_coords)
    self._is_open = True
    return True

  def Close(self):
    """Closes this subject and returns device to the home screen."""
    if not self._is_open:
      raise Exception("Subject has not been opened.")
    self._backend.Tap(*self._back_button_coords)
    self._is_open = False

  def Reset(self):
    """Attempt to reset the device back to it's home location."""
    if self._app_icon_coords:
      self._backend.Tap(*self._app_icon_coords)
    self._backend.Tap(*self._back_button_coords)
    self._backend.Tap(*self._back_button_coords)
    self._backend.Tap(*self._home_button_coords)
    self._is_open = False
    self._current_page = None

  def Cleanup(self):
    if self._current_page:
      self.ClosePage()
    if self._is_open:
      self.Close()

  def OpenPage(self, page_name):
    """Open a page by it's name.

    Just as Open, this will detect the buttons for each page or re-use the
    coordinates detected previously.

    :param str page_name: Name of the page to open.
    :returns bool: False if the button for this page could not be detected.
    """
    if not self._is_open:
      raise Exception("Can't open page if subject has not been opened.")
    if self._current_page:
      raise Exception("Another page is already open.")
    if page_name not in self.PAGE_NAMES:
      raise ValueError("Unknown page name '%s'" % page_name)

    coords = self._page_button_coords.get(page_name, None)
    if not coords:
      self._page_button_coords = self._DetectPageButtonCoords()
      coords = self._page_button_coords[page_name]
    if not coords:
      return False

    self._backend.Tap(*coords)
    self._current_page = page_name
    return True

  def WaitForGesturesToFinish(self):
    """Blocks until all gestures are finished."""
    self._backend.WaitForGesturesToFinish()

  def ClosePage(self):
    """Close currently opened page."""
    if not self._current_page:
      raise Exception("No page open.")
    self._backend.Tap(*self._back_button_coords)
    self._current_page = None

  def Tap(self, x, y, count=1, blocking=True):
    """Tap at location (x, y).

    :param float x
    :param float y
    :param bool blocking: Block until the gesture is finished (default).
    """
    self._SavelyMoveToDevice(x, y, self.HOVER_HEIGHT)
    self._backend.Tap(x, y, count=count)
    if blocking:
      self._backend.WaitForGesturesToFinish()

  def TapOnTestPlane(self, y, count=1, blocking=True):
    """Tap on test-plane to location y

    :param float y
    :param bool blocking: Block until the gesture is finished (default).
    """
    self.Tap(self._test_plane, y, count, blocking)

  def Move(self, x, y, z, blocking=True):
    """Move to location (x, y, z).

    :param float x
    :param float y
    :param float z
    :param bool blocking: Block until the gesture is finished (default).
    """
    self._SavelyMoveToDevice(x, y, z)
    self._backend.Move(x, y, z)
    if blocking:
      self._backend.WaitForGesturesToFinish()

  def MoveOnTestPlane(self, y, z, blocking=True):
    """Move on test-plane to location (y, z).

    :param float y
    :param float z
    :param bool blocking: Block until the gesture is finished (default).
    """
    self.Move(self._test_plane, y, z)

  def MoveRobotOutOfCameraView(self, blocking=True):
    self.MoveOnTestPlane(-100.0, self.HOVER_HEIGHT, blocking)

  def Jump(self, x, y, z, blocking=True):
    """Jump to location (x, y, z).

    A jump will lift the finger before moving to a new location. This is
    necessary for moving safely between devices.

    :param float x
    :param float y
    :param float z
    :param bool blocking: Block until the gesture is finished (default).
    """
    self._backend.Jump(x, y, z)
    if blocking:
      self._backend.WaitForGesturesToFinish()

  def JumpOnTestPlane(self, y, z, blocking=True):
    """Jump on test-plane to location (y, z).

    A jump will lift the finger before moving to a new location. This is
    necessary for moving safely between devices.

    :param float y
    :param float z
    :param bool blocking: Block until the gesture is finished (default).
    """
    self.Jump(self._test_plane, y, z)

  def RecordCalibrationVideo(self):
    """Records a video of the screen flashing, used for calibration.

    The subject has to be opened before using this method.

    :returns VideoReader: A video reader containing the calibration video.
    """
    self.camera.Prepare(60)
    self.OpenPage(self.PAGE_FLASH)
    self.MoveRobotOutOfCameraView()
    self.camera.Trigger()
    video = self.camera.ReceiveVideo()
    self.ClosePage()
    return video

  def _SavelyMoveToDevice(self, target_x, target_y, target_z):
    x, y, _ = self._backend.position
    if (x < 0 or x > self._backend.width or y < 0 or y > self._backend.height):
      self.Jump(target_x, target_y, target_z)

  def _DetectAppIconCoords(self):
    return self._backend.DetectIcon(self.app_icon_shape_file)

  def _DetectPageButtonCoords(self):
    return self._backend.DetectWords(self.PAGE_NAMES)

  @const_property
  def _back_button_coords(self):
    screen_min_width = 50
    button_distance_scale_factor = 0.75
    button_min_distance = 10
    button_max_distance = 20

    back_location = (button_min_distance + (self.width - screen_min_width) *
                     button_distance_scale_factor)
    back_location = min((back_location, button_max_distance))

    return (float(self.width / 2 - back_location), float(self._backend.height - 3))

  @const_property
  def _home_button_coords(self):
    return (float(self.width / 2), float(self._backend.height - 3))

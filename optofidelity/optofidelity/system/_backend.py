# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Abstract base classes for a backend to execute robot actions."""

from abc import abstractmethod, abstractproperty

from safetynet import Dict, InterfaceMeta, List, Optional, Tuple


class DUTBackend(object):
  __metaclass__ = InterfaceMeta

  @abstractmethod
  def DetectIcon(self, icon_file):
    """Detect an icon on the DUT screen and return it's coordinates.

    :param str icon_file: path to .shp file describing the icon.
    :returns Optional[Tuple[float, float]]: icon coordinates or None if not
             found.
    """

  @abstractmethod
  def DetectWords(self, words):
    """Detect a collection of words on the DUT screen.

    If a word cannot be detected the entry in the returned dict will be None.

    :param List[str] words: List of words to detect.
    :returns Dict[str, Tuple[float, float]]: Dict of coordinates for each word.
    """

  @abstractmethod
  def Tap(self, x, y, count=1):
    """Instructs the robot to tap at the location (x, y).

    :param float x
    :param float y
    """

  @abstractmethod
  def Move(self, x, y, z):
    """Instructs the robot to move to the location (x, y, z).

    :param float x
    :param float y
    :param float z
    """

  @abstractmethod
  def Jump(self, x, y, z):
    """Instructs the robot to jump to the location (x, y).

    A jump will raise the finger before moving to this location, which is
    necessary for safe movement between devices.
    """

  @abstractmethod
  def WaitForGesturesToFinish(self):
    """Blocks until all gestures are finished."""

  @abstractproperty
  def position(self):
    """Current position of the robot finger.

    :returns Tuple[float, float, float]: (x, y, z) coordinates.
    """

  @abstractproperty
  def width(self):
    """Width of the device on the x-Axis.

    :returns float
    """

  @abstractproperty
  def height(self):
    """Height of the device on the y-Axis.

    :returns float
    """

  @abstractproperty
  def orientation(self):
    """Orientation of the device in radians.

    The orientation is measured from your perspective while standing in front
    of the robot tray.
    0:     The device is upright, as in: You can read it's screen.
    pi/2:  The device is facing to the right.
    pi:    The device is upside down.
    3pi/2: The device is facing to the left.
    :returns float
    """


class RobotBackend(object):
  __metaclass__ = InterfaceMeta

  @abstractmethod
  def Reset(self):
    """Reset robot to it's home location."""

  def GetDUTBackend(self, name):
    """Return a DUTBackend instance the specified DUT.

    :param str name: Name of the DUT.
    :returns DUTBackend: Backend for the DUT.
    """

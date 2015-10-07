# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from abc import abstractmethod
import time

from safetynet import TypecheckMeta

from optofidelity.util import ADB, Cambrionix


class Access(object):
  __metaclass__ = TypecheckMeta

  def __init__(self):
    self.active = False

  def Activate(self):
    """Activate access to subject."""
    self.active = True

  def Deactivate(self):
    """Deactivate access to subject."""
    self.active = False

  def __enter__(self):
    self.Activate()

  def __exit__(self, type, value, traceback):
    self.Deactivate()


class FakeAccess(Access):
  @classmethod
  def FromConfig(cls, attributes, children):
    return cls()


class CambrionixAccess(Access):
  ADB_TIMEOUT = 2 * 60
  """Wait for device to connect for 2 minutes."""

  def __init__(self, serial_device, port_id, adb_serial):
    super(CambrionixAccess, self).__init__()
    self.cambrionix = Cambrionix(serial_device)
    self.port_id = port_id
    self.adb = ADB(adb_serial)
    self.adb_serial = adb_serial

  @classmethod
  def FromConfig(cls, attributes, children):
    return cls(attributes["serial"], int(attributes["port"]),
               attributes["adb"])

  def Activate(self):
    if not self.active:
      self.cambrionix.SetPortMode("charge")
      self.cambrionix.SetPortMode("sync", self.port_id)
    super(CambrionixAccess, self).Activate()
    self.adb.WaitForDevice(self.ADB_TIMEOUT)

  def Deactivate(self):
    if self.active:
      self.cambrionix.SetPortMode("charge")
    super(CambrionixAccess, self).Deactivate()

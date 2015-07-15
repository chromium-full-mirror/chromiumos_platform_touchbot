# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from optofidelity.util import ADB

class SubjectPreparer(object):
  def Prepare(self):
    pass

class ADBScreenOffPreparer(SubjectPreparer):
  def __init__(self, adb_device):
    self._adb = ADB(adb_device)

  @classmethod
  def FromConfig(cls, parameters, children):
    return cls(parameters.get("adb"))

  def Prepare(self):
    self._adb.PowerOff()
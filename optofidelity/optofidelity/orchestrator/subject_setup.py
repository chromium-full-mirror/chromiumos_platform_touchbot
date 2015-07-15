# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from optofidelity.util import ADB

class SubjectSetup(object):
  def SetUp(self):
    pass

class ADBSettingsSetup(SubjectSetup):
  def __init__(self, adb_device, settings_dict):
    self._adb = ADB(adb_device)
    self._settings_dict = settings_dict

  @classmethod
  def FromConfig(cls, parameters, children):
    settings_dict = {}
    for child_name, attributes in children:
      name = attributes.get("name")
      value = attributes.get("value")
      if (child_name == "setting" and name and value):
        settings_dict[attributes["name"]] = attributes["value"]
      else:
        raise Exception("Expected name and value attribute in setting element")
    return cls(parameters.get("adb"), settings_dict)

  def SetUp(self):
    for name, value in self._settings_dict.iteritems():
      self._adb.ExecuteShell(["settings", "put", "system", name, value])
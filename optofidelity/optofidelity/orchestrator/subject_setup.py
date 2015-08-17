# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from abc import abstractmethod

from optofidelity.util import ADB

class SubjectSetup(object):
  """Abstract interface for setup steps executed on a subject.

  The setup step is executed via the command line --setup flag. The purpose is
  to set up a new device for usage with the benchmark system.
  """

  @abstractmethod
  def SetUp(self):
    pass


class FakeSubjectSetup(object):
  """Fake implementation that does nothing."""

  @classmethod
  def FromConfig(cls, parameters, children):
    return cls()

  def SetUp(self):
    pass


class ADBSettingsSetup(SubjectSetup):
  """Setup component that sets android system properties via ADB.

  Example config:
  <setup type="adb_settings">
    <setting name="prop.name" value="prop.value" />
  </setup>
  """
  def __init__(self, adb_device, settings_dict):
    self._adb = ADB(adb_device)
    self._settings_dict = settings_dict

  @classmethod
  def FromConfig(cls, parameters, children):
    settings_dict = {}
    for child_name, attributes in children:
      name = attributes.get("name")
      value = attributes.get("value")
      namespace = attributes.get("namespace", "system")
      if (child_name == "setting" and name and value):
        settings_dict[name] = (namespace, value)
      else:
        raise Exception("Expected name and value attribute in setting element")
    return cls(parameters.get("adb"), settings_dict)

  def SetUp(self):
    for name, (namespace, value) in self._settings_dict.iteritems():
      self._adb.PutSetting(namespace, name, value)
# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
import logging

from safetynet import List

from optofidelity.system import BenchmarkSubject
from optofidelity.util import ProgressPrinter

_log = logging.getLogger(__name__)
BenchmarkDefinition = namedtuple("BenchmarkDefinition",
                                 ["name", "benchmark_type", "activity",
                                  "params"])

class OrchestratorSubject(BenchmarkSubject):
  def __init__(self, name, dut_backend, camera):
    super(OrchestratorSubject, self).__init__(name, dut_backend, camera)
    self.benchmark_defs = {}
    self.updater = None
    self.dashboard = None
    self._progress = ProgressPrinter(_log)

  @classmethod
  def FromBenchmarkSubject(cls, other):
    self = cls(other.name, other._dut_backend, other.camera)
    self.__dict__.update(other.__dict__)
    return self

  def DefineBenchmark(self, name, benchmark_type, activity, params):
    self.benchmark_defs[name] = BenchmarkDefinition(name, benchmark_type,
                                                    activity, params)

  def Verify(self):
    """Verify that the subject is accessible and in working order.

    This method should never throw any exceptions.

    :returns bool: True if verification was successful.
    """
    with self._progress.CaptureFailures(self.name, "Subject verification"):
      self.updater.Verify()
      self.navigator.Verify()
      return True
    return False

  def Update(self, version):
    """Update subject to a specific version.

    This method should never throw any exceptions.

    :returns bool: True if the update was successful.
    """
    with self._progress.CaptureFailures(self.name, "Subject update"):
      if version != self.updater.installed_version:
        self.updater.Install(version)
      return True
    return False

  def GetMatchingVersions(self, versions, skip_installed):
    """Generate list of versions matching the versions string.

    :type versions: str
    :type skip_installed: bool
    :returns List[str]: List of matching versions
    :raises Exception: If the updater cannot access the device.
    """
    available_versions = self.updater.available_versions
    installed_version = self.updater.installed_version
    if available_versions:
      versions_to_test = self._ParseVersionRange(versions, installed_version,
                                                 available_versions)
      if skip_installed and versions_to_test[0] == installed_version:
          versions_to_test = versions_to_test[1:]
      return versions_to_test
    elif not skip_installed:
      return [installed_version]
    return []

  @classmethod
  def _ParseVersion(cls, string, installed_version, available_versions):
    string = string.strip()
    if string == "installed":
      if installed_version is None:
        raise Exception("No version installed.")
      return installed_version
    if string == "latest":
      return available_versions[-1]
    else:
      return_last_match = True
      if string.endswith("-"):
        string = string[:-1]
        return_last_match = False
      last_match = None
      for version in available_versions:
        if version.startswith(string):
          if return_last_match:
            last_match = version
          else:
            return version
      if last_match:
        return last_match
      raise Exception("No such version '%s'" % string)

  @classmethod
  def _ParseVersionRange(cls, string, installed_version, available_versions):
    segments = string.split(":")
    if len(segments) == 1:
      return [cls._ParseVersion(string, installed_version, available_versions)]
    elif len(segments) == 2:
      from_version = cls._ParseVersion(segments[0], installed_version,
                                        available_versions)
      to_version = cls._ParseVersion(segments[1], installed_version,
                                      available_versions)
    else:
      raise Exception("Invalid version syntax '%s'" % string)

    version_list = []
    in_range = False
    out_range = False
    for version in available_versions:
      if not in_range and version.startswith(from_version):
          in_range = True

      if in_range:
        if version.startswith(to_version):
          out_range = True
        elif out_range:
          break
        version_list.append(version)
    return version_list

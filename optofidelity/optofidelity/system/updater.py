# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from abc import abstractmethod, abstractproperty
from datetime import datetime
from tempfile import NamedTemporaryFile
import csv
import logging
import subprocess
import urllib2

from safetynet import InterfaceMeta, List, Optional

from optofidelity.util import ProgressBar, const_property

from .adb import ADB

log = logging.getLogger(__name__)


class Updater(object):
  """Interface for a service to update subjects."""
  __metaclass__ = InterfaceMeta

  @abstractproperty
  def available_versions(self):
    """:returns List[str]: List of versions available for install."""

  @abstractproperty
  def installed_version(self):
    """:returns Optional[str]: Currently installed version or None."""

  @abstractmethod
  def GetVersionUID(self, version):
    """:returns int: Unique incrementing integer identifying a version."""

  @abstractmethod
  def Install(self, version):
    """Install specific app version.

    :type version: str
    """

  @abstractmethod
  def Uninstall(self):
    """Uninstall app."""


class ManualUpdater(Updater):
  """Updater that returns a constant version.

  This updater is to be used for devices and subjects that require manual
  updating.
  """
  def __init__(self, version):
    """
    :param Optional[str] version: Version number to report
    """
    self._version = version

  @classmethod
  def FromConfig(cls, attributes, children, dut_backend):
    return cls(attributes["version"])

  @property
  def available_versions(self):
    return []

  @property
  def installed_version(self):
    return self._version

  def GetVersionUID(self, version):
    return 0

  def Install(self, version):
    raise NotImplementedError()

  def Uninstall(self):
    raise NotImplementedError()


class ChromeUpdater(Updater):
  """Updater for stable and beta Chrome app."""

  def __init__(self, adb_device, channel):
    """
    :param str adb_device: USB serial of the device under test.
    :param str channel: stable or beta.
    """
    if channel not in ("stable", "beta"):
      raise ValueError("No such channel '%s'" % channel)

    self._adb = ADB(adb_device)
    self._channel = channel
    if channel == "stable":
      self._package_name = "com.android.chrome"
      self._filename = "ChromeStable.apk"
    elif channel == "beta":
      self._package_name = "com.chrome.beta"
      self._filename = "ChromeBeta.apk"

  @classmethod
  def FromConfig(cls, attributes, children, dut_backend):
    return cls(attributes["adb"], attributes["channel"])

  def GetVersionUID(self, version):
    for uid_version, uid in self._version_db:
      if uid_version == version:
        print version, uid
        return uid
    raise Exception("Unknown version %s" % version)

  @property
  def installed_version(self):
    return self._adb.GetPackageVersion(self._package_name)

  @const_property
  def _version_db(self):
    url = ("https://omahaproxy.appspot.com/history?os=android&channel=%s" %
           self._channel)
    request = urllib2.urlopen(url)
    reader = csv.reader(request)
    versions = []
    for row in reader:
      if row[0] == "os":
        continue
      release_date = datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S.%f")
      timestamp = (release_date - datetime.utcfromtimestamp(0)).total_seconds()
      versions.append((row[2], int(timestamp)))
    return sorted(versions, reverse=True)

  @property
  def available_versions(self):
    return [version for version, uid in self._version_db]

  def Uninstall(self):
    msg = "Uninstalling %s" % self._package_name
    with ProgressBar(msg):
      self._adb.UninstallPackage(self._package_name)

  def Install(self, version):
    with NamedTemporaryFile(suffix=".apk") as apk_tempfile:
      msg = "Downloading APK version %s" % version
      with ProgressBar(msg):
        self._DownloadAPK(version, apk_tempfile.name)

      msg = "Installing APK version %s" % version
      with ProgressBar(msg):
        self._adb.InstallAPK(apk_tempfile.name)

  def _DownloadAPK(self, version, filename):
    """Download specific version of chrome to filename.

    :type version: str
    :type filename: str
    """
    url = "gs://chrome-signed/android-C4MPAR1/%s/arm/%s" % (version,
                                                            self._filename)

    command = ["gsutil", "cp", url, filename]
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    process.communicate()
    if process.returncode > 0:
      raise Exception("'%s' returned with %d" % (" ".join(command),
                                                 process.returncode))

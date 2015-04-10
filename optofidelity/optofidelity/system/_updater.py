# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from tempfile import NamedTemporaryFile
import csv
import logging
import subprocess
import urllib2

from safetynet import Optional

from optofidelity.util import ProgressBar

from ._adb import ADB
from .subject import Updater

log = logging.getLogger(__name__)


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

  @property
  def available_versions(self):
    return []

  @property
  def installed_version(self):
    return self._version

  def Install(self, version):
    raise NotImplementedError()

  def Uninstall(self):
    raise NotImplementedError()


class ChromeUpdater(Updater):
  """Updater for stable and beta Chrome app."""

  def __init__(self, adb_device, channel, print_progress=False):
    """
    :param str adb_device: USB serial of the device under test.
    :param str channel: stable or beta.
    :param bool print_progress: Prints progress of commands to stdout.
    """
    if channel not in ("stable", "beta"):
      raise ValueError("No such channel '%s'" % channel)

    self._adb = ADB(adb_device)
    self._channel = channel
    self._print_progress = print_progress
    if channel == "stable":
      self._package_name = "com.android.chrome"
      self._filename = "ChromeStable.apk"
    elif channel == "beta":
      self._package_name = "com.chrome.beta"
      self._filename = "ChromeBeta.apk"

  @property
  def installed_version(self):
    return self._adb.GetPackageVersion(self._package_name)

  @property
  def available_versions(self):
    request = urllib2.urlopen("https://omahaproxy.appspot.com/history")
    reader = csv.reader(request)
    versions = []
    for row in reader:
      if row[0] == "android" and row[1] == self._channel:
        versions.append(row[2])
    return sorted(versions, reverse=True)

  def Uninstall(self):
    with self._ProgressBar("Uninstalling %s" % self._package_name):
      self._adb.UninstallPackage(self._package_name)

  def Install(self, version):
    with NamedTemporaryFile(suffix=".apk") as apk_tempfile:
      with self._ProgressBar("Downloading APK version %s" % version):
        self._DownloadAPK(version, apk_tempfile.name)
      with self._ProgressBar("Installing APK version %s" % version):
        self._adb.InstallAPK(apk_tempfile.name)

  def _ProgressBar(self, message):
    return ProgressBar(message, suppress=(not self._print_progress))

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

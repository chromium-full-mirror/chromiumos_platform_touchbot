# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import subprocess
import re


class ADB(object):
  """Wrapper around the adb command line tool."""

  def __init__(self, adb_device):
    """
    :param str adb_device: USB serial number of the device to use.
    """
    self.adb_cmd = ["adb", "-s", adb_device]

  def UninstallPackage(self, package_name):
    """Uninstalls package on device.

    :type package_name: str
    """
    self.ExecuteShell(["pm", "uninstall", package_name], check_success=True)

  def InstallAPK(self, apk):
    """Install local apk file onto device

    :param str apk: path to apk file
    """
    self.Execute(["install", "-r", "-d", apk], check_success=True)

  def GetPackageVersion(self, package_name):
    """Returns the version name of an installed package or None

    :type package_name: str
    :returns Optional[str]: version name of package if it is installed
    """
    info = self.ExecuteShell(["pm", "dump", package_name])
    version_regex = re.compile("versionName=(.+)")
    match = version_regex.search(info)
    if match:
      return match.group(1)
    return None

  def Execute(self, sub_command, check_success=False):
    """Execute an adb command.

    Many ADB commands do not return an error code when failing, so we have
    the option to look for a 'success' message, which is usually printed
    after commands.

    :type sub_command: List[str]
    :param bool check_success: Check for 'success' message, raises Exception if
           it was not printed.
    """
    command = self.adb_cmd + sub_command
    process = subprocess.Popen(command, shell=False, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    stdout = process.stdout.read().replace("\r", "").strip()
    if process.returncode > 0:
      print stdout
      raise Exception("'%s' returned with %d" % (" ".join(command),
                                                 process.returncode))
    if check_success and not "Success" in stdout:
      print stdout
      raise Exception("'%s' failed" % (" ".join(command)))
    return stdout

  def ExecuteShell(self, shell_command, check_success=False):
    """Wrapper to execute an adb shell command.

    :type shell_command: List[str]
    :param bool check_success: Check for 'success' message, raises Exception if
           it was not printed.
    """
    return self.Execute(["shell"] + shell_command)
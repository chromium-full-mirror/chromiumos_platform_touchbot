# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import re
import subprocess

from .tools import TimeoutCommunicate

_log = logging.getLogger(__name__)


class ADB(object):
  """Wrapper around the adb command line tool."""
  KEY_POWER = "26"
  KEY_UNLOCK = "82"

  def __init__(self, adb_device):
    """
    :param str adb_device: USB serial number of the device to use.
    """
    self.adb_cmd = ["adb", "-s", adb_device]

  def WaitForDevice(self, timeout=1):
    self.Execute(["wait-for-device"], timeout=timeout)

  def UninstallPackage(self, package_name):
    """Uninstalls package on device.

    :type package_name: str
    """
    self.ExecuteShell(["pm", "uninstall", package_name], check_success=True,
                      timeout=60)

  def InstallAPK(self, apk):
    """Install local apk file onto device

    :param str apk: path to apk file
    """
    self.Execute(["install", "-r", "-d", apk], check_success=True, timeout=120)

  def GetPackageVersion(self, package_name):
    """Returns the version name of an installed package or None

    :type package_name: str
    :returns Optional[str]: version name of package if it is installed
    """
    info = self.ExecuteShell(["pm", "dump", package_name], timeout=20)
    version_regex = re.compile("versionName=(.+)")
    match = version_regex.search(info)
    if match:
      return match.group(1).strip()
    return None

  def PowerOn(self):
    if not self.IsAwake():
      self.SendKey(self.KEY_POWER)
    self.SendKey(self.KEY_UNLOCK)
    self.ExecuteShell(["svc", "power", "stayon", "true"])

  def PowerOff(self):
    self.ExecuteShell(["svc", "power", "stayon", "false"])
    if self.IsAwake():
      self.SendKey(self.KEY_POWER)

  def IsAwake(self):
    power_dump = self.ExecuteShell(["dumpsys", "power"], timeout=20)
    return "mWakefulness=Awake" in power_dump

  def GetProp(self, prop_name):
    """Return 'getprop' property from device.

    Returns None if the property does not exist.
    """
    prop = self.ExecuteShell(["getprop", prop_name]).strip()
    if len(prop):
      return prop
    return None

  def PutSetting(self, namespace, key, value):
    self.ExecuteShell(["settings", "put", namespace, key, value])

  def GetSetting(self, namespace, key):
    stdout = self.ExecuteShell(["settings", "get", namespace, key])
    return stdout.strip()

  def SendKey(self, key_name):
    self.ExecuteShell(["input", "keyevent", key_name], timeout=10, retries=2)

  def PushFile(self, local_file, remote_file):
    self.Execute(["push", local_file, remote_file], timeout=240)

  def StartActivity(self, action=None, component=None, uri=None, category=None,
                    wait=True, force_stop=False):
    """Start an activity via the adb activity manager.

    The parameters are directly passed to the am start command to specify the
    intent to start.
    """
    cmd = ["am", "start"]
    for flag, value in [("-W", wait), ("-S", force_stop)]:
      if value:
        cmd += [flag]

    for flag, value in [("-a", action), ("-n", component),
                        ("-d", uri), ("-c", category)]:
      if value:
        cmd += [flag, value]
    self.ExecuteShell(cmd, check_error=True, timeout=20)

  def Execute(self, sub_command, check_success=False, check_error=False,
              timeout=False, retries=0):
    """Execute an adb command.

    Many ADB commands do not return an error code when failing, so we have
    the option to look for a 'success' message, which is usually printed
    after commands.

    :type sub_command: List[str]
    :param bool check_success: Check for 'success' message, raises Exception if
           it was not printed.
    """
    try:
      command = self.adb_cmd + sub_command
      _log.info("Executing %s", " ".join(command))
      process = subprocess.Popen(command, shell=False, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
      stdout = TimeoutCommunicate(process, timeout)
      error_message = None
      if stdout is False:
        error_message = "'%s' timed out." % (" ".join(command),)
      elif process.returncode > 0:
        error_message = "'%s' returned with %d" % (" ".join(command),
                                                   process.returncode)
      elif ((check_success and not "Success" in stdout) or
            (check_error and "Error" in stdout) or
            (process.returncode > 0)):
        error_message = "'%s' failed" % (" ".join(command))
      if error_message:
        if stdout:
          _log.error(error_message + "\n" + stdout)
        raise Exception(error_message)
      return stdout
    except KeyboardInterrupt:
      raise
    except:
      if retries > 0:
        _log.exception("Retrying command")
        return self.Execute(sub_command, check_success, check_error, timeout,
                            retries - 1)
      raise

  def ExecuteShell(self, shell_command, check_success=False, check_error=False,
                   timeout=False, retries=0):
    """Wrapper to execute an adb shell command.

    :type shell_command: List[str]
    :param bool check_success: Check for 'success' message, raises Exception if
           it was not printed.
    """
    return self.Execute(["shell"] + shell_command, check_success, check_error,
                        timeout, retries)

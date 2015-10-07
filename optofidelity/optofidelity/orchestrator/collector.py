# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from abc import abstractmethod, abstractproperty
from tempfile import NamedTemporaryFile
import logging
import math
import os
import shutil
import subprocess

_log = logging.getLogger(__name__)


class Collector(object):
  """Abstract interface for collecting additional information from DUTs

  The collectors are run during the execution of a benchmark and then saved
  alongside the report.
  """
  @abstractmethod
  def Start(self, duration):
    pass

  @abstractmethod
  def Stop(self):
    pass

  @abstractmethod
  def Save(self, folder):
    pass

  @abstractproperty
  def report_links(self):
    pass

  def __enter__(self):
    self.Start()

  def __exit__(self, type, value, traceback):
    self.Stop()


class FakeCollector(Collector):
  """Fake implementation that does nothing and writes an empty fake.log file."""

  def __init__(self):
    self.started = False
    self.collected = False

  @classmethod
  def FromConfig(cls, parameters, children):
    return cls()

  def Start(self, duration):
    self.started = True

  def Stop(self):
    self.started = False
    self.collected = True

  def Save(self, folder):
    if self.collected:
      open(os.path.join(folder, "fake.log"), "w").close()

  @property
  def report_links(self):
    return [("Fake Log", "fake.log")]


class SystraceCollector(Collector):
  """Collection of Android systraces."""

  def __init__(self, adb_device, sdk_path):
    systrace_script = os.path.join(sdk_path, "platform-tools", "systrace",
                                   "systrace.py")
    self.base_cmd = ["python", systrace_script, "-e", adb_device]
    self.process = None
    self.tempfile = NamedTemporaryFile()

  @classmethod
  def FromConfig(cls, parameters, children):
    return cls(parameters["adb"], parameters["sdk-path"])

  def Start(self, duration):
    seconds = int(math.ceil(float(duration) / 1000.0))
    cmd = self.base_cmd + ["-t", str(seconds), "-o", self.tempfile.name]
    _log.info("Starting: %s", " ".join(cmd))
    self.process = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)

  def Stop(self):
    stdout, stderr = self.process.communicate()
    if self.process.returncode > 0:
      _log.error(stdout)
      _log.error("Systrace failed to collect")
    else:
      _log.debug(stdout)

  def Save(self, folder):
    shutil.copy(self.tempfile.name, os.path.join(folder, "systrace.html"))

  @property
  def report_links(self):
    return [("Systrace", "systrace.html")]


class ChromeProfileCollector(Collector):
  """Collection of Chrome profile traces."""

  def __init__(self, adb_device, chromium_path, browser):
    profile_script = os.path.join(chromium_path, "build", "android",
                                  "adb_profile_chrome")
    self.base_cmd = [profile_script,
                     "-d", adb_device,
                     "--browser", browser,
                     "--systrace", "gfx,view,input,freq,sched"]
    self.process = None
    self.tempfile = NamedTemporaryFile()

  @classmethod
  def FromConfig(cls, parameters, children):
    return cls(parameters["adb"], parameters["chromium-path"],
               parameters["browser"])

  def Start(self, duration):
    seconds = int(math.ceil(float(duration) / 1000.0))
    cmd = self.base_cmd + ["-t", str(seconds), "-o", self.tempfile.name]
    _log.info("Starting: %s", " ".join(cmd))
    self.process = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)

  def Stop(self):
    stdout, stderr = self.process.communicate()
    if self.process.returncode > 0:
      _log.error(stdout)
      _log.error("Systrace failed to collect")
    else:
      _log.debug(stdout)

  def Save(self, folder):
    shutil.copy(self.tempfile.name, os.path.join(folder, "chrome_profile.html"))

  @property
  def report_links(self):
    return [("ChromeProfile", "chrome_profile.html")]
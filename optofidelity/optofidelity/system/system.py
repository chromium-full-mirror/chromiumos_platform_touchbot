# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from ConfigParser import SafeConfigParser
import h5py

from optofidelity.phantom import Phantom
from optofidelity.system.app import ClankTestApp
from optofidelity.system.dut import AndroidDUT
from optofidelity.system.util import RetryFunction
from optofidelity.tnt.TnTClient import TnTClient

class OptofidelityTestSystem(object):
  """Robot system which manages multiple DUTs.

  The system is setup using ReadConfig, followed by either a call to
  Calibrate to run the calibration process, or LoadCalibration to load
  calibration data previously saved using SaveCalibration.

  After the calibration you can access devices by name and execute commands on
  them such as:
    >>> system["Nexus7"].Reset()
    >>> system["Nexus7"].EnterApp("Clank")
  """
  def __init__(self, config_file):
    self.duts = {}
    self.tnt = None
    self.camera = None
    self.ReadConfig(config_file)

  def __getitem__(self, key):
    if isinstance(key, int):
      return self.duts.values().__getitem__(key)
    else:
      return self.duts.__getitem__(key)

  def ReadConfig(self, config_file):
    """Read robot configuration from file.

    The configuration contains a list of DUTs and their properties as follows:
    [DUTName]
    type=Android
    apps=Clank

    The DUTName has to be the name of the DUT on the OptoFidelity system,
    whereas the only supported type at this time is Android, and the only
    supported app is Clank.
    """
    config = SafeConfigParser()
    config.read([config_file])

    host = config.get("robot", "host")
    port = config.get("robot", "port")
    self.tnt = TnTClient(host, port)

    camera_host = config.get("camera", "host")
    self.camera = Phantom(camera_host)

    for dut_name in config.sections():
      if dut_name in ("robot", "camera"):
        continue
      dut_type = config.get(dut_name, "type")
      dut_apps = config.get(dut_name, "apps").split(",")
      dut_apps = [a.strip() for a in dut_apps]
      if dut_type.lower() == "android":
        dut = AndroidDUT(self.tnt, dut_name)
      else:
        raise Exception("Unknown device type %s" % dut_type)

      for app_name in dut_apps:
        if app_name.lower() == "clank":
          app = ClankTestApp(dut)
        else:
          raise Exception("Unknown device type %s" % dut_type)
        dut.RegisterApp(app)
      self.duts[dut.name] = dut

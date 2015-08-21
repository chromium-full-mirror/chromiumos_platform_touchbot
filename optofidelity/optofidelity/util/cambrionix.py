# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from serial import Serial

_log = logging.getLogger(__name__)

class PortStatus(object):
  """Structure to carry status of a port."""

  def __init__(self, status_line):
    """Initialize with a line returned from the status command."""
    # A status line looks like this: 1, 0000, R D S, 0, 0, x, 0.00
    # id, milli amps, flags, profile, time charging, time charged, energy
    parts = status_line.split(",")
    self.id = int(parts[0])
    flags = parts[2]
    if "S" in flags:
      self.mode = "sync"
    elif "O" in flags:
      self.mode = "off"
    else:
      self.mode = "charge"

    self.attached = "A" in flags

  def __str__(self):
    attached = "(attached)" if self.attached else ""
    return "Port %02d: %s %s" % (self.id, self.mode, attached)


class Cambrionix(object):
  BAUD_RATE = 115200
  """Baud rate for serial communication."""

  LINE_TERMINATOR = "\r\n"
  """Line terminator used by serial console."""

  READ_TIMEOUT = 1
  """Read timeout in seconds when reading from serial."""

  def __init__(self, serial_device):
    """
    :param str serial_device: path to serial device (e.g. /dev/ttyUSB0)
    """
    self.serial_device = serial_device

  @property
  def ports_status(self):
    """Dictionary of port ids -> PortStatus."""
    lines = self._SendCommand("state")
    status_list = {}
    for line in lines:
      if line == "state":
        continue
      status = PortStatus(line)
      status_list[status.id] = status
    return status_list

  def SetPortMode(self, mode, port=0):
    """Sets mode for all or selected port.

    :param str mode: sync, off or charge
    :param int port: Port number to operate. 0 = all ports.
    """
    mode = mode[0]
    if mode not in ("s", "o", "c"):
      raise Exception("status has to be sync, off or charge")
    command = "mode %s" % mode
    if port:
      command += " %d" % port
    self._SendCommand(command)

  def _SendCommand(self, command):
    serial = Serial(self.serial_device, self.BAUD_RATE,
                    timeout=self.READ_TIMEOUT)
    try:
      _log.info("Serial command: %s", command)
      _log.debug("> %s", command)
      serial.write(command + self.LINE_TERMINATOR)

      # The console responds with an echo of the command
      prompt_response = serial.readline()
      _log.debug("< %s", prompt_response)

      # Read command response
      lines = []
      while True:
        line = serial.readline()
        _log.debug("< %s", line)
        if not len(line):
          raise Exception("Serial communication timeout")
        if line.startswith("*E"):
          raise Exception("Command '%s' failed: %s" % (command, line))
        if line == self.LINE_TERMINATOR:
          break
        lines.append(line.strip())
      return lines
    finally:
      serial.close()

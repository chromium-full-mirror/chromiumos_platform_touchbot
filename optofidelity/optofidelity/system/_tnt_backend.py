# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of the robot backend classes with the Optofidelity API."""

import math

from ._backend import DUTBackend, RobotBackend
from .tnt.TnTClient import TnTClient


class TnTDUTBackend(DUTBackend):
  """DUT backend implementation for the Optofidelity TnT robot."""

  def __init__(self, name, client):
    self.name = name
    self._client = client

  def DetectIcon(self, icon_file):
    ret = self._client.find_objects(icon_file)
    if not ret["success"]:
      return None
    best_match = max(ret["results"], key=lambda r: r["score"])
    if best_match["score"] < 0.5:
      return None
    x = (best_match["topLeftX"] + best_match["bottomRightX"]) / 2.0
    y = (best_match["topLeftY"] + best_match["bottomRightY"]) / 2.0
    return x, y

  def DetectWords(self, words):
    word_coords = {word: None for word in words}
    ret = self._client.read_text()
    if not ret["success"]:
      return word_coords
    for match in ret["results"]:
      x = (match["topLeftX"] + match["bottomRightX"]) / 2.0
      y = (match["topLeftY"] + match["bottomRightY"]) / 2.0
      text = match["text"]
      if text in word_coords:
        word_coords[text] = (x, y)
    return word_coords

  def Tap(self, x, y, count=1):
    if count == 1:
      self._client.tap(x, y)
    else:
      self._client.multi_tap([(x, y)] * count)

  def Move(self, x, y, z):
    self._client.move(x, y, z)

  def Jump(self, x, y, z):
    self._client.jump(x, y, z, height=40)

  def WaitForGesturesToFinish(self):
    self._client.complete_requests()

  @property
  def position(self):
    return self._client.get_position()

  @property
  def width(self):
    return self._client.panel_width

  @property
  def height(self):
    return self._client.panel_height

  @property
  def orientation(self):
    return float(self._client.panel_angle) / 180.0 * math.pi


class TnTRobotBackend(RobotBackend):
  """Robot backend implementation for the Optofidelity TnT robot."""

  def __init__(self, host, port=None):
    self._client = TnTClient(host, port or 8000)

  def Reset(self):
    robot = self._client.robots().values()[0]
    robot.go_home()
    robot.set_speed(200)

  def GetDUTBackend(self, name):
    dut_client = self._client.dut(name)
    return TnTDUTBackend(name, dut_client)

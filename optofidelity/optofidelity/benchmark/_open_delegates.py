# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Temporary implementation of OpenStuffDelegate"""

from ._delegate import BenchmarkDelegate
from .results import DrawEventLatencySeries


class OpenStuffDelegate(BenchmarkDelegate):
  """Contains logic to measure the latency of opening stuff."""

  def InitializeProcessor(self, processor):
    processor.EnableDetectors(led=True)

  def ExecuteOnSubject(self, subject):
    subject.camera.Prepare(6000, subject.exposure)
    center = (subject.width / 2.0, subject.height / 2.0)

    subject.Tap(*center, blocking=True)
    subject.camera.Trigger()
    subject.Tap(*center, count=10)

    return subject.camera.ReceiveVideo()

  def ProcessTrace(self, trace, measurements):
    measurements.AddSeriesInfo("LEDLatency", DrawEventLatencySeries)
    series = measurements.AddSeries("LEDLatency")
    for i in range(len(trace) - 1):
      series.AddMEasurement(trace[i], trace[i + 1])


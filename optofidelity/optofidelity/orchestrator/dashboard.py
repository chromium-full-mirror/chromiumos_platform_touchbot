# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import requests

from safetynet import TypecheckMeta

from optofidelity.benchmark import BenchmarkResults

import socket
import httplib
import requests


class Dashboard(object):
  __metaclass__ = TypecheckMeta

  def __init__(self, endpoint_url, fake=False):
    """
    :param str endpoint_url: URL of dashboard endpoint to post results to.
    :param bool fake: Print JSON requests instead of sending them.
    """
    self.endpoint_url = endpoint_url
    self.fake = fake

  def ReportResults(self, benchmark_results, version, version_uid, report_url):
    """Report results of benchmark to dashboard.

    :type benchmark_results: BenchmarkResults
    """
    payload = self._FormatRequest(benchmark_results, version, version_uid,
                                  report_url)
    if not self.endpoint_url:
      print json.dumps(payload, indent=2)
      return

    params = dict(data=json.dumps(payload))
    result = requests.post(self.endpoint_url, data=params)
    if result.status_code != 200:
      print result.text
      raise Exception("Error while reporting results to dashboard.")

  def _FormatRequest(self, benchmark_results, version, version_uid, report_url):
    charts = {}
    measurements = benchmark_results.measurement_list
    for mid, id_measurements in measurements.IterByMeasurementID():
      charts[mid] = {}
      charts[mid]["overall"] = {
        "type": "list_of_scalar_values",
        "file": report_url,
        "units": "ms",
        "values": list(measurements.latencies)
      }

    chart_data = {
      "format_version": "1.0",
      "benchmark_name": "touch_latency.%s" % benchmark_results.benchmark_type,
      "charts": charts
    }
    data = {
      "master": "TouchBot",
      "bot": benchmark_results.subject_name.replace("/", "."),
      "point_id": version_uid,
      "versions": {
        "chrome": version
      },
      "supplemental": {},
      "chart_data": chart_data
    }
    return data


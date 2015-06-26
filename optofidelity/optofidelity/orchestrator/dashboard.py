# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from abc import abstractmethod
from StringIO import StringIO
from urllib import urlencode
import json
import logging

from safetynet import InterfaceMeta, Optional

from optofidelity.benchmark import BenchmarkResults
import pycurl

from .omaha import GetChromeBuildTimestamp

_log = logging.getLogger(__name__)

class Dashboard(object):
  __metaclass__ = InterfaceMeta

  def __init__(self, subject_name):
    self.subject_name = subject_name

  @abstractmethod
  def ReportResults(self, benchmark_results, version, report_url):
    """Report results of benchmark to dashboard.

    :type benchmark_results: BenchmarkResults
    """


def HTTPPost(url, data):
  buffer = StringIO()
  curl = pycurl.Curl()
  curl.setopt(curl.URL, url)

  postfields = urlencode(data)
  curl.setopt(curl.POSTFIELDS, postfields)
  curl.setopt(curl.WRITEDATA, buffer)
  curl.setopt(curl.IPRESOLVE, curl.IPRESOLVE_V4)
  curl.perform()
  status_code = curl.getinfo(pycurl.HTTP_CODE)
  curl.close()

  if status_code != 200:
      print buffer.getvalue()
      raise Exception("Error while reporting results to dashboard.")

  return buffer.getvalue()


class ChromePerfDashboard(Dashboard):
  def __init__(self, subject_name, endpoint_url):
    """
    :param Optional[str] endpoint_url: URL of dashboard endpoint to post results
           to, will dump JSON requests instead of posting them to the URL if
           this parameter is None.
    """
    super(ChromePerfDashboard, self).__init__(subject_name)
    self.endpoint_url = endpoint_url

  @classmethod
  def FromConfig(cls, parameters, children, subject_name):
    return cls(subject_name, parameters["endpoint"])

  def ReportResults(self, benchmark_results, version, report_url):
    payload = self._FormatRequest(benchmark_results, version, report_url)
    if not self.endpoint_url:
      print json.dumps(payload, indent=2)
    else:
      params = dict(data=json.dumps(payload))
      HTTPPost(self.endpoint_url, params)

    for line in json.dumps(payload, indent=2).split("\n"):
      _log.info("    %s" % line)

  def _FormatRequest(self, benchmark_results, version, report_url):
    point_id = GetChromeBuildTimestamp(version)

    charts = {}
    charts[benchmark_results.benchmark_name] = {}
    msrmnts = benchmark_results.measurements
    for series_name, series_info in msrmnts.series_infos.iteritems():
      values = msrmnts.SummarizeValues(series_name)
      charts[benchmark_results.benchmark_name][series_name] = {
        "type": "list_of_scalar_values",
        "units": series_info.units,
        "values": [value for value in values]
      }

    chart_data = {
      "format_version": "1.0",
      "benchmark_name": "touch_latency",
      "charts": charts
    }
    data = {
      "master": "TouchBot",
      "bot": self.subject_name.replace("/", "."),
      "point_id": point_id,
      "versions": {
        "chrome_version": version
      },
      "supplemental": {
        "stdio_uri": report_url,
        "default_rev": "r_chrome_version",
      },
      "chart_data": chart_data
    }
    return data

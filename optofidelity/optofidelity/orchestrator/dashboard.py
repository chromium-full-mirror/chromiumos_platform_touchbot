# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from StringIO import StringIO
from urllib import urlencode
import logging
import json

from safetynet import Optional, TypecheckMeta

from optofidelity.benchmark import BenchmarkResults
import pycurl


_log = logging.getLogger(__name__)


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


class Dashboard(object):
  __metaclass__ = TypecheckMeta

  def __init__(self, endpoint_url):
    """
    :param Optional[str] endpoint_url: URL of dashboard endpoint to post results
           to, will dump JSON requests instead of posting them to the URL if
           this parameter is None.
    """
    self.endpoint_url = endpoint_url

  def ReportResults(self, benchmark_results, version, version_uid, report_url):
    """Report results of benchmark to dashboard.

    :type benchmark_results: BenchmarkResults
    """
    payload = self._FormatRequest(benchmark_results, version, version_uid,
                                  report_url)
    if not self.endpoint_url:
      print json.dumps(payload, indent=2)
    else:
      params = dict(data=json.dumps(payload))
      print HTTPPost(self.endpoint_url, params)

    for line in json.dumps(payload, indent=2).split("\n"):
      _log.info("    %s" % line)

  def _FormatRequest(self, benchmark_results, version, version_uid, report_url):
    charts = {}
    charts[benchmark_results.benchmark_type] = {}
    msrmnts = benchmark_results.measurements
    for series_name, series_info in msrmnts.series_infos.iteritems():
      values = msrmnts.SummarizeValues(series_name)
      charts[benchmark_results.benchmark_type][series_name] = {
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
      "bot": benchmark_results.subject_name.replace("/", "."),
      "point_id": version_uid,
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

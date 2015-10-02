# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from abc import abstractmethod
from StringIO import StringIO
from urllib import urlencode
import json
import logging
import traceback

from safetynet import InterfaceMeta, Optional
import numpy as np

from oauth2client.client import SignedJwtAssertionCredentials
from optofidelity.benchmark import BenchmarkResults
from optofidelity.util import PrintTime, const_property
import gspread
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


class FakeDashboard(Dashboard):
  def __init__(self, subject_name):
    super(FakeDashboard, self).__init__(subject_name)
    self.results = []

  @classmethod
  def FromConfig(cls, parameters, children, subject_name):
    return cls(subject_name)

  def ReportResults(self, benchmark_results, version, report_url):
    self.results.append(benchmark_results)


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
  def __init__(self, subject_name, master_name, endpoint_url):
    """
    :param Optional[str] endpoint_url: URL of dashboard endpoint to post results
           to, will dump JSON requests instead of posting them to the URL if
           this parameter is None.
    """
    super(ChromePerfDashboard, self).__init__(subject_name)
    self.endpoint_url = endpoint_url
    self.master_name = master_name

  @classmethod
  def FromConfig(cls, parameters, children, subject_name):
    return cls(subject_name, parameters["master"], parameters["endpoint"])

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
    type_name = benchmark_results.benchmark_name.split("/")[-1]

    charts = {}
    charts[type_name] = {}
    msrmnts = benchmark_results.measurements
    for series_name, series_info in msrmnts.series_infos.iteritems():
      values = msrmnts.SummarizeValues(series_name)
      charts[type_name][series_name] = {
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
      "master": self.master_name,
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


class SpreadsheetDashboard(Dashboard):
  __metaclass__ = InterfaceMeta

  def __init__(self, subject_name, spreadsheet_key, private_key_file):
    super(SpreadsheetDashboard, self).__init__(subject_name)
    json_key = json.load(open(private_key_file))
    scope = ['https://spreadsheets.google.com/feeds']
    self.credentials = SignedJwtAssertionCredentials(json_key['client_email'],
                                                     json_key['private_key'],
                                                     scope)
    self.spreadsheet_key = spreadsheet_key
    self._document = None

  @classmethod
  def FromConfig(cls, parameters, children, subject_name):
    report_as = parameters.get("report-as")
    if report_as is not None:
      subject_name = report_as
    return cls(subject_name, parameters["sheet-key"],
               parameters["oauth-key-file"])

  def _Connect(self):
    gs_api = gspread.authorize(self.credentials)
    return gs_api.open_by_key(self.spreadsheet_key)

  def ReportResults(self, benchmark_results, version, report_url):
    for i in range(3):
      try:
        document = self._Connect()
        subject_sheet = self._OpenSubjectSheet(document, benchmark_results)
        subject_header = self._UpdateHeader(subject_sheet, benchmark_results)
        self._UpdateSummarySheet(document, benchmark_results, subject_header)

        measurements = benchmark_results.measurements
        type_name = benchmark_results.benchmark_name.split("/")[-1]

        # Add new row for results
        subject_sheet.add_rows(1)
        row = subject_sheet.row_count

        # Insert meta information at front
        metadata = benchmark_results.metadata
        if "time" in metadata:
          subject_sheet.update_cell(row, 1, metadata["time"])
        subject_sheet.update_cell(row, 2, version)
        subject_sheet.update_cell(row, 3, type_name)
        subject_sheet.update_cell(row, 4, "=hyperlink(\"%s\", \"link\")" %
                                          report_url)

        # Insert latency measurements results
        for header, col in subject_header.iteritems():
          if header not in measurements.series_infos:
            continue
          values = measurements.SummarizeValues(header)
          subject_sheet.update_cell(row, col, np.mean(values))
        return
      except KeyboardInterrupt:
        raise
      except:
        traceback.print_exc()
    raise Exception("Reporting to spreadsheet failed.")

  def _OpenSubjectSheet(self, document, benchmark_results):
    """Opens the subject sheet or initializes it if it does not exist yet."""
    try:
      subject_sheet = document.worksheet(self.subject_name)
    except gspread.WorksheetNotFound:
      subject_sheet = document.add_worksheet(self.subject_name, 1, 4)
      subject_sheet.update_cell(1, 1, "Time")
      subject_sheet.update_cell(1, 2, "Version")
      subject_sheet.update_cell(1, 3, "Type")
      subject_sheet.update_cell(1, 4, "Report")
    return subject_sheet

  def _UpdateHeader(self, sheet, benchmark_results):
    """Updates the header at the top of the sheet.

    Returns a dictionary mapping the header label to col name.
    """
    header_locations = dict()
    for i, existing_header in enumerate(sheet.row_values(1)):
      header_locations[existing_header] = i + 1

    for header in benchmark_results.measurements.series_infos.keys():
      if header in header_locations:
        continue
      sheet.add_cols(1)
      location = sheet.col_count
      sheet.update_cell(1, location, header)
      header_locations[header] = location
    return header_locations

  def _UpdateSummarySheet(self, document, benchmark_results, subject_header):
    """Updates the summary sheet to include pointers to the subject sheet."""
    try:
      summary_sheet = document.worksheet("summary")
    except gspread.WorksheetNotFound:
      summary_sheet = document.add_worksheet("summary", 1, 1)
      summary_sheet.update_cell(1, 1, "Subject")

    summary_header = self._UpdateHeader(summary_sheet, benchmark_results)

    # Find row to update (or insert a new one)
    summary_row = None
    for i, row in enumerate(summary_sheet.col_values(1)):
      if row == self.subject_name or row is None:
        summary_row = i + 1
        break
    if summary_row is None:
      summary_sheet.add_rows(1)
      summary_row = summary_sheet.row_count
      summary_sheet.update_cell(summary_row, 1, self.subject_name)

    # Update each cell with an expression that points to the latest value
    # in the subject sheet
    for header, col in summary_header.iteritems():
      subject_col = subject_header.get(header)
      if subject_col is None:
        continue
      target_col_label = summary_sheet.get_addr_int(1, subject_col)[:-1]
      target_range = "'%s'!%s:%s" % (self.subject_name, target_col_label,
                                      target_col_label)
      expression = ("=index(filter(%(range)s, not(isblank(%(range)s))), " +
                      "rows(filter(%(range)s, not(isblank(%(range)s)))))")
      expression = expression % dict(range=target_range)
      summary_sheet.update_cell(summary_row, col, expression)

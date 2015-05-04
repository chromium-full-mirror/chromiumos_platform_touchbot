# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from collections import defaultdict
from datetime import datetime
from fnmatch import fnmatch
import logging
import os

from safetynet import List, Optional, TypecheckMeta
import dataset

from optofidelity.benchmark import Benchmark, BenchmarkResults, BenchmarkRunner
from optofidelity.gsutil import GSPathExists
from optofidelity.system import BenchmarkSubject, BenchmarkSystem
from optofidelity.util import ProgressPrinter

from .dashboard import Dashboard

_log = logging.getLogger(__name__)


class Orchestrator(object):
  """Orchestrates running multiple tests and persistent storage or results.

  Each test that can be run by the orchestrator has a name in the format:
    dut_name/subject_name/benchmark_type
  """
  __metaclass__ = TypecheckMeta

  def __init__(self, benchmark_system, benchmark_runner, dashboard, results_url,
               results_db_url, print_progress=False):
    """
    :type benchmark_system: BenchmarkSystem
    :type benchmark_runner: BenchmarkRunner
    :type dashboard: Dashboard
    :type results_url: str
    :type results_db_url: str
    :type results_url: str
    """
    self._system = benchmark_system
    self._runner = benchmark_runner
    self._dashboard = dashboard
    self._results_url = results_url
    self._print_progress = print_progress

    self._results_db = dataset.connect(results_db_url)
    self._results_table = self._results_db["benchmark_results"]
    self._progress = ProgressPrinter(_log, print_progress)

  def UpdateAndRunBenchmarks(self, match, debug_flags, forced_version=None,
                             skip_update=False):
    """Update, then run all benchmarks matching 'match' and save results.

    This will update all subjects and executes benchmarks if they have been
    updated.

    :param str match: One of the following:
           - The full name of a benchmark
           - The beginning of the name of a benchmark
           - A unix glob
    :type debug_flags: List[str]
    :param Optional[str] forced_version: Force version number to benchmark.
    :param bool skip_update: Skip update process and run all benchmarks
    """
    for subject_name, benchmark_types in self._ListMatchingBenchmarks(match):
      try:
        subject = self._system.subjects[subject_name]
        self._progress.Info(subject_name,
                            "Running benchmarks: %s" % (benchmark_types,))
        if not skip_update:
          if not self.UpdateSubject(subject, forced_version):
            self._progress.Info(subject.name, "Skipping benchmarks.")
            continue

        time = datetime.now()
        subject_version = subject.updater.installed_version
        metadata = dict(time=time)
        if subject_version:
          metadata["subject_version"] = subject_version
        for benchmark in self._runner.RunBenchmarks(subject, benchmark_types,
                                                    metadata, debug_flags):
          self._StoreBenchmark(benchmark, subject, time)
      except:
        self._progress.Exception(subject.name)
        self._progress.Error(subject.name, "Subject in bad state")

  def UpdateSubject(self, subject, forced_version=None):
    """Update subject to latest or custom version.

    :type subject: BenchmarkSubject
    :param Optional[str] forced_version: Force version number install
    :returns bool: True if the subject has been updated.
    """
    self._progress.Info(subject.name, "Checking for updates")
    available = subject.updater.available_versions

    target_version = None
    if forced_version:
      for version in available:
        if fnmatch(version, forced_version):
          target_version = version
          break
      self._progress.Info(subject.name, "Forcing version %s" % target_version)
      if not target_version:
        raise ValueError("Version %s is not available" % forced_version)
    else:
      target_version = available[0]
      self._progress.Info(subject.name, "Latest version is %s" % target_version)
      if target_version == subject.updater.installed_version:
        self._progress.Info(subject.name, "Already installed")
        return False
    self._progress.Info(subject.name, "Installing %s" % target_version)
    subject.updater.Install(target_version, self._print_progress)
    return True

  def QueryResults(self):
    """Return iterator over all results in database."""
    return self._results_table.all()

  def _StoreBenchmark(self, benchmark, subject, time):
    """Store benchmark to results folder and register in database.

    :type benchmark: Benchmark
    :type subject: BenchmarkSubject
    :type time: datetime
    """
    subject_version = subject.updater.installed_version
    metadata = dict(time=time)
    if subject_version:
      metadata["subject_version"] = subject_version

    results_url, uid = self._FindUniqueResultsURL(time)

    self._progress.Info(benchmark.name, "Saving benchmark to %s" % results_url)
    benchmark.Save(results_url, debug_info=True,
                   print_progress=self._print_progress)

    self._progress.Info(benchmark.name, "Generating Report")
    benchmark.GenerateReport(results_url, print_progress=self._print_progress)
    self._InsertResults(time, uid, subject_version, benchmark.results)

    public_url = results_url.replace("gs://", "http://storage.googleapis.com/")
    report_url = os.path.join(public_url, "report.html")
    self._progress.Info(benchmark.name, "Report available at: %s" % report_url)

    self._progress.Info(benchmark.name, "Reporting results to dashboard")
    self._dashboard.ReportResults(benchmark.results, subject_version,
        subject.updater.GetVersionUID(subject_version), report_url)

  def _FindUniqueResultsURL(self, time):
    """Find a unique folder to store results into.

    This will return a folder name of the following format:
    results_path/date_time_000/
    With 000 being an increasing number.

    :type time: datetime
    :rtype str
    """
    for i in range(999):
      timestamp = time.strftime("%Y%m%d_%H%M")
      uid = "%s_%03d" % (timestamp, i)
      results_path = os.path.join(self._results_url, uid)
      if not GSPathExists(results_path):
        return results_path, uid
    raise Exception("Cannot find unique results path")

  def _ListMatchingBenchmarks(self, match):
    """Lists (subject_name, benchmark_type) for a match string

    :type match: str
    """
    type_names = Benchmark.BENCHMARK_TYPES
    subject_names = self._system.subjects.keys()
    benchmarks = { ("%s/%s" % (s, t)): (s, t) for s in subject_names
                                              for t in type_names }
    match_fn = lambda name: fnmatch(name, match) or name.startswith(match)
    matches = [n for n in benchmarks.iterkeys() if match_fn(n)]
    grouped = defaultdict(list)
    for match in matches:
      subject_name, benchmark_type = benchmarks[match]
      grouped[subject_name].append(benchmark_type)
    return grouped.iteritems()

  def _InsertResults(self, time, uid, subject_version, results):
    """Inserts results into database

    :type time: datetime
    :type uid: str
    :type subject_version: Optional[str]
    :type results: BenchmarkResults
    """
    dump = lambda array: ", ".join(str(array))
    for mid, id_measurements in results.measurement_list.IterByMeasurementID():
      row_data = dict(
          time=time,
          uid=uid,
          subject_name=results.subject_name,
          subject_version=subject_version,
          benchmark_type=results.benchmark_type,
          measurement_id=mid,
          draw_start_mean=id_measurements.draw_start_mean,
          draw_start_std=id_measurements.draw_start_std,
          draw_end_mean=id_measurements.mean,
          draw_end_std=id_measurements.std,
          draw_start_latencies=dump(id_measurements.draw_start_latencies),
          draw_end_latencies=dump(id_measurements.latencies)
      )
      self._results_table.insert(row_data)

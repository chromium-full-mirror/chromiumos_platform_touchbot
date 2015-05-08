# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from collections import defaultdict
from datetime import datetime
from fnmatch import fnmatch
import logging
import os

from safetynet import List, Optional, TypecheckMeta

from optofidelity.benchmark import (AggregateResults, Benchmark,
                                    BenchmarkResults, BenchmarkRunner,
                                    MeasurementList)
from optofidelity.gsutil import GSFolder, GSPathExists
from optofidelity.reporting import AggregateReport, BenchmarkReport
from optofidelity.system import BenchmarkSubject, BenchmarkSystem
from optofidelity.util import ProgressPrinter
import dataset

from .dashboard import Dashboard

_log = logging.getLogger(__name__)


class Orchestrator(object):
  """Orchestrates running multiple tests and persistent storage or results.

  Each test that can be run by the orchestrator has a name in the format:
    dut_name/subject_name/benchmark_type
  """
  __metaclass__ = TypecheckMeta

  MAX_BENCHMARK_TRIES = 3
  """Maximum number of tries to run a benchmark before giving up."""

  MIN_NUMBER_SAMPLES = 20
  """Minimum number of measurement samples before commiting to the dashboard."""

  def __init__(self, benchmark_system, benchmark_runner, dashboard, results_url,
               results_db_url):
    """
    :type benchmark_system: BenchmarkSystem
    :type benchmark_runner: BenchmarkRunner
    :type dashboard: Dashboard
    :type results_url: str
    :type results_db_url: str
    """
    self._system = benchmark_system
    self._runner = benchmark_runner
    self._dashboard = dashboard
    self._results_url = results_url

    self._results_db = dataset.connect(results_db_url)
    self._results_table = self._results_db["benchmark_results"]
    self._progress = ProgressPrinter(_log)

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
        self.RunSubjectBenchmarks(subject, benchmark_types, debug_flags)
      except:
        self._progress.Exception(subject.name)
        self._progress.Error(subject.name, "Subject in bad state")

  def RunSubjectBenchmarks(self, subject, benchmark_types, debug_flags):
    """Run benchmarks on a subject and store/report results.

    :type subject: BenchmarkSubject
    :type benchmark_types: List[str]
    :type debug_flags: List[str]
    """
    subject_version = subject.updater.installed_version
    metadata = dict()
    if subject_version:
      metadata["subject_version"] = subject_version

    with self._runner.UseSubject(subject):
      for benchmark_type in benchmark_types:
        benchmark_name = "%s/%s" % (subject.name, benchmark_type)

        aggregate = self._GatherBenchmarkSamples(subject, benchmark_type,
                                                 metadata, debug_flags)
        if not aggregate:
          continue
        self._progress.Info(benchmark_name, "Aggregate Results:")
        print aggregate

        self._progress.Info(benchmark_name, "Generating Aggregate report:")
        time = datetime.now()
        results_url, uid = self._FindUniqueResultsURL(time)
        self._GenerateAggregateReport(aggregate, results_url)

        public_url = self._GetPublicReportUrl(results_url)
        self._progress.Info(benchmark_name,
                            "Report available at: %s" % public_url)

        self._progress.Info(benchmark_name, "Reporting results to dashboard")
        self._dashboard.ReportResults(aggregate, subject_version,
            subject.updater.GetVersionUID(subject_version), "")

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
    subject.updater.Install(target_version)
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
    benchmark.Save(results_url, debug_info=True)

    self._progress.Info(benchmark.name, "Generating Report")
    self._GenerateBenchmarkReport(benchmark, results_url)
    self._InsertResults(time, uid, subject_version, benchmark.results)

    public_url = self._GetPublicReportUrl(results_url)
    self._progress.Info(benchmark.name, "Report available at: %s" % public_url)

    benchmark.results.report_url = public_url
    benchmark.results.uid = uid

  def _GetPublicReportUrl(self, url):
    public_url = url.replace("gs://", "http://storage.googleapis.com/")
    return os.path.join(public_url, "report.html")

  def _GenerateBenchmarkReport(self, benchmark, report_url):
    """Generate benchmark report into folder.

    :param str report_path: path to folder to save the report into.
    :rtype Report
    """
    with GSFolder(report_url) as report_path:
      report = BenchmarkReport(report_path, "report.html",
                               benchmark.finger_calib_delay)
      report.GenerateReport(benchmark.results, benchmark.trace,
                            benchmark.screen_calibration, benchmark.video)

  def _GenerateAggregateReport(self, aggregate_results, report_url):
    """Generate aggregate report into folder

    :param str report_path: path to folder to save the report into.
    :rtype Report
    """
    with GSFolder(report_url) as report_path:
      report = AggregateReport(report_path, "report.html")
      report.GenerateReport(aggregate_results)

  def _GatherBenchmarkSamples(self, subject, benchmark_type, metadata,
                              debug_flags):
    """Runs benchmark until enough measurements are collected.

    Returns None if running one of the benchmarks failed.

    :type subject: BenchmarkSubject
    :type benchmark_type: str
    :type metadata: dict
    :type debug_flags: List[str]
    :rtype Optional[BenchmarkResults]
    """
    aggregate = AggregateResults(subject.name, benchmark_type, metadata)
    while True:
      benchmark = self._SafelyRunBenchmark(subject, benchmark_type, metadata,
                                           debug_flags)
      if not benchmark:
        return None
      aggregate.AddRepetition(benchmark.results)

      enough_samples = True
      generator = aggregate.measurement_list.IterByMeasurementID()
      for mid, id_measurements in generator:
        self._progress.Info(benchmark.name, "Collected %d samples for %s." %
                                             (len(id_measurements), mid))
        if len(id_measurements) < self.MIN_NUMBER_SAMPLES:
          enough_samples = False
      if not enough_samples:
        self._progress.Info(benchmark.name, "Collecting more samples.")
      else:
        return aggregate

  def _SafelyRunBenchmark(self, subject, benchmark_type, metadata, debug_flags):
    """Run benchmark and retry until successful.

    Returns None if the the benchmark failed MAX_BENCHMARK_TRIES times.

    :type subject: BenchmarkSubject
    :type benchmark_type: str
    :type metadata: dict
    :type debug_flags: List[str]
    :rtype Optional[Benchmark]
    """
    time = datetime.now()
    benchmark_name = "%s/%s" % (subject.name, benchmark_type)
    metadata["time"] = time

    for repetition in range(self.MAX_BENCHMARK_TRIES):
      rep_name = "Benchmark (repetiton=%d)" % repetition
      self._progress.Info(benchmark_name, "Running %s" % rep_name)

      benchmark = self._runner.RunBenchmark(benchmark_type, metadata,
                                            debug_flags)
      self._StoreBenchmark(benchmark, subject, time)

      if not len(benchmark.results.error):
        self._progress.Info(benchmark_name, "Results:")
        print benchmark.results
        return benchmark

      self._progress.Error(benchmark.name, "%s failed." % rep_name)

    self._progress.Error(benchmark.name, "All repetitions failed. Giving up!")
    return None

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

    if len(results.error):
      generator = [("", MeasurementList())]
    else:
      generator = results.measurement_list.IterByMeasurementID()
    for mid, id_measurements in generator:
      row_data = dict(
          time=time,
          uid=uid,
          subject_name=results.subject_name,
          subject_version=subject_version,
          benchmark_type=results.benchmark_type,
          error=results.error,
          measurement_id=mid,
          draw_start_mean=id_measurements.draw_start_mean,
          draw_start_std=id_measurements.draw_start_std,
          draw_end_mean=id_measurements.mean,
          draw_end_std=id_measurements.std,
          draw_start_latencies=dump(id_measurements.draw_start_latencies),
          draw_end_latencies=dump(id_measurements.latencies)
      )
      self._results_table.insert(row_data)

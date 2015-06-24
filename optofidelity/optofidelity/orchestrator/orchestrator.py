# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from collections import defaultdict
from datetime import datetime
from fnmatch import fnmatch
import logging
import os
import time

from safetynet import List, Optional, TypecheckMeta
import numpy as np

from optofidelity.benchmark import (AggregateResults, Benchmark,
                                    BenchmarkResults, BenchmarkRunner)
from optofidelity.reporting import AggregateReport, BenchmarkReport
from optofidelity.system import BenchmarkSubject, BenchmarkSystem
from optofidelity.util import (GSFindUniqueFilename, GSFolder, GSPathExists,
                               ProgressPrinter)
import dataset

from .dashboard import Dashboard
from .orchestrator_subject import OrchestratorSubject

_log = logging.getLogger(__name__)


class Orchestrator(object):
  """Orchestrates running multiple tests and persistent storage or results.

  Each test that can be run by the orchestrator has a name in the format:
    dut_name/subject_name/benchmark_type
  """
  __metaclass__ = TypecheckMeta

  MAX_BENCHMARK_TRIES = 3
  """Maximum number of tries to run a benchmark before giving up."""

  FILED_BENCHMARKS_FILE = "failed_benchmarks.log"

  def __init__(self, benchmark_system, benchmark_runner, dashboard, results_url,
               results_db_url, generate_reports=True, xkcd=False):
    """
    :type benchmark_system: BenchmarkSystem
    :type benchmark_runner: BenchmarkRunner
    :type dashboard: Optional[Dashboard]
    :type results_url: str
    :type results_db_url: str
    :param bool xkcd: Give reports more authority
    :param bool generate_reports: Generate reports for each benchmark
    """
    self._system = benchmark_system
    self._runner = benchmark_runner
    self._dashboard = dashboard
    self._results_url = results_url

    self._results_db = None
    self._results_table = None
    if results_db_url:
      self._results_db = dataset.connect(results_db_url)
      self._results_table = self._results_db["benchmark_results"]

    self._progress = ProgressPrinter(_log)
    self._generate_reports = generate_reports
    self._xkcd = xkcd
    self._subjects = {}

  @property
  def benchmark_names(self):
    return [ "%s/%s" % (s.name, n) for s in self._subjects.itervalues()
                                   for n in s.benchmark_defs ]

  def AddSubject(self, subject):
    """
    :type subject: OrchestratorSubject
    """
    self._subjects[subject.name] = subject

  @classmethod
  def FromConfig(cls, parameters, children, system, runner, dashboard):
    xkcd = parameters.get("xkcd") is not None
    results = parameters["results"]
    database = parameters["database"]
    return cls(system, runner, dashboard, results, database, xkcd=xkcd)

  def RunHistoryBenchmarks(self, match, debug_flags, first_version):
    for subject_name, benchmark_types in self._ListMatchingBenchmarks(match):
      subject = self._system.subjects[subject_name]

      versions = subject.updater.available_versions
      first_version_idx = versions.index(first_version)
      versions_to_test = versions[:(first_version_idx + 1)]
      self._progress.Info(subject_name,
                          "Versions to test: %s" % (versions_to_test,))
      start_time = time.time()
      for version in reversed(versions_to_test):
        try:
          self._progress.Info(subject_name,
                              "Running benchmarks: %s" % (benchmark_types,))
          self.UpdateSubject(subject, version)
          self.RunSubjectBenchmarks(subject, benchmark_types, debug_flags)
        except KeyboardInterrupt:
          raise
        except:
          self._progress.Exception(subject.name)
          self._progress.Error(subject.name, "Version %s failed" % version)
      elapsed_minutes = (time.time() - start_time) / 60
      self._progress.Info(subject_name, "History total time: %d min" % (
                                        elapsed_minutes))


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
    for subject, benchmark_defs in self._ListMatchingBenchmarks(match):
      try:
        benchmark_names = [d.name for d in benchmark_defs]
        self._progress.Info(subject.name,
                            "Running benchmarks: %s" % (benchmark_names,))
        if not skip_update:
          if not self.UpdateSubject(subject, forced_version):
            self._progress.Info(subject.name, "Skipping benchmarks.")
            continue
        self.RunSubjectBenchmarks(subject, benchmark_defs, debug_flags)
      except KeyboardInterrupt:
        raise
      except:
        self._progress.Exception(subject.name)
        self._progress.Error(subject.name, "Subject in bad state")

  def RunSubjectBenchmarks(self, subject, benchmark_defs, debug_flags):
    """Run benchmarks on a subject and store/report results.

    :type subject: BenchmarkSubject
    :type debug_flags: List[str]
    """
    subject_version = subject.updater.installed_version
    metadata = dict()
    if subject_version:
      metadata["subject_version"] = subject_version

    start_time = time.time()
    with self._runner.UseSubject(subject):
      for benchmark_def in benchmark_defs:
        full_name = "%s/%s" % (subject.name, benchmark_def.name)

        aggregate = self._GatherBenchmarkSamples(subject, benchmark_def,
                                                 metadata, debug_flags)
        if not aggregate:
          continue
        self._progress.Info(full_name, "Aggregate Results:")
        print aggregate

        self._progress.Info(full_name, "Generating Aggregate report:")
        benchmark_time = datetime.now()
        results_url, uid = self._FindUniqueResultsURL(benchmark_time)
        self._GenerateAggregateReport(aggregate, results_url)

        public_url = self._GetPublicReportUrl(results_url)
        self._progress.Info(full_name,
                            "Report available at: %s" % public_url)

        if subject.dashboard:
          self._progress.Info(full_name, "Reporting results to dashboard")
          version_uid = subject.updater.GetVersionUID(subject_version)
          subject.dashboard.ReportResults(aggregate, subject_version,
                                          version_uid, public_url)
    elapsed_minutes = (time.time() - start_time) / 60
    self._progress.Info(subject.name, "Elapsed time: %d min" % elapsed_minutes)

  def UpdateSubject(self, subject, forced_version=None):
    """Update subject to latest or custom version.

    :type subject: BenchmarkSubject
    :param Optional[str] forced_version: Force version number install
    :returns bool: True if the subject has been updated.
    """
    available = subject.updater.available_versions

    target_version = None
    if forced_version:
      for version in available:
        if fnmatch(version, forced_version):
          target_version = version
          break
      self._progress.Info(subject.name, "Forcing update to version %s" %
                          target_version)
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
    save_video = bool(len(benchmark.results.error))
    benchmark.Save(results_url, debug_info=True, video=save_video)

    self._progress.Info(benchmark.name, "Generating Report")
    self._GenerateBenchmarkReport(benchmark, results_url)
    self._InsertResults(time, uid, subject, benchmark.results)

    public_url = self._GetPublicReportUrl(results_url)
    self._progress.Info(benchmark.name, "Report available at: %s" % public_url)

    if len(benchmark.results.error):
      with open(self.FILED_BENCHMARKS_FILE, "a") as error_log:
        error_log.write("-" * 80 + "\n")
        error_log.write(str(benchmark.results))
        error_log.write("\n")

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
    if not self._generate_reports:
      return
    with GSFolder(report_url) as report_path:
      report = BenchmarkReport(report_path, "report.html", xkcd=self._xkcd)
      report.GenerateReport(benchmark.results, benchmark.trace,
                            benchmark.screen_calibration, benchmark.video)

  def _GenerateAggregateReport(self, aggregate_results, report_url):
    """Generate aggregate report into folder

    :param str report_path: path to folder to save the report into.
    :rtype Report
    """
    if not self._generate_reports:
      return
    with GSFolder(report_url) as report_path:
      report = AggregateReport(report_path, "report.html", xkcd=self._xkcd)
      report.GenerateReport(aggregate_results)

  def _GatherBenchmarkSamples(self, subject, benchmark_def, metadata,
                              debug_flags):
    """Runs benchmark until enough measurements are collected.

    Returns None if running one of the benchmarks failed.

    :type subject: BenchmarkSubject
    :type metadata: dict
    :type debug_flags: List[str]
    :rtype Optional[BenchmarkResults]
    """
    aggregate = AggregateResults(benchmark_def.name, metadata)
    start_time = time.time()
    while True:
      benchmark = self._SafelyRunBenchmark(subject, benchmark_def, metadata,
                                           debug_flags)
      if not benchmark:
        return None
      aggregate.AddRepetition(benchmark.results)

      enough_samples = True
      msrmnts = aggregate.measurements
      for series_name, series_info in msrmnts.series_infos.iteritems():
        series_values = msrmnts.SummarizeValues(series_name)
        self._progress.Info(benchmark.name, "Collected %d samples for %s." %
                                             (len(series_values), series_name))
        if len(series_values) < series_info.min_num_samples:
          enough_samples = False
      if not enough_samples:
        self._progress.Info(benchmark.name, "Collecting more samples.")
      else:
        elapsed_time = time.time() - start_time
        aggregate.metadata["elapsed_time"] = elapsed_time
        return aggregate

  def _SafelyRunBenchmark(self, subject, benchmark_def, metadata, debug_flags):
    """Run benchmark and retry until successful.

    Returns None if the the benchmark failed MAX_BENCHMARK_TRIES times.

    :type subject: BenchmarkSubject
    :type metadata: dict
    :type debug_flags: List[str]
    :rtype Optional[Benchmark]
    """
    benchmark_time = datetime.now()
    metadata["time"] = benchmark_time

    for repetition in range(self.MAX_BENCHMARK_TRIES):
      full_name = "%s/%s" % (subject.name, benchmark_def.name)
      rep_name = "Benchmark (repetiton=%d)" % repetition
      self._progress.Info(full_name, "Running %s" % rep_name)

      benchmark = self._runner.CreateBenchmark(full_name,
          benchmark_def.benchmark_type, benchmark_def.activity,
          benchmark_def.params, metadata)
      self._runner.RunBenchmark(benchmark, debug_flags)

      self._StoreBenchmark(benchmark, subject, benchmark_time)

      if not len(benchmark.results.error):
        self._progress.Info(full_name, "Results:")
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
    base_name = str(time.strftime("%Y%m%d_%H%M"))
    return GSFindUniqueFilename(self._results_url, base_name)

  def _ListMatchingBenchmarks(self, match):
    """Lists (subject, benchmark_definition) for a match string

    :type match: str
    """
    benchmarks = { ("%s/%s" % (s.name, n)): (s, d)
                   for s in self._subjects.itervalues()
                   for n, d in s.benchmark_defs.iteritems() }

    match_fn = lambda name: fnmatch(name, match)
    matches = [n for n in benchmarks.iterkeys() if match_fn(n)]
    grouped = defaultdict(list)
    for match in matches:
      subject, definition = benchmarks[match]
      grouped[subject].append(definition)
    return grouped.iteritems()

  def _InsertResults(self, time, uid, subject, results):
    """Inserts results into database

    :type time: datetime
    :type uid: str
    :type subject_version: Optional[str]
    :type results: BenchmarkResults
    """
    dump = lambda array: ", ".join(str(array))

    for series_name in results.measurements.series_infos:
      values = results.measurements.SummarizeValues(series_name)
      row_data = dict(
          time=time,
          uid=uid,
          subject_name=subject.name,
          subject_version=subject.updater.installed_version,
          benchmark_name=results.benchmark_name,
          error=results.error,
          series_name=series_name,
          mean=np.mean(values),
          std=np.std(values),
          values=dump(values)
      )
      self._results_table.insert(row_data)

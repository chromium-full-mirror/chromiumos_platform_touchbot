# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from collections import defaultdict
from datetime import datetime
from fnmatch import fnmatch
import cPickle as pickle
import logging
import os
import sys
import time

from safetynet import Any, Dict, List, Optional, TypecheckMeta
import numpy as np

from optofidelity.benchmark import (AggregateResults, Benchmark,
                                    BenchmarkResults, BenchmarkRunner)
from optofidelity.reporting import AggregateReport, BenchmarkReport
from optofidelity.system import BenchmarkSystem
from optofidelity.util import (GSFindUniqueFilename, GSFolder, GSPathExists,
                               ProgressPrinter)

from .dashboard import Dashboard
from .orchestrator_subject import BenchmarkDefinition, OrchestratorSubject

_log = logging.getLogger(__name__)


def MatchName(name, pattern):
  if fnmatch(name, pattern):
    return True
  if name.split("/")[0] == pattern:
    return True
  return False


class Orchestrator(object):
  """Orchestrates running multiple tests and persistent storage or results.

  Each test that can be run by the orchestrator has a name in the format:
    dut_name/subject_name/benchmark_type
  """
  __metaclass__ = TypecheckMeta

  MAX_BENCHMARK_TRIES = 3
  """Maximum number of tries to run a benchmark before giving up."""

  FILED_BENCHMARKS_FILE = "failed_benchmarks.log"

  def __init__(self, benchmark_system, benchmark_runner, results_url,
               generate_reports=True, xkcd=False,
               save_video=False, quick=False, reports_url=None):
    """
    :type benchmark_system: BenchmarkSystem
    :type benchmark_runner: BenchmarkRunner
    :type results_url: str
    :type results_db_url: Optional[str]
    :param bool generate_reports: Generate reports for each benchmark
    :param bool xkcd: Give reports more authority
    """
    self._system = benchmark_system
    self._runner = benchmark_runner
    self.results_url = results_url
    self.reports_url = reports_url

    self._results_db = None
    self._results_table = None

    self._progress = ProgressPrinter(_log)
    self._generate_reports = generate_reports
    self._xkcd = xkcd
    self._subjects = {}
    self._save_video = save_video
    self._quick = quick

  @property
  def state(self):
    return {"subjects": {k: v.state for k, v in self._subjects.iteritems()}}

  @state.setter
  def state(self, state):
    for key, value in state["subjects"].iteritems():
      if key in self._subjects:
        self._subjects[key].state = value

  @classmethod
  def FromConfig(cls, parameters, children, system, runner):
    """
    :type parameters: Dict[str, str]
    :type children: List[Dict[str, str]]
    :type system: BenchmarkSystem
    :type runner: BenchmarkRunner
    """
    xkcd = parameters.get("xkcd") is not None
    results = parameters["results"]
    reports = parameters.get("reports")

    true_values = ("True", "true", "1")
    save_video = parameters.get("save-video", "") in true_values
    quick = parameters.get("quick", "") in true_values
    generate_reports = parameters.get("generate-reports", "True") in true_values
    return cls(system, runner, results, xkcd=xkcd,
               save_video=save_video, quick=quick, reports_url=reports,
               generate_reports=generate_reports)

  def PrintInfo(self, match):
    for subject in self._subjects.itervalues():
      if not MatchName(subject.name, match):
        continue
      print "Subject:", subject.name
      with subject.access:
        if not subject.Verify():
          print "  Cannot verify subject"
          continue
        installed_version = subject.updater.installed_version
        print "  Installed version:", installed_version

        print "  Available versions:"
        sys.stdout.write("    ")
        for i, version in enumerate(subject.updater.available_versions):
          if i % 6 == 0 and i != 0:
            sys.stdout.write("\n    ")
          if version == installed_version:
            version = "*" + version
          sys.stdout.write(version.ljust(16))
        print

      print "  Available benchmarks:"
      for benchmark_def in subject.benchmark_defs.itervalues():
        print "    %s/%s (type=%s activity=%s)" % (subject.name,
            benchmark_def.name, benchmark_def.benchmark_type,
            benchmark_def.activity)
      print

  def AddSubject(self, subject):
    """
    :type subject: OrchestratorSubject
    """
    self._subjects[subject.name] = subject

  def AccessSubjects(self, match):
    matched = False
    for subject in self._subjects.itervalues():
      if not MatchName(subject.name, match):
        continue
      matched = True
      subject.access.Activate()
      print "Subject '%s' is now accessible." % subject.name
      if subject.adb:
        print "ADB serial: %s" % subject.adb
    if not matched:
      print "No subject matching", match

  def SetUpSubjects(self, match, versions_string):
    """Runs setup on all subjects matching 'match'.

    :param str match: a glob on subject names
    """
    for subject in self._subjects.itervalues():
      if not MatchName(subject.name, match):
        continue
      with self._progress.LogExceptions("Error during setup"):
        self._progress.Info(subject.name, "Setting up Subject")
        with subject.access:
          subject.SetUp()

          if versions_string:
            versions = subject.GetMatchingVersions(versions_string, False)
            if len(versions) > 1:
              self._progress.Error(subject.name, "Pick a single version.")
            if not subject.Update(versions[0]):
              self._progress.Error(subject.name, "Cannot update subject.")

          if not subject.Verify():
            self._progress.Error(subject.name, "Subject is in a bad state.")

          self._runner.OpenAndCalibrateSubject(subject, self._save_video)
          self._runner.CloseSubject()

  def PrepareSubjects(self, match="*"):
    """Gets all subjects into testable state.

    :type subject: OrchestratorSubject
    """
    for subject in self._subjects.itervalues():
      if not MatchName(subject.name, match):
        continue
      with self._progress.LogExceptions("Error during prepare"):
        self._progress.Info(subject.name, "Preparing")
        with subject.access:
          subject.Prepare()

  def VerifySubjects(self, match="*"):
    """Gets all subjects into testable state.

    :type subject: OrchestratorSubject
    """
    for subject in self._subjects.itervalues():
      if not MatchName(subject.name, match):
        continue
      with self._progress.LogExceptions("Error during verify"):
        self._progress.Info(subject.name, "Verifying")
        with subject.access:
          subject.Verify()

  def DryRunBenchmarks(self, match="*"):
    for subject, benchmark_defs in self._ListMatchingBenchmarks(match):
      self._progress.Info(subject.name, "Access")
      with subject.access:
        try:
          subject.navigator.Open()
          for benchmark_def in benchmark_defs:
            full_name = "%s/%s" % (subject.name, benchmark_def.name)
            self._progress.Info(full_name, "Dry Run")
            benchmark = self._runner.CreateBenchmark(full_name,
                benchmark_def.benchmark_type, benchmark_def.activity,
                benchmark_def.params, {})
            benchmark.ExecuteOnSubject(subject)
        finally:
          subject.navigator.Cleanup()

  def UpdateAndRunBenchmarks(self, match, versions, skip_installed=False):
    """Runs updates and benchmarks on all bencharks matching 'match'

    This method should never throw Exceptions except for KeyboardInterrupts.

    :param match: A glob on benchmark names
    :param str versions: Specifies which versions to run:
           "40.0.2214.36" run only on a single specific version.
           "40" run on latest version that starts with 40.
           "40-" run on first version that starts with 40.
           "latest" run only on latest version
           "installed" run only on currently installed version.
           "40:43" run on range of versions between the specified matches.
    :param bool skip_installed: Don't run on the currently installed version.
    """
    for subject, benchmark_defs in self._ListMatchingBenchmarks(match):
      with self._progress.LogExceptions(subject.name, "Fatal Exception"):
        self.RunSubject(subject, benchmark_defs, versions, skip_installed)

  def RunSubject(self, subject, benchmark_defs, versions, skip_installed):
    """Run all benchmarks and versions on a single subject.

    This method should never throw Exceptions except for KeyboardInterrupts.

    :type subject: OrchestratorSubject
    :type benchmark_defs: List[BenchmarkDefinition]
    :type versions: str
    :type skip_installed: bool
    """
    with subject.access:
      if not subject.Verify():
        self._progress.Error(subject.name, "Subject in bad state.")
        return

      versions_to_test = subject.GetMatchingVersions(versions, skip_installed)
      if not versions_to_test:
        self._progress.Info(subject.name, "No versions to test.")
        return

      self._progress.Info(subject.name,
                          "Versions to test: %s" % (versions_to_test,))
      for version in versions_to_test:
        with self._progress.LogExceptions(subject.name, "Fatal Exception"):
          benchmark_names = [d.name for d in benchmark_defs]
          self._progress.Info(subject.name,
                              "Running benchmarks: %s" % (benchmark_names,))
          self.RunSubjectVersion(subject, benchmark_defs, version)
        if not subject.Verify():
          self._progress.Error(subject.name, "Subject in bad state.")
          return

  def RunSubjectVersion(self, subject, benchmark_defs, version):
    """Run all benchmarks on a single version/subject.

    This method should never throw Exceptions except for KeyboardInterrupts.

    :type subject: OrchestratorSubject
    :type benchmark_defs: List[BenchmarkDefinition]
    :type version: str
    """
    try:
      if not subject.Update(version):
        self._progress.Error(subject.name, "Update failed.")
        return dict()
      if not self.OpenAndCalibrateSubject(subject):
        self._progress.Error(subject.name, "Cannot open subject.")
        return dict()

      with self._progress.LogPerf(subject.name):
        for benchmark_def in benchmark_defs:
          with self._progress.LogExceptions(subject.name, "Fatal Exception"):
            self.RunSubjectVersionBenchmark(subject, benchmark_def, version)
    finally:
      with self._progress.LogExceptions(subject.name, "Subject closing"):
        self._runner.CloseSubject()

  def RunSubjectVersionBenchmark(self, subject, benchmark_def, version):
    """Run single benchmark on a subject/version.

    The benchmark is repeated multiple times to collect enough samples for
    statistically stable results.

    This method should never throw Exceptions except for KeyboardInterrupts.

    :type subject: OrchestratorSubject
    :type benchmark_def: BenchmarkDefinition
    :type version: str
    """
    metadata = dict(subject_version=version)
    full_name = "%s/%s" % (subject.name, benchmark_def.name)

    aggregate = AggregateResults(full_name, metadata)
    start_time = time.time()
    while True:
      benchmark = self.RunSubjectVersionBenchmarkRepetition(subject,
          benchmark_def, metadata)
      if not benchmark:
        self._progress.Error(full_name, "All repetitions failed!")
        return
      aggregate.AddRepetition(benchmark.results)

      if not self._quick and not aggregate.measurements.HasMinNumSamples():
        self._progress.Info(full_name, "Collecting more samples.")
      else:
        break

    elapsed_time = time.time() - start_time
    aggregate.metadata["elapsed_time"] = elapsed_time

    with self._progress.LogExceptions(full_name, "Fatal Exception"):
      self.PublishAggregateResults(subject, aggregate, version)
    self._progress.Info(full_name, "Aggregate Results:\n%s" % aggregate)
    return aggregate

  def RunSubjectVersionBenchmarkRepetition(self, subject, benchmark_def,
                                           metadata):
    """Run single benchmark repetition on a subject/version.

    This method should never throw Exceptions except for KeyboardInterrupts.

    :type subject: OrchestratorSubject
    :type benchmark_def: BenchmarkDefinition
    :type metadata: Dict[str, Any]
    """
    benchmark_time = datetime.now()
    metadata["time"] = benchmark_time
    full_name = "%s/%s" % (subject.name, benchmark_def.name)

    for repetition in range(self.MAX_BENCHMARK_TRIES):
      with self._progress.LogExceptions(full_name, "Fatal Exception"):
        rep_name = "Benchmark (repetiton=%d)" % repetition
        self._progress.Info(full_name, "Running %s" % rep_name)

        benchmark = self._runner.CreateBenchmark(full_name,
            benchmark_def.benchmark_type, benchmark_def.activity,
            benchmark_def.params, metadata)
        self._runner.RunBenchmark(benchmark)

        self.PublishBenchmarkRepetition(benchmark, subject, benchmark_time)
        if (len(benchmark.results.error) or
            not len(benchmark.results.measurements)):
          self._progress.Error(full_name, "%s failed." % rep_name)
          self._progress.LogFailure(full_name, "Benchmark failed",
                                    str(benchmark.results))
        else:
          self._progress.Info(full_name, "Results:\n%s" % benchmark.results)
          return benchmark
    return None

  def OpenAndCalibrateSubject(self, subject):
    """Safely open and calibrate a subject on the BenchmarkRunner.

    This method should never throw Exceptions except for KeyboardInterrupts.

    :type subject: OrchestratorSubject
    :returns bool: True if successful.
    """
    with self._progress.CaptureFailures(subject.name, "Subject calibration"):
      self._runner.OpenAndCalibrateSubject(subject, self._save_video)
      return True
    return False

  def PublishAggregateResults(self, subject, aggregate, version):
    """Publishes AggregateResults of a benchmark.

    Generates the reports and reports the results to the dashboard.

    :type subject: OrchestratorSubject
    :type aggregate: AggregateResults
    :type version: str
    :raises Exception: If Google cloud storage is offline
    """
    name = aggregate.benchmark_name

    benchmark_time = datetime.now()
    results_url, uid = self._FindUniqueResultsURL(benchmark_time)

    with GSFolder(results_url) as report_path:
      if not os.path.exists(report_path):
        os.mkdir(report_path)
      pickle_file = open(os.path.join(report_path, "results.pickle"), "wb")
      pickle.dump(aggregate, pickle_file, protocol=pickle.HIGHEST_PROTOCOL)
      if self._generate_reports:
        report = AggregateReport(report_path, xkcd=self._xkcd)
        report.GenerateReport(aggregate)

    public_url = self._GetPublicReportUrl(results_url)
    aggregate.report_url = public_url
    aggregate.uid = uid
    self._progress.Info(name,
                        "Aggregate report available at: %s" % public_url)

    if subject.dashboard:
      self._progress.Info(name, "Reporting results to dashboard")
      subject.dashboard.ReportResults(aggregate, version,
                                      public_url)

  def PublishBenchmarkRepetition(self, benchmark, subject, time):
    """Store benchmark to results folder and register in database.

    :type benchmark: Benchmark
    :type subject: OrchestratorSubject
    :type time: datetime
    :raises Exception: If Google cloud storage is offline
    """
    results_url, uid = self._FindUniqueResultsURL(time)
    public_url = self._GetPublicReportUrl(results_url)
    benchmark.results.report_url = public_url
    benchmark.results.uid = uid

    self._progress.Info(benchmark.name, "Saving benchmark to %s" % results_url)
    save_video = self._save_video or bool(len(benchmark.results.error))
    benchmark.Save(results_url, debug_info=True, video=save_video)

    with GSFolder(results_url) as report_path:
      additional_links = []
      for collector in subject.collectors:
        additional_links.extend(collector.report_links)
        collector.Save(report_path)
      if self._generate_reports:
        report = BenchmarkReport(report_path, xkcd=self._xkcd)
        report.GenerateReport(benchmark.results, benchmark.trace,
                              benchmark.screen_calibration, benchmark.video,
                              additional_links)
        self._progress.Info(benchmark.name, "Repetition report available at: %s"
                                            % public_url)

  def _GetPublicReportUrl(self, url):
    if self.reports_url:
      url = url.replace(self.results_url, self.reports_url)
    return os.path.join(url, "report.html")

  def _FindUniqueResultsURL(self, time):
    """Find a unique folder to store results into.

    This will return a folder name of the following format:
    results_path/date_time_000/
    With 000 being an increasing number.

    :type time: datetime
    :rtype str
    :raises Exception: If Google cloud storage is offline
    """
    base_name = str(time.strftime("%Y%m%d_%H%M_"))
    return GSFindUniqueFilename(self.results_url, base_name)

  def _ListMatchingBenchmarks(self, match):
    """Lists (subject, benchmark_definition) for a match string

    :type match: str
    """
    benchmarks = { ("%s/%s" % (s.name, n)): (s, d)
                   for s in self._subjects.itervalues()
                   for n, d in s.benchmark_defs.iteritems() }

    match_fn = lambda name: MatchName(name, match)
    matches = [n for n in benchmarks.iterkeys() if match_fn(n)]
    grouped = defaultdict(list)
    for match in matches:
      subject, definition = benchmarks[match]
      grouped[subject].append(definition)
    return grouped.iteritems()

# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from datetime import datetime
from fnmatch import fnmatch
import logging
import os

from safetynet import List, Optional, TypecheckMeta

from optofidelity.benchmark import Benchmark, BenchmarkResults, BenchmarkRunner
from optofidelity.system import BenchmarkSystem, BenchmarkSubject
import dataset

_log = logging.getLogger(__name__)

class Orchestrator(object):
  """Orchestrates running multiple tests and persistent storage or results.

  Each test that can be run by the orchestrator has a name in the format:
    dut_name/subject_name/benchmark_type
  """
  __metaclass__ = TypecheckMeta

  def __init__(self, benchmark_system, benchmark_runner, results_dir,
               results_db_url, print_progress=False):
    """
    :type benchmark_system: BenchmarkSystem
    :type benchmark_runner: BenchmarkRunner
    :type results_dir: str
    """
    self._system = benchmark_system
    self._runner = benchmark_runner
    self._results_dir = results_dir
    self._print_progress = print_progress

    self._results_db = dataset.connect(results_db_url)
    self._results_table = self._results_db["benchmark_results"]

  def PrintProgress(self, message, *args):
    _log.info(message, *args)
    if self._print_progress:
      print message % args

  def RunTest(self, subject, benchmark_type, debug_flags):
    """Run a single test case and store results in database.

    :type subject_name: str
    :type benchmark_type: str
    :type debug_flags: List[str]
    """
    time = datetime.now()
    subject_version = subject.updater.installed_version
    metadata = dict(time=time)
    if subject_version:
      metadata["subject_version"] = subject_version

    self.PrintProgress("%s/%s: Running benchmark", subject.name, benchmark_type)
    benchmark = self._runner.RunBenchmark(subject, benchmark_type, metadata,
                                          debug_flags, self._print_progress)

    results_path, uid = self._FindUniqueResultsFolder(time)
    self.PrintProgress("%s/%s: Saving to %s", subject.name, benchmark_type,
                       results_path)
    benchmark.Save(results_path)
    self._InsertResults(time, uid, subject_version, benchmark.results)

  def RunTests(self, match, debug_flags):
    """Run all tests matching 'match' and save results to database.

    :param str match: One of the following:
           - The full name of a test
           - The beginning of the name of a test
           - A unix glob
    :type debug_flags: List[str]
    """
    for subject_name, benchmark_type in self._ListMatchingBenchmarks(match):
      subject = self._system.subjects[subject_name]
      self.RunTest(subject, benchmark_type, debug_flags)

  def UpdateAndRunTests(self, match, debug_flags, forced_version=None):
    """Update, then run all tests matching 'match' and save results.

    This will update all subjects before runnin the tests and only run tests
    if they have been updated.

    :param str match: One of the following:
           - The full name of a test
           - The beginning of the name of a test
           - A unix glob
    :type debug_flags: List[str]
    :param Optional[str] forced_version: Force version number to test.
    """
    for subject_name, benchmark_type in self._ListMatchingBenchmarks(match):
      subject = self._system.subjects[subject_name]
      if self.UpdateSubject(subject, forced_version):
        self.RunTest(subject, benchmark_type, debug_flags)

  def UpdateSubject(self, subject, forced_version=None):
    """Update subject to latest or custom version.

    :type subject: BenchmarkSubject
    :param Optional[str] forced_version: Force version number install
    :returns bool: True if the subject has been updated.
    """
    self.PrintProgress("%s: Checking for updates", subject.name)
    available = subject.updater.available_versions
    target_version = None
    if forced_version:
      self.PrintProgress("%s: Forcing version %s", subject.name,
                         forced_version)
      for version in available:
        if fnmatch(version, forced_version):
          target_version = version
          break
      if not target_version:
        raise ValueError("Version %s is not available" % forced_version)
    else:
      target_version = available[0]
      if target_version == subject.updater.installed_version:
        self.PrintProgress("%s: Version %s is already installed", subject.name,
                           target_version)
        return False
    subject.updater.Install(target_version, self._print_progress)
    return True

  def QueryResults(self):
    """Return iterator over all results in database."""
    return self._results_table.all()

  def _FindUniqueResultsFolder(self, time):
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
      results_path = os.path.join(self._results_dir, uid)
      if not os.path.exists(results_path):
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
    for match in matches:
      yield benchmarks[match]

  def _InsertResults(self, time, uid, subject_version, results):
    """Inserts results into database

    :type time: datetime
    :type uid: str
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

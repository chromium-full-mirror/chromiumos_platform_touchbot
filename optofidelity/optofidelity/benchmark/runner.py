# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contextlib import contextmanager
import logging
import time
import traceback

from safetynet import Any, Dict, InterfaceMeta, List

from optofidelity.detection import ScreenCalibration, VideoProcessor
from optofidelity.system import BenchmarkSubject, BenchmarkSystem
from optofidelity.util import LogCapture, ProgressPrinter

from .benchmark import Benchmark

_log = logging.getLogger(__name__)


class BenchmarkRunner(object):
  """Runs benchmarks on BenchmarkSubjects.

  Basic usage:
  with runner.UseSubject(subject):
    benchmark = runner.RunBenchmark("tap", metadata, debug_flags)
    benchmark2 = runner.RunBenchmark("scroll", metadata, debug_flags)
    ...
  """
  __metaclass__ = InterfaceMeta
  MAX_REPETITIONS = 3

  def __init__(self, benchmark_system, video_processor):
    """
    :type benchmark_system: BenchmarkSystem
    :type video_processor: VideoProcessor
    """
    self.benchmark_system = benchmark_system
    self.video_processor = video_processor
    self._progress = ProgressPrinter(_log)

  @contextmanager
  def UseSubject(self, subject):
    """Context manager to allow running of benchmarks on a subject.

    The context manager will open and calibrate the subject on entering, and
    close the subject on exiting.
    :type subject: BenchmarkSubject
    """
    try:
      self._screen_calibration = self._OpenAndCalibrateSubject(subject)
      self._current_subject = subject
      yield
    finally:
      self._screen_calibration = None
      self._current_subject = None
      subject.navigator.Cleanup()

  def RunBenchmark(self, benchmark_type, metadata, debug_flags):
    """Run benchmark on subject picked with UseSubject.

    This method has to be called within the context of UseSubject.
    :type benchmark_type: str
    :type metadata: Dict[str, Any]
    :type debug_flags: List[str]
    :rtype Benchmark
    """
    if not self._current_subject:
      raise Exception("Must be executed within the context of UseSubject.")

    benchmark = Benchmark(self._current_subject.name, benchmark_type, metadata,
                          self._screen_calibration)
    self._ExecuteBenchmark(benchmark, debug_flags)
    return benchmark

  def _OpenAndCalibrateSubject(self, subject):
    """Open a subject and calibrate screen.

    :type subject: BenchmarkSubject
    :rtype: ScreenCalibration
    """
    try:
      self._progress.Info(subject.name, "Opening and calibrating")
      subject.navigator.Open(False)
      return self._CalibrateScreen(subject)
    except KeyboardInterrupt:
      raise
    except:
      self._progress.Exception(subject.name,
                               "Caught Exception. Retrying in safe mode.")
      # Failed? Re-try using safe-mode Open.
      subject.navigator.Reset()
      subject.navigator.Open(True)
      return self._CalibrateScreen(subject)

  def _ExecuteBenchmark(self, benchmark, debug_flags):
    """Execute all steps of benchmark processing.

    All log output is captured, so are exceptions. They are available in
    benchmark.log and benchmark.error.

    :type benchmark: Benchmark
    :type debug_flags: List[str]
    """
    start_time = time.time()
    capture = LogCapture()
    with capture:
      try:
        self._progress.Info(benchmark.name, "Executing benchmark")
        benchmark.ExecuteOnSubject(self.benchmark_system)
        self._progress.Info(benchmark.name, "Processing video")
        benchmark.ProcessVideo(self.video_processor, debug_flags)
        self._progress.Info(benchmark.name, "Processing trace")
        benchmark.ProcessTrace()
      except KeyboardInterrupt:
        raise
      except:
        self._progress.Exception(benchmark.name)
        benchmark.results.error = traceback.format_exc()
    elapsed_time = time.time() - start_time
    benchmark.results.metadata["elapsed_time"] =  "%ds" % elapsed_time
    benchmark.log = capture.log

  def _CalibrateScreen(self, subject):
    """Execute the screen calibration process.

    :type subject: BenchmarkSubject
    :rtype ScreenCalibration
    """
    self._progress.Info(subject.name, "Calibrating screen")
    video_reader = subject.RecordCalibrationVideo()
    screen_calibration = self.video_processor.CreateScreenCalibration(
        video_reader)
    return screen_calibration

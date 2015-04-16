# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import traceback

from safetynet import Any, Dict, InterfaceMeta, List

from optofidelity.detection import ScreenCalibration, VideoProcessor
from optofidelity.system import BenchmarkSystem, BenchmarkSubject
from optofidelity.util import LogCapture

from .benchmark import Benchmark

_log = logging.getLogger(__name__)


class BenchmarkRunner(object):
  __metaclass__ = InterfaceMeta

  def __init__(self, benchmark_system, video_processor, print_progress=False):
    """
    :type benchmark_system: BenchmarkSystem
    :type video_processor: VideoProcessor
    :type print_progress: bool
    """
    self.benchmark_system = benchmark_system
    self.video_processor = video_processor
    self._print_progress = print_progress

  def RunBenchmarks(self, subject, benchmark_types, metadata, debug_flags):
    """Run multiple benchmarks on a subject.

    This method will run all benchmarks listed in benchmark_types and yield
    the resulting Benchmark containing results and potential errors.

    :type subject: BenchmarkSubject
    :type benchmark_types: List[str]
    :type metadata: Dict[str, Any]
    :type debug_flags: List[str]
    :yields Benchmark: Benchmark results
    """
    try:
      screen_calibration = self._OpenAndCalibrateSubject(subject)
      for benchmark_type in benchmark_types:
        benchmark = Benchmark(subject.name, benchmark_type, metadata,
                              screen_calibration)
        self._ExecuteBenchmark(benchmark, debug_flags)
        yield benchmark
    finally:
      subject.Close()

  def RunBenchmark(self, subject, benchmark_type, metadata, debug_flags):
    """Run single benchmark on a subject.

    This is a shorthand to call RunBenchmarks with a single benchmark_type.

    :type subject: BenchmarkSubject
    :type benchmark_types: List[str]
    :type metadata: Dict[str, Any]
    :type debug_flags: List[str]
    :rtype: Benchmark
    """
    benchmarks = self.RunBenchmarks(subject, [benchmark_type], metadata,
                                    debug_flags)
    return benchmarks.next()

  def _OpenAndCalibrateSubject(self, subject):
    """Open a subject and calibrate screen.

    :type subject: BenchmarkSubject
    :rtype: ScreenCalibration
    """
    try:
      subject.Open(False)
      return self._CalibrateScreen(subject)
    except:
      # Failed? Re-try using safe-mode Open.
      subject.Reset()
      subject.Open(True)
      return self._CalibrateScreen(subject)

  def _ExecuteBenchmark(self, benchmark, debug_flags):
    """Execute all steps of benchmark processing.

    All log output is captured, so are exceptions. They are available in
    benchmark.log and benchmark.error.

    :type benchmark: Benchmark
    :type debug_flags: List[str]
    """
    def PrintProgress(msg):
      self._PrintProgress(benchmark.subject_name, benchmark.benchmark_type, msg)

    capture = LogCapture()
    with capture:
      try:
        PrintProgress("Executing benchmark")
        benchmark.ExecuteOnSubject(self.benchmark_system)
        PrintProgress("Processing video")
        benchmark.ProcessVideo(self.video_processor, debug_flags,
                               self._print_progress)
        PrintProgress("Processing trace")
        benchmark.ProcessTrace()
      except:
        PrintProgress("Exception during benchmark")
        if self._print_progress:
          traceback.print_exception()
        _log.exception("")
        benchmark.error = traceback.format_exc()
    benchmark.log = capture.log

  def _CalibrateScreen(self, subject):
    """Execute the screen calibration process.

    :type subject: BenchmarkSubject
    :rtype ScreenCalibration
    """
    self._PrintProgress(subject.name, None, "Calibrating screen")
    video_reader = subject.RecordCalibrationVideo()
    screen_calibration = self.video_processor.CreateScreenCalibration(
        video_reader)
    return screen_calibration

  def _PrintProgress(self, subject_name, benchmark_type, msg):
    if benchmark_type:
      message = "%s/%s: %s" % (subject_name, benchmark_type, msg)
    else:
      message = "%s: %s" % (subject_name, msg)
    _log.info(message)
    if self._print_progress:
      print message

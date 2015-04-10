# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from optofidelity.detection import VideoProcessor
from optofidelity.system import BenchmarkSystem
from optofidelity.util import LogCapture

from .benchmark import Benchmark

_log = logging.getLogger(__name__)


class BenchmarkRunner(object):
  def __init__(self, benchmark_system, video_processor, ):
    self.benchmark_system = benchmark_system
    self.video_processor = video_processor

  def RunBenchmark(self, subject, benchmark_type, metadata, debug_flags,
                   print_progress=False):
    def PrintProgress(msg):
      message = "%s/%s: %s" % (subject.name, benchmark_type, msg)
      _log.info(message)
      if print_progress:
        print message

    capture = LogCapture()
    with capture:
      benchmark = Benchmark(subject.name, benchmark_type, metadata)
      PrintProgress("Calibrating screen")
      benchmark.CalibrateScreen(self.benchmark_system, self.video_processor)
      PrintProgress("Executing benchmark")
      benchmark.ExecuteOnSubject(self.benchmark_system)
      PrintProgress("Processing video")
      benchmark.ProcessVideo(self.video_processor, debug_flags, print_progress)
      PrintProgress("Processing trace")
      benchmark.ProcessTrace()
    benchmark.log = capture.log
    return benchmark

# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from .benchmark import Benchmark
from optofidelity.system import BenchmarkSystem
from optofidelity.detection import VideoProcessor


class BenchmarkRunner(object):
  def __init__(self, benchmark_system, video_processor):
    self.benchmark_system = benchmark_system
    self.video_processor = video_processor

  def RunBenchmark(self, subject, benchmark_type, metadata, debug_flags,
                   print_progress=False):
    benchmark = Benchmark(subject.name, benchmark_type, metadata)
    benchmark.CalibrateScreen(self.benchmark_system, self.video_processor)
    benchmark.ExecuteOnSubject(self.benchmark_system)
    benchmark.ProcessVideo(self.video_processor, debug_flags, print_progress)
    benchmark.ProcessTrace()
    return benchmark

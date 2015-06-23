# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from safetynet import Optional

from optofidelity.detection import Trace, VideoProcessor
from optofidelity.detection.fake import FakeVideoProcessor
from optofidelity.system import BenchmarkSystem
from optofidelity.system.fake import FakeBenchmarkSystem

from .benchmark import Benchmark
from .runner import BenchmarkRunner


class FakeBenchmarkRunner(BenchmarkRunner):
  """Fake BenchmarkRunner that can return fixed instances of Benchmarks.

  By providing a fake_trace, the video processing can be skipped and forced
  to return the specified trace.
  By providing a fake_benchmark, the whole benchmark execution is skipped to
  return the specified instance.
  """

  def __init__(self, benchmark_system=None, video_processor=None,
               fake_trace=None, fake_benchmark=None):
    """
    The FakeBenchmarkRunner will automatically create a FakeBenchmarkSystem
    as well as a FakeVideoProcessor if none are provided.

    :type benchmark_system: Optional[BenchmarkSystem]
    :type video_processor: Optional[VideoProcessor]
    :type fake_trace: Optional[Trace]
    :type fake_benchmark: Optional[Benchmark]
    """
    super(FakeBenchmarkRunner, self).__init__(
        benchmark_system or FakeBenchmarkSystem(),
        video_processor or FakeVideoProcessor())
    self.fake_benchmark = fake_benchmark
    self.video_processor.fake_trace = fake_trace

  @classmethod
  def FromTrace(cls, fake_trace, benchmark_type, metadata):
    runner = FakeBenchmarkRunner(fake_trace=fake_trace)
    with runner.UseSubject(runner.benchmark_system.fake_subject):
      benchmark = runner.CreateBenchmark("fake", benchmark_type, "fake", {},
                                         metadata)
      runner.RunBenchmark(benchmark, [])
      return benchmark

  def CreateBenchmark(self, name, benchmark_type, activity, parameters,
                      metadata):
    if self.fake_benchmark:
      return self.fake_benchmark
    return super(FakeBenchmarkRunner, self).CreateBenchmark(name,
        benchmark_type, activity, parameters, metadata)

  def RunBenchmark(self, benchmark, debug_flags):
    if self.fake_benchmark:
      return
    super(FakeBenchmarkRunner, self).RunBenchmark(benchmark, debug_flags)

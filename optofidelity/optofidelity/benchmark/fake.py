# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from safetynet import Any, Dict, Optional

from optofidelity.detection import Trace
from optofidelity.videoproc import FakeVideoReader, VideoReader

from ._delegate import BenchmarkDelegate
from .benchmark import Benchmark


class FakeBenchmark(Benchmark):
  """Fake implementation of a benchmark.

  This class allows the user to specify a video and trace instead of relying
  on the expensive ExecuteOnSubject and ProcessVideo calls to generate them.
  """
  FAKE_VIDEO_LENGTH = 10000
  FAKE_VIDEO_SHAPE = (720, 1280)
  FAKE_VIDEO_FPS = 300

  def __init__(self, subject_name, benchmark_type, metadata, video, trace,
               delegate):
    """
    :param str subject_name: Name of the subject this benchmark is going to be
           executed on.
    :param str benchmark_type: One of the types defined in BENCHMARK_TYPES.
    :param Dict[str, Any] metadata: Metainformation to be stored along with the
           benchmark.
    :param Optional[VideoReader] video: Override video. A FakeVideoReader is
           created if not specified.
    :param Optional[Trace] trace: Override trace.
    :param Optional[BenchmarkDelegate] delegate: Overrides the delegate that is
           used for the benchmark execution.
    """
    super(FakeBenchmark, self).__init__(subject_name, benchmark_type, metadata,
                                        delegate)

    self.video = video or FakeVideoReader(self.FAKE_VIDEO_LENGTH,
                                          self.FAKE_VIDEO_SHAPE,
                                          self.FAKE_VIDEO_FPS)
    self.framerate = self.video.framerate
    self.trace = trace

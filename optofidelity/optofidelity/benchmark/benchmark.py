# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of Benchmark."""

import cPickle as pickle
import logging
import os
import time

from safetynet import Any, Dict, List, Optional, TypecheckMeta
import skimage.io as io

from optofidelity.detection import CreateVideoProcessor, ScreenCalibration
from optofidelity.system import BenchmarkSystem
from optofidelity.videoproc import FileVideoReader

from ._delegate import BenchmarkDelegate
from ._line_delegates import (ScrollDelegate, ScrollStartDelegate,
                              TouchMoveDelegate, TouchMoveStartDelegate)
from ._report import Report
from ._tap_delegate import TapDelegate
from ._trace_figures import TraceOverviewFigure
from .results import BenchmarkResults

_log = logging.getLogger("benchmark")
_perf_log = logging.getLogger("perf")


class Benchmark(object):
  """Represents a single benchmark that can be executed and serialized.

  A benchmark integrates the robot and video processing and allows benchmarks of
  the following types to be executed:

  - touch_move: Line draw latency on the 'move' page of the subject.
  - scroll: Line draw latency on the 'scroll' page of the subject.
  - touch_move_start: Line draw start latency on the 'move' page of the subject.
  - scroll_start: Line draw start latency on the 'scroll' page of the subject.
  - tap: Tap latency

  The line draw latency measurement measures the time between a line draw and
  when the finger has crossed the location of line draw.

  The line draw start measurement measures the time from when the finger starts
  moving to the first reaction of the screen.

  The tap latency measurement measures the time between the touch down of the
  robot finger until the screen flashes.

  For the video processing to work, a benchmark requires a screen calibration,
  which can either be executed with CalibrateScreen or provided from a previous
  calibration via UseExistingCalibration.

  The overall process is divided into 3 stages that have to be executed in the
  right order: ExecuteOnSubject, ProcessVideo and ProcessTrace. All 3 can be
  executed together using the Run method.
  """

  __metaclass__ = TypecheckMeta

  BENCHMARK_TYPES = {
    "touch_move": TouchMoveDelegate,
    "scroll": ScrollDelegate,
    "scroll_start": ScrollStartDelegate,
    "touch_move_start": TouchMoveStartDelegate,
    "tap": TapDelegate
  }

  def __init__(self, subject_name, benchmark_type, metadata, _delegate=None):
    """Provide information on new benchmark.

    :param str subject_name: Name of the subject this benchmark is going to be
           executed on.
    :param str benchmark_type: One of the types defined in BENCHMARK_TYPES.
    :param Dict[str, Any] metadata: Metainformation to be stored along with the
           benchmark.
    :param Optional[BenchmarkDelegate] _delegate: Overrides the delegate that is
           used for the benchmark execution. For internal use only.
    """
    self._benchmark_type = benchmark_type
    self._delegate = _delegate or self.BENCHMARK_TYPES[benchmark_type]()
    self._subject_name = subject_name

    self.screen_calibration = None
    self.framerate = None
    self.results = None
    self.metadata = metadata
    self.trace = None
    self.video = None

  @property
  def ms_per_frame(self):
    return 1000.0 / float(self.framerate)

  def CalibrateScreen(self, benchmark_system):
    """Execute the required screen calibration process.

    :type benchmark_system: BenchmarkSystem
    """
    subject = benchmark_system.subjects[self._subject_name]
    video_reader = subject.RecordCalibrationVideo()
    self.screen_calibration = ScreenCalibration.FromScreenFlashVideo(
        video_reader)

  def UseExistingCalibration(self, screen_calibration):
    """Use previously calculated screen calibration for this benchmark.

    :type screen_calibration ScreenCalibration
    """
    self.screen_calibration = screen_calibration

  def ExecuteOnSubject(self, benchmark_system):
    """Instruct the robot to execute the benchmark.

    :type benchmark_system BenchmarkSystem
    """
    subject = benchmark_system.subjects[self._subject_name]
    self.video = self._delegate.ExecuteOnSubject(subject)
    self.framerate = self.video.framerate
    self.trace = None
    self.results = None
    self.report = None
    return self.video

  def ProcessVideo(self, debug_flags, print_progress, multithreaded):
    """Process the recorded video into a trace.

    This step requires that ExecuteOnSubject and CalibrateScreen (or
    UseExistingCalibration) have been called before.

    :param List[str] debug_flags: list of debug flags for the VideoProcessor.
    :param bool print_progress: Print progress report to console.
    :param bool multithreaded: Use all cores of the system to do processing.
    :rtype Trace
    """
    assert self.video, "No test video"
    assert self.screen_calibration, "No screen calibration"

    processor = CreateVideoProcessor(self.screen_calibration, multithreaded)
    self._delegate.InitializeProcessor(processor)

    start_t = time.time()
    self.trace = processor.ProcessVideo(self.video, debug_flags, print_progress)
    self.results = None
    self.report = None

    delta_t = (time.time() - start_t)
    delta_t_per_frame = delta_t / self.video.num_frames
    _perf_log.info("Processing: %f s", delta_t)
    _perf_log.info("            %f ms / frame", (delta_t_per_frame * 1000))

    return self.trace

  def ProcessTrace(self):
    """Process the calculated trace into latency measurements.

    :rtype BenchmarkResults
    """
    assert self.trace is not None, "No test trace"

    start_t = time.time()
    self.results = BenchmarkResults(self._subject_name, self._benchmark_type,
                                    self.metadata)
    self._delegate.ProcessTrace(self.trace, self.results)
    self.report = None

    _perf_log.info("Trace processing: %f s", (time.time() - start_t))
    return self.results

  def GenerateReport(self, report_path):
    """Generate HTML into folder.

    :param str report_path: path to folder to save the report into.
    :rtype Report
    """
    assert self.results is not None, "No benchmark results"
    self.report = Report(report_path, "report.html", self.ms_per_frame)
    self.report.GenerateReport(self.results, self.trace,
                               self.screen_calibration, self.video)
    return self.report

  def Run(self, benchmark_system, debug_flags, print_progress=False,
          multithreaded=True):
    """Run the whole benchmark process.

    :type benchmark_system: BenchmarkSystem
    :param List[str] debug_flags: list of debug flags for the VideoProcessor.
    :param bool print_progress: Print progress report to console.
    :param bool multithreaded: Use all cores of the system to do processing.
    """
    self.ExecuteOnSubject(benchmark_system)
    self.ProcessVideo(debug_flags, print_progress, multithreaded)
    return self.ProcessTrace()

  def Save(self, path, debug_info=False, video=False):
    """Serialize benchmark to a folder on disk.

    The benchmark is saved into multiple files in the folder specified in path.

    :param str path: path to folder.
    :param bool debug_info: Extract human readable debug information
    :param bool video: Save video too, this allows you to call ProcessVideo
           after serialization.
    """
    if not os.path.exists(path):
      os.makedirs(path)

    pickle_file = open(self._GetPickleFileName(path), "w")
    pickle.dump(self, pickle_file, protocol=pickle.HIGHEST_PROTOCOL)
    if debug_info:
      self._SaveDebugInfo(path)
    if video and self.video:
      self.video.Save(self._GetVideoFileName(path), True)

  def _SaveDebugInfo(self, path):
    """Save human readable debug information into benchmark folder.

    :param str path: path to folder.
    """
    calib = self.screen_calibration
    if calib:
      io.imsave(os.path.join(path, "calibration_black.png"), calib.black_frame)
      io.imsave(os.path.join(path, "calibration_white.png"), calib.white_frame)
    if self.trace:
      pickle.dump(self.trace, open(os.path.join(path, "trace.pickle"), "w"))
      figure = TraceOverviewFigure(1024, 512, 256, self.ms_per_frame)
      figure.PlotTrace(self.trace, 0.0, 0.0)
      figure.Save(os.path.join(path, "trace.png"), False)

    def DumpProperty(variable_name):
      data = getattr(self, variable_name)
      if data:
        with open(os.path.join(path, "%s.txt" % variable_name), "w") as file:
          file.write(str(data))
    DumpProperty("trace")
    DumpProperty("results")
    DumpProperty("metadata")

  @classmethod
  def Load(cls, path):
    """Load benchmark from folder.

    :param str path: folder to load from.
    """
    pickle_file = open(cls._GetPickleFileName(path), "r")
    self = pickle.load(pickle_file)

    video_file = cls._GetVideoFileName(path)
    if os.path.exists(video_file):
      self.video = FileVideoReader(video_file, self.framerate)
    return self

  @classmethod
  def _GetPickleFileName(cls, path):
    return os.path.join(path, "benchmark.pickle")

  @classmethod
  def _GetVideoFileName(cls, path):
    return os.path.join(path, "video.avi")

  def __getstate__(self):
    state = dict(self.__dict__)
    del state["video"]
    return state

  def __setstate__(self, state):
    subject_name = state["_subject_name"]
    benchmark_type = state["_benchmark_type"]
    metadata = state["metadata"]
    _delegate = state["_delegate"]
    self.__init__(subject_name, benchmark_type, metadata, _delegate)
    self.__dict__.update(state)

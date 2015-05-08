# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of Benchmark."""

import cPickle as pickle
import logging
import os
import time

from safetynet import Any, Dict, List, Optional, TypecheckMeta

from optofidelity.detection import (LEDEvent, ScreenCalibration, Trace,
                                    VideoProcessor)
from optofidelity.gsutil import GSFile, GSFolder, GSOpenFile, GSPathExists
from optofidelity.system import BenchmarkSystem
from optofidelity.videoproc import FileVideoReader, SaveImage

from ._delegate import BenchmarkDelegate
from ._line_delegates import (ScrollDelegate, ScrollStartDelegate,
                              TouchMoveDelegate, TouchMoveStartDelegate)
from ._tap_delegate import TapDelegate
from .results import BenchmarkResults, MeasurementList

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

  def __init__(self, subject_name, benchmark_type, metadata, screen_calibration,
               _delegate=None):
    """Provide information on new benchmark.

    :param str subject_name: Name of the subject this benchmark is going to be
           executed on.
    :param str benchmark_type: One of the types defined in BENCHMARK_TYPES.
    :param Dict[str, Any] metadata: Metainformation to be stored along with the
           benchmark.
    :param Optional[BenchmarkDelegate] _delegate: Overrides the delegate that is
           used for the benchmark execution. For internal use only.
    """
    self.benchmark_type = benchmark_type
    self._delegate = _delegate or self.BENCHMARK_TYPES[benchmark_type]()
    self.subject_name = subject_name
    self.finger_calib_delay = (0.0, 0.0)
    self.name = "%s/%s" % (subject_name, benchmark_type)

    self.screen_calibration = screen_calibration
    self.framerate = None
    self.results = BenchmarkResults(subject_name, benchmark_type, metadata)
    self.metadata = metadata
    self.trace = None
    self.video = None

    self.log = ""

  @property
  def calibrated_trace(self):
    """Trace with applied finger led calibration."""
    def ApplyLEDCalib(event):
      if isinstance(event, LEDEvent):
        if event.state == LEDEvent.STATE_ON:
          return LEDEvent(int(event.time - self.finger_calib_delay.down),
                          event.state)
        else:
          return LEDEvent(int(event.time + self.finger_calib_delay.up),
                          event.state)
      return event
    return Trace([ApplyLEDCalib(e) for e in self.trace],
                 self.trace.ms_per_frame)

  def ExecuteOnSubject(self, benchmark_system):
    """Instruct the robot to execute the benchmark.

    :type benchmark_system: Optional[BenchmarkSystem]
    """
    subject = self._GetSubject(benchmark_system)
    self.video = self._delegate.ExecuteOnSubject(subject)
    self.framerate = self.video.framerate
    self.finger_calib_delay = benchmark_system.finger_calib_delay
    self.trace = None
    self.results.measurement_list = MeasurementList()
    return self.video

  def ProcessVideo(self, video_processor, debug_flags):
    """Process the recorded video into a trace.

    This step requires that ExecuteOnSubject and CalibrateScreen (or
    UseExistingCalibration) have been called before.

    :param List[str] debug_flags: list of debug flags for the VideoProcessor.
    :param bool multithreaded: Use all cores of the system to do processing.
    :rtype Trace
    """
    assert self.video, "No test video"

    self._delegate.InitializeProcessor(video_processor)

    start_t = time.time()
    self.trace = video_processor.ProcessVideo(self.video,
                                              self.screen_calibration,
                                              debug_flags)
    self.results.measurement_list = MeasurementList()

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
    self.results.measurement_list = MeasurementList()
    self._delegate.ProcessTrace(self.calibrated_trace, self.results)

    _perf_log.info("Trace processing: %f s", (time.time() - start_t))
    return self.results

  def Save(self, url, debug_info=False, video=False):
    """Serialize benchmark to a folder on disk.

    The benchmark is saved into multiple files in the folder specified in path.

    :param str path: path to folder.
    :param bool debug_info: Extract human readable debug information
    :param bool video: Save video too, this allows you to call ProcessVideo
           after serialization.
    """
    with GSFolder(url) as path:
      if not os.path.exists(path):
        os.makedirs(path)

      with open(self._GetPickleFileName(path), "w") as pickle_file:
        pickle.dump(self, pickle_file, protocol=pickle.HIGHEST_PROTOCOL)
      if debug_info:
        self._SaveDebugInfo(path)
      if video and self.video:
        self.video.Save(self._GetVideoFileName(path))

  def _SaveDebugInfo(self, path):
    """Save human readable debug information into benchmark folder.

    :param str path: path to folder.
    """
    calib = self.screen_calibration
    if calib:
      SaveImage(os.path.join(path, "calibration_black.png"), calib.black_frame)
      SaveImage(os.path.join(path, "calibration_white.png"), calib.white_frame)
    if self.trace:
      with open(os.path.join(path, "trace.pickle"), "w") as pickle_file:
        pickle.dump(self.trace, pickle_file)

    def DumpProperty(variable_name):
      data = getattr(self, variable_name)
      if data is not None:
        with open(os.path.join(path, "%s.txt" % variable_name), "w") as file:
          file.write(str(data))
    DumpProperty("trace")
    DumpProperty("results")
    DumpProperty("metadata")
    DumpProperty("log")

  @classmethod
  def Load(cls, url):
    """Load benchmark from folder or cloud storage

    :param str url: local folder or gs:// url
    """
    with GSOpenFile(cls._GetPickleFileName(url), "r") as pickle_file:
      self = pickle.load(pickle_file)

    video_url = cls._GetVideoFileName(url)
    if GSPathExists(video_url):
      with GSFile(video_url, download=True, upload=False) as video_file:
        self.video = FileVideoReader(video_file, self.framerate)
    return self

  def _GetSubject(self, benchmark_system):
    return benchmark_system.subjects[self.subject_name]

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
    subject_name = state.get("subject_name", state.get("_subject_name"))
    benchmark_type = state.get("benchmark_type", state.get("_benchmark_type"))
    metadata = state["metadata"]
    screen_calibration = state["screen_calibration"]
    _delegate = state["_delegate"]
    self.__init__(subject_name, benchmark_type, metadata, screen_calibration,
                  _delegate)
    self.__dict__.update(state)

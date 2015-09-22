# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contextlib import contextmanager
import logging
import time
import traceback

from safetynet import Any, Dict, InterfaceMeta, List, Optional

from optofidelity.detection import ScreenCalibration, VideoProcessor
from optofidelity.system import BenchmarkSubject, BenchmarkSystem
from optofidelity.util import GSFindUniqueFilename, LogCapture, ProgressPrinter

from ._keyboard_delegate import KeyboardDelegate
from ._line_delegates import LineDrawDelegate, LineDrawStartDelegate
from ._open_delegates import OpenStuffDelegate
from ._tap_delegate import TapDelegate
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

  BENCHMARK_TYPES = {
    "line_draw": LineDrawDelegate,
    "line_draw_start": LineDrawStartDelegate,
    "tap": TapDelegate,
    "open": OpenStuffDelegate,
    "keyboard": KeyboardDelegate
  }

  def __init__(self, benchmark_system, video_processor):
    """
    :type benchmark_system: BenchmarkSystem
    :type video_processor: VideoProcessor
    """
    self.benchmark_system = benchmark_system
    self.video_processor = video_processor
    self._progress = ProgressPrinter(_log)
    self._screen_calibration = None
    self._current_subject = None
    self.led_calib_delays = (0.0, 0.0)
    self._calib_video_path = None

  @classmethod
  def FromConfig(cls, parameters, children, benchmark_system, video_processor):
    self = cls(benchmark_system, video_processor)
    down = parameters.get("led-calibration-down")
    up = parameters.get("led-calibration-up")
    self.led_calib_delays = (float(down) if down else 0.0,
                             float(up) if up else 0.0)
    self._calib_video_path = parameters.get("calibration-video-path")
    return self

  @contextmanager
  def UseSubject(self, subject):
    """Context manager to allow running of benchmarks on a subject.

    The context manager will open and calibrate the subject on entering, and
    close the subject on exiting.
    :type subject: BenchmarkSubject
    """
    try:
      self.OpenAndCalibrateSubject(subject)
      yield
    finally:
      self.CloseSubject()

  def OpenAndCalibrateSubject(self, subject):
    self._screen_calibration = self._OpenAndCalibrateSubject(subject)
    self._current_subject = subject

  def CloseSubject(self):
    subject = self._current_subject
    self._screen_calibration = None
    self._current_subject = None
    if subject:
      subject.navigator.Cleanup()

  def CreateBenchmark(self, name, benchmark_type, activity, parameters,
                      metadata):
    delegate_type = self.BENCHMARK_TYPES[benchmark_type]
    delegate = delegate_type(activity, parameters)
    benchmark = Benchmark(name, delegate, metadata, self._screen_calibration)
    benchmark.led_calib_delays = self.led_calib_delays
    return benchmark

  def RunBenchmark(self, benchmark):
    """Run benchmark on subject picked with UseSubject.

    This method has to be called within the context of UseSubject.
    :type benchmark: Benchmark
    """
    if not self._current_subject:
      raise Exception("Must be executed within the context of UseSubject.")
    self._ExecuteBenchmark(benchmark)

  def _OpenAndCalibrateSubject(self, subject):
    """Open a subject and calibrate screen.

    :type subject: BenchmarkSubject
    :rtype: Optional[ScreenCalibration]
    """
    self._progress.Info(subject.name, "Opening and calibrating")
    subject.navigator.Open()
    try:
      return self._CalibrateScreen(subject)
    except:
      subject.navigator.Close()
      raise

  def _ExecuteBenchmark(self, benchmark):
    """Execute all steps of benchmark processing.

    All log output is captured, so are exceptions. They are available in
    benchmark.log and benchmark.error.

    :type benchmark: Benchmark
    """
    start_time = time.time()
    capture = LogCapture()
    with capture:
      try:
        benchmark.ExecuteOnSubject(self._current_subject)
        benchmark.ProcessVideo(self.video_processor, [])
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
    :rtype Optional[ScreenCalibration]
    """
    try:
      self._progress.Info(subject.name, "Calibrating screen")
      if subject.camera.is_relative:
        return None
      video_reader = subject.RecordCalibrationVideo()
      screen_calibration = self.video_processor.CreateScreenCalibration(
          video_reader)
      return screen_calibration
    except KeyboardInterrupt:
      raise
    except:
      if self._calib_video_path:
        unique_file, _ = GSFindUniqueFilename(self._calib_video_path,
                                              "calibration_", ".avi")
        self._progress.Exception(subject.name, "Failed calibration video at: %s" %
                                           (unique_file,))
        video_reader.Save(unique_file)

      raise

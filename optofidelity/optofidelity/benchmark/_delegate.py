# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of the BenchmarkDelegate interface."""

from abc import abstractmethod

from safetynet import InterfaceMeta

from optofidelity.detection import Trace, VideoProcessor
from optofidelity.system import BenchmarkSubject
from optofidelity.videoproc import VideoReader

from .results import BenchmarkMeasurements


class BenchmarkDelegate(object):
  """Interface for benchmark logic.

  A delegate has to perform two tasks:
  1. It has to execute the benchmark on the robot, instructing camera and robot
     to perform and record the test.
  2. It has to process the resulting trace, returning the measurements.
  """
  __metaclass__ = InterfaceMeta

  def __init__(self, activity, parameters):
    self.activity = activity

  @abstractmethod
  def InitializeProcessor(self, processor, video_reader, screen_calibration):
    """Configure video processor processor.

    Most specifically enable the required detectors.
    :param VideoProcessor processor: a
    """

  @abstractmethod
  def ExecuteOnSubject(self, subject):
    """Execute benchmark on the subject

    This method has to instruct the camera and robot to perform and record the
    test, then return the recorded video as a VideoReader.
    :param BenchmarkSubject subject: a
    :returns VideoReader
    """

  @abstractmethod
  def ProcessTrace(self, trace, measurements):
    """Process the trace and put measurements into the results object

    The trace is generated from the video returned by ExecuteTest. This
    method calculates the measurements from the trace.
    :param Trace trace
    :param BenchmarkMeasurements measurements
    """
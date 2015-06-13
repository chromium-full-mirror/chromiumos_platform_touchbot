# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Module to execute a latency benchmark and store it to disk.

The Benchmark class is responsible for executing a single benchmark on a
subject. The actual benchmark logic is implemented in delegates defined
in benchmark._line_delegates and benchmark._tap_delegate.

A benchmark can be saved to and loaded from disk, optionally including
debugging information and the benchmark video.

The results of a benchmark are defined in benchmark.results, and include a
list of measurements, which are defined by an input and output event.
"""
from .benchmark import Benchmark
from .led_calibrator import LEDCalibrator
from .results import (AggregateResults, BenchmarkMeasurements,
                      BenchmarkResults, DrawEventLatencySeries,
                      DroppedFramesSeries, MeasurementSeries)
from .runner import BenchmarkRunner

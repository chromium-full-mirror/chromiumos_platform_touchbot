# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

import numpy as np
import skimage.color as color
import skimage.feature as feature
import skimage.io

from optofidelity.benchmark.results import (AggregateMeasurements,
                                            BenchmarkMeasurements,
                                            DrawEventLatencySeries)
from optofidelity.detection.events import Event
from optofidelity.reporting._figures import (PrimarySecondaryAxesFigure,
                                             SingleAxesFigure)
from optofidelity.reporting._hist_figure import LatencyHistogramFigure
from optofidelity.reporting._trace_figures import (EventsMeasurementsFigure,
                                                   LocationMeasurementsFigure,
                                                   TraceOverviewFigure)
from optofidelity.videoproc import DebugView

from . import test_data


class FigureVerificationTests(unittest.TestCase):
  FORCE_UPDATE_ALL = False
  WIDTH = 1024
  LOCATION_HEIGHT = 512
  EVENTS_HEIGHT = 256
  LATENCIES_HEIGHT = 256
  MS_PER_FRAME = 3.33

  def addSimplePlots(self, figure):
    location_timeseries = np.asarray(range(0, 1000, 10))
    event_timeseries = np.zeros(location_timeseries.shape)
    event_timeseries[25:75] = 1

    figure.PlotLocation(location_timeseries, {})
    figure.PlotEvents(event_timeseries, 0.0, {})
    figure.UpdateAxes()

  def assertImageMatches(self, image, expected_file_name, force_update=False):
    expected_image_path = test_data.Path(expected_file_name)
    if (self.FORCE_UPDATE_ALL or force_update or
        not os.path.exists(expected_image_path)):
      skimage.io.imsave(expected_image_path, image)
      DebugView(title=expected_file_name, created_image=image)
      self.skipTest("Created expected image %s" % expected_file_name)

    expected_image = color.rgb2gray(test_data.LoadImage(expected_file_name))
    actual_image = color.rgb2gray(image)
    cross_corr_image = feature.match_template(actual_image, expected_image)

    if np.max(cross_corr_image) < 0.99:
      message = "Image not matching expected image: %s" % expected_file_name
      print message
      DebugView(actual_image=actual_image, expected_image=expected_image)
      self.fail(message)


class FigureTests(FigureVerificationTests):
  def testSingleLayoutScalability(self):
    height = 256
    for width in (256, 512, 1024):
      figure = SingleAxesFigure(width, height, "X Label", "Y Label")
      figure.axes.plot(np.linspace(0, 100))
      image = figure.AsImage(False)
      self.assertEqual(image.shape[0], height)
      self.assertEqual(image.shape[1], width)

  def testSecondaryAxesLayoutScalability(self):
    prim_height = 192
    second_height = 54
    overall_height = prim_height + second_height
    for width in (256, 512, 1024):
      figure = PrimarySecondaryAxesFigure(width, prim_height, second_height,
                                          "X Label", "Primary Label",
                                          "Secondary Label")
      figure.prim_axes.plot(np.linspace(0, 100))
      figure.second_axes.plot(np.linspace(0, 100))
      image = figure.AsImage(False)
      self.assertEqual(image.shape[0], overall_height)
      self.assertEqual(image.shape[1], width)

  def testSingleLayoutRendering(self):
    figure = SingleAxesFigure(256, 256, "X Label", "Y Label")
    figure.axes.plot(np.linspace(100, 0))
    self.assertImageMatches(figure.AsImage(False),
                             "single_layout_rendering.png")

  def testLegendGeneration(self):
    figure = SingleAxesFigure(256, 256, "X Label", "Y Label")
    figure.axes.plot(np.linspace(100, 0), label="Test")
    self.assertImageMatches(figure.AsImage(True), "legend_rendering.png")

  def testSecondaryLayoutRendering(self):
    figure = PrimarySecondaryAxesFigure(512, 192, 64, "X Label",
                                        "Primary Label", "Secondary Label")
    figure.prim_axes.plot(np.linspace(0, 100))
    figure.second_axes.plot(np.linspace(0, 100))
    self.assertImageMatches(figure.AsImage(False),
                             "secondary_layout_rendering.png")


class TraceOverviewFigureTests(FigureVerificationTests):
  def createSimplePlot(self):
    figure = TraceOverviewFigure(self.WIDTH, self.LOCATION_HEIGHT,
                                 self.EVENTS_HEIGHT, self.MS_PER_FRAME)
    self.addSimplePlots(figure)
    return figure

  def createTracePlot(self, filename):
    figure = TraceOverviewFigure(self.WIDTH, self.LOCATION_HEIGHT,
                                 self.EVENTS_HEIGHT, self.MS_PER_FRAME)
    trace = test_data.LoadTrace(filename)
    trace.ApplyFingerLocationCalib(10)
    trace.ApplyLEDCalib(-10, 10)
    figure.PlotTrace(trace)
    return figure

  def testLineDrawTraceOverviewFigure(self):
    figure = self.createTracePlot("line_draw_basic.trace")
    self.assertImageMatches(figure.AsImage(False), "line_draw_basic.png")

  def testTapTraceOverviewFigure(self):
    figure = self.createTracePlot("tap_basic.trace")
    self.assertImageMatches(figure.AsImage(False), "tap_basic.png")

  def testSimpleFigure(self):
    figure = self.createSimplePlot()
    self.assertImageMatches(figure.AsImage(False), "simple_trace_figure.png")

  def testLimits(self):
    figure = self.createSimplePlot()
    figure.SetLimits(20, 80)
    self.assertImageMatches(figure.AsImage(False), "simple_limits.png")


  def testPassMarker(self):
    figure = self.createSimplePlot()
    figure.AddRangeMarker("Pass 1", 5, 45)
    figure.AddRangeMarker("Pass 2", 55, 95)
    self.assertImageMatches(figure.AsImage(False), "pass_marker.png")


class MeasurementsFigureTests(FigureVerificationTests):
  def createSimpleResults(self):
    measurements = BenchmarkMeasurements()
    measurements.AddSeriesInfo("Location", DrawEventLatencySeries)
    measurements.AddSeriesInfo("Events", DrawEventLatencySeries)

    location_series = measurements.AddSeries("Location")
    for i in range(0, 100, 10):
      location_series.AddMeasurement(Event(time=i, location=float(i * 10)),
                                     Event(time=i + 5,
                                           location=float((i * 10) + 50)))
    event_series = measurements.AddSeries("Events")
    event_series.AddMeasurement(Event(time=15, state=False),
                                Event(time=25, state=True))
    event_series.AddMeasurement(Event(time=75, state=True),
                                Event(time=85, state=False))
    return measurements

  def testLatencyPlot(self):
    figure = EventsMeasurementsFigure(self.WIDTH, self.EVENTS_HEIGHT,
                                      self.LATENCIES_HEIGHT,
                                      self.MS_PER_FRAME)
    latencies = np.asarray([(i, i + 50) for i in np.linspace(0, 100, num=10)])
    figure.PlotLatencies(latencies, "Test", "r")
    self.assertImageMatches(figure.AsImage(False), "latencies.png")

  def testMasurementsPlot(self):
    figure = EventsMeasurementsFigure(self.WIDTH, self.EVENTS_HEIGHT,
                                      self.LATENCIES_HEIGHT,
                                      self.MS_PER_FRAME)
    measurements = [((0, 0), (20, 1)), ((40, 1), (50, 0))]
    figure.PlotEventsMeasurements(measurements, "Test", "r")
    figure.UpdateAxes()
    self.assertImageMatches(figure.AsImage(False), "measurements.png")

  def testEventsMeasurementsPlot(self):
    figure = EventsMeasurementsFigure(self.WIDTH, self.EVENTS_HEIGHT,
                                      self.LATENCIES_HEIGHT,
                                      self.MS_PER_FRAME)
    self.addSimplePlots(figure)
    measurements = self.createSimpleResults()
    figure.PlotMeasurements(measurements[0].values())
    self.assertImageMatches(figure.AsImage(True), "event_measurements.png")

  def testLocationMeasurementsPlot(self):
    figure = LocationMeasurementsFigure(self.WIDTH, self.LOCATION_HEIGHT,
                                        self.LATENCIES_HEIGHT,
                                        self.MS_PER_FRAME)
    self.addSimplePlots(figure)
    measurements = self.createSimpleResults()
    figure.PlotMeasurements(measurements[0].values())
    self.assertImageMatches(figure.AsImage(True), "location_measurements.png")


class HistogramFigureTests(FigureVerificationTests):
  LATENCIES = np.asarray([
      104.80590931,  101.39959026,   96.18115035,   86.89391975,
      103.12146378,   86.08486046,   96.05411581,  100.33152484,
       97.48061073,  114.82677329,   97.51435366,  112.37953043,
       89.52607202,  101.50421159,   83.53152664,  110.11220344,
       98.69820428,  101.37292205,  111.51249425,   98.52950697 ])

  def createMultiPassResults(self, offset):
    measurements = BenchmarkMeasurements()
    measurements.AddSeriesInfo("TestMeasurement", DrawEventLatencySeries)
    series = [measurements.AddSeries("TestMeasurement", 0),
              measurements.AddSeries("TestMeasurement", 1)]
    for i, latency in enumerate(self.LATENCIES):
      pass_num = i % 2
      late_time = int(i + latency / 3.33 + offset)
      series[pass_num].AddMeasurement(Event(i, start_time=i - 20),
                                      Event(late_time,
                                            start_time=int(i + latency) - 20))
    return measurements

  def testPrimaryHistogram(self):
    figure = LatencyHistogramFigure(512, 512)
    figure.PlotPrimary(self.LATENCIES, "Test", "r")
    self.assertImageMatches(figure.AsImage(False), "histogram_main.png")

  def testSecondaryHistogram(self):
    figure = LatencyHistogramFigure(512, 512)
    figure.PlotSecondary(self.LATENCIES, "Test", "r")
    self.assertImageMatches(figure.AsImage(False), "histogram_secondary.png")

  def testOverviewHistogram(self):
    msrmnts = self.createMultiPassResults(0.0)
    pass_values = dict((pass_num, pass_msrmnts["TestMeasurement"].values)
                       for pass_num, pass_msrmnts in msrmnts.iteritems())
    figure = LatencyHistogramFigure(512, 512)
    figure.PlotOverviewHistogram(pass_values, "Pass")
    self.assertImageMatches(figure.AsImage(False), "histogram_overview.png")

  def testAggregateHistogram(self):
    msrmnts = AggregateMeasurements()
    msrmnts[0] = self.createMultiPassResults(-5)
    msrmnts[1] = self.createMultiPassResults(0)
    msrmnts[2] = self.createMultiPassResults(+5)

    rep_values = dict((rep_num, rep_msrmnts.SummarizeValues("TestMeasurement"))
                      for rep_num, rep_msrmnts in msrmnts.iteritems())

    figure = LatencyHistogramFigure(512, 512)
    figure.PlotOverviewHistogram(rep_values, "Repetition")
    self.assertImageMatches(figure.AsImage(False), "histogram_aggregate.png")

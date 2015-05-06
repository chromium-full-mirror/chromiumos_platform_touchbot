# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from safetynet import Any, Dict, Optional
import numpy as np

from optofidelity.benchmark import MeasurementList, AggregateResults
import matplotlib.mlab as mlab

from . import _styles
from ._figures import SingleAxesFigure


class HistogramFigure(SingleAxesFigure):
  """Figure showing multiple latency histograms."""

  def __init__(self, width, height, ms_per_frame):
    """Create empty histogram figure.

    :param int width: Width of image in pixels.
    :param int height: Height of image in pixels.
    :param float ms_per_frame: Milliseconds per camera frame ratio
    """
    super(HistogramFigure, self).__init__(width, height, "Latency [ms]",
        "Relative Frequency")
    self.ms_per_frame = ms_per_frame
    self.axes.set_xlim(_styles.MIN_LATENCY, _styles.MAX_LATENCY)
    self.axes.set_ylim(0, _styles.MAX_REL_FREQ)

  def PlotPassHistogram(self, pass_num, measurement_list):
    """Plot histogram of latencies in a single pass.

    Plots all latencies in measurement_list. The color of the plot
    is selected based on pass_num and identical to the one used in the
    overview histogram.

    :param int pass_num: pass number of measurements in measurement_list.
    :param MeasurementList measurement_list: measurements made during that pass.
    """
    label = "Pass %d" % pass_num
    color = self.GetRotationColor(pass_num)
    self.PlotPrimary(measurement_list.latencies,
                     measurement_list.draw_start_latencies, label, color)

  def PlotOverviewHistogram(self, measurement_list):
    """Plot overview histogram of multiple passes.

    Each pass will have a sepearate PDF of an automatically assigned color,
    additionally we will plot a full histogram and PDF of all measurements
    combined.

    :param MeasurementList measurement_list: measurements to plot
    """
    color = _styles.SUMMARY_PDF_COLOR
    self.PlotPrimary(measurement_list.latencies,
                     measurement_list.draw_start_latencies, "Overall", color)

    if len(list(measurement_list.IterByPass())) == 1:
      return
    for pass_num, pass_measurements in measurement_list.IterByPass():
      label = "Pass %d" % pass_num
      color = self.GetRotationColor(pass_num)
      self.PlotSecondary(pass_measurements.latencies, label, color)

  def PlotAggregateHistogram(self, measurement_list, rep_measurement_lists):
    """
    """
    color = _styles.SUMMARY_PDF_COLOR
    msrmnt_list = measurement_list
    self.PlotPrimary(msrmnt_list.latencies,
                     msrmnt_list.draw_start_latencies, "Aggregate", color)

    for i, rep_msrmnt in enumerate(rep_measurement_lists):
      label = "Repetition #%02d" % i
      color = self.GetRotationColor(i)
      self.PlotSecondary(rep_msrmnt.latencies, label, color)

  def PlotPrimary(self, latencies, draw_start_latencies, label, color):
    """Plot latency numbers with histogram and PDF.

    Draws a full histogram as well as PDF with the provided latencies.
    Optionally includes draw start latencies as a dashed plot next to it.
    :type latencies: np.ndarray
    :type draw_start_latencies: Optional[np.ndarray]
    :param str label: Label of this plot for the legend.
    :param str color: Color of plot.
    """
    values = self._InMS(latencies)
    self._PlotHistogram(values, _styles.HISTOGRAM_STYLE)
    self._PlotPDF(values, label + " PDF", color, _styles.MAIN_PDF_STYLE)

    if draw_start_latencies is not None:
      draw_start_values = self._InMS(draw_start_latencies)
      self._PlotPDF(draw_start_values, label + " PDF (start)", color,
                    _styles.DRAW_START_PDF_STYLE)

  def PlotSecondary(self, latencies, label, color):
    """Plot latency numbers with histogram only

    :type latencies: np.ndarray
    :param str label: Label of this plot for the legend.
    :param str color: Color of plot.
    """
    values = self._InMS(latencies)
    self._PlotPDF(values, label, color, _styles.SECONDARY_PDF_STYLE)

  def _PlotHistogram(self, values, style):
    """Plot histogram bars.

    :type values: np.ndarray
    :type style: Dict[str, Any]
    """
    bins = range(_styles.MIN_LATENCY, _styles.MAX_LATENCY, 10)
    self.axes.hist(values, normed=1, bins=bins, **style)

  def _PlotPDF(self, values, label, color, style):
    """Plot probability density function.

    :type values: np.ndarray
    :type label: str
    :type color: str
    :type style: Dict[str, Any]
    """
    xs = np.linspace(_styles.MIN_LATENCY, _styles.MAX_LATENCY, 240)
    mu = np.mean(values)
    sigma = np.std(values)
    ys = mlab.normpdf(xs, mu, sigma)
    self.axes.plot(xs, ys, label=label, color=color, **style)

  def GetRotationColor(self, i):
    """Map integer to color.

    :type i: int
    :rtype str
    """
    return _styles.COLOR_ROTATION[i % len(_styles.COLOR_ROTATION)]

  def _InMS(self, frame_index):
    """Convert high speed camera frame index into milliseconds."""
    return frame_index * self.ms_per_frame

# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import itertools

from safetynet import Any, Dict, List, Optional
import numpy as np

import matplotlib.mlab as mlab

from . import _styles
from ._figures import SingleAxesFigure

def MergeLists(list_of_lists):
  return np.fromiter(itertools.chain(*list_of_lists), np.float)

class HistogramFigure(SingleAxesFigure):
  def __init__(self, width, height, unit_label, x_min, x_max):
    """Create empty histogram figure.

    :param int width: Width of image in pixels.
    :param int height: Height of image in pixels.
    :param float ms_per_frame: Milliseconds per camera frame ratio
    """
    super(HistogramFigure, self).__init__(width, height, unit_label,
        "Relative Frequency")
    self.axes.set_xlim(x_min, x_max)
    self.axes.set_ylim(0, _styles.MAX_REL_FREQ)
    self.x_min = x_min
    self.x_max = x_max

  def PlotPassHistogram(self, pass_num, value_list):
    """Plot histogram of values in a single pass.

    :param int pass_num: Pass number of measurement
    :param List[float] value_list: List of measurement values
    """
    if not len(value_list):
        return
    label = "Pass %d" % pass_num
    color = self.GetRotationColor(pass_num)
    self.PlotPrimary(np.asarray(value_list), label, color)

  def PlotOverviewHistogram(self, values_map, subplot_title):
    """Plot overview histogram with multiple sub histograms.

    Each pass will have a sepearate PDF of an automatically assigned color,
    additionally we will plot a full histogram and PDF of all measurements
    combined.

    :param Dict[int, List[float]] values_map: Dictionary mapping key number to
           values for that histogram.
    :param str subplot_title: Title for each sub histogram.

    """
    color = _styles.SUMMARY_PDF_COLOR

    all_values = MergeLists(values_map.values())
    self.PlotPrimary(all_values, "Overall", color)

    if len(values_map) == 1:
      return
    for pass_num, values in values_map.iteritems():
      label = "%s %d" % (subplot_title, pass_num)
      color = self.GetRotationColor(pass_num)
      self.PlotSecondary(np.asarray(values), label, color)

  def PlotPrimary(self, values, label, color):
    """Plot latency numbers with histogram and PDF.

    Draws a full histogram as well as PDF with the provided values.
    :type values: np.ndarray
    :param str label: Label of this plot for the legend.
    :param str color: Color of plot.
    """
    if not len(values):
      return
    self._PlotHistogram(values, _styles.HISTOGRAM_STYLE)
    self._PlotPDF(values, label + " PDF", color, _styles.MAIN_PDF_STYLE)

  def PlotSecondary(self, values, label, color):
    """Plot latency numbers with histogram only

    :type values: np.ndarray
    :param str label: Label of this plot for the legend.
    :param str color: Color of plot.
    """
    if not len(values):
      return
    self._PlotPDF(values, label, color, _styles.SECONDARY_PDF_STYLE)

  def _PlotHistogram(self, values, style):
    """Plot histogram bars.

    :type values: np.ndarray
    :type style: Dict[str, Any]
    """
    bins = np.linspace(self.x_min, self.x_max, 25)
    self.axes.hist(values, normed=1, bins=bins, **style)

  def _PlotPDF(self, values, label, color, style):
    """Plot probability density function.

    :type values: np.ndarray
    :type label: str
    :type color: str
    :type style: Dict[str, Any]
    """
    xs = np.linspace(self.x_min, self.x_max, 240)
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

class LatencyHistogramFigure(HistogramFigure):
  """Figure showing multiple latency histograms."""

  def __init__(self, width, height):
    """Create empty histogram figure.

    :param int width: Width of image in pixels.
    :param int height: Height of image in pixels.
    """
    super(LatencyHistogramFigure, self).__init__(width, height, "Latency [ms]",
        _styles.MIN_LATENCY, _styles.MAX_LATENCY)

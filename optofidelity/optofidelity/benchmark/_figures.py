# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Base classes for rendering figures based on matplotlib."""
from safetynet import Any, Dict, List, Optional, Tuple, TypecheckMeta
import numpy as np

from matplotlib.backends.backend_agg import FigureCanvasAgg
import matplotlib.figure

from . import _styles


class Figure(object):
  """Base class for a figure that can be rendered into an image."""
  __metaclass__ = TypecheckMeta

  DPI = 64.0
  """Dots per inches used for font-rendering."""

  LEFT_PADDING = 48.0
  """Left padding in pixels."""

  RIGHT_PADDING = 16.0
  """Right padding in pixels."""

  TOP_PADDING = 12.0
  """Top padding in pixels."""

  BOTTOM_PADDING = 32.0
  """Bottom padding in pixels."""

  AXIS_COLOR = "#444444"
  """Color of all axes and labels."""

  def __init__(self, width, height):
    """Create new figure image of specified size.

    :param int width: Width of image in pixels.
    :param int height: Height of image in pixels.
    """
    self.figure = matplotlib.figure.Figure(facecolor=[1, 1, 1], dpi=self.DPI)
    self.axes_list = []
    self.width = float(width)
    self.height = float(height)
    if self.width and self.height:
      self.figure.set_size_inches(self.width / self.DPI, self.height / self.DPI)

    self.left = self.LEFT_PADDING / self.width
    self.right = 1.0 - (self.RIGHT_PADDING / self.width)
    self.bottom = self.BOTTOM_PADDING / self.height
    self.top = 1.0 - (self.TOP_PADDING / self.height)

  def Save(self, filename, show_legend):
    """Save figure to image.

    :param str filename: Path to file to store image to.
    :param bool show_legend: True if the image should contain a legend.
    """
    canvas = self._CreateCanvas(show_legend)
    canvas.print_figure(filename, dpi=self.DPI)

  def AsImage(self, show_legend):
    """Same as Save, but return image as a numpy array instead.

    :param bool show_legend: True if the image should contain a legend.
    :rtype np.ndarray
    """
    canvas = self._CreateCanvas(show_legend)
    (buffer, (width, height)) = canvas.print_to_buffer()
    return np.reshape(buffer, (height, width, 4))

  def _CreateAxes(self, left, bottom, width, height):
    """Create new axes instance with specified border.

    left, bottom, width and height are specified in the matplotlib 0..1 relative
    coordinate system.

    :type left: float
    :type bottom: float
    :type width: float
    :type height: float
    :rtype matplotlib.axes.Axes
    """
    axes = self.figure.add_axes([left, bottom, width, height])

    for axis in ['top', 'bottom', 'left', 'right']:
      axes.spines[axis].set_color(self.AXIS_COLOR)
    axes.tick_params(colors=self.AXIS_COLOR)
    axes.xaxis.label.set_color(self.AXIS_COLOR)
    axes.yaxis.label.set_color(self.AXIS_COLOR)

    self.axes_list.append(axes)
    return axes

  def _CreateCanvas(self, show_legend):
    """Create matplotlib canvas, optionally including legend.

    :param bool show_legend: True if the canvas should show a legend.
    :rtype FigureCanvasAgg
    """
    for axes in self.axes_list:
      legend = axes.legend()
      if legend:
        legend.set_visible(show_legend)
    return FigureCanvasAgg(self.figure)


class SingleAxesFigure(Figure):
  """A figure that contains only one pair of Axes."""

  def __init__(self, width, height, x_label, y_label):
    """
    :param int width: Width of image in pixels.
    :param int height: Height of image in pixels.
    :param Optional[str] x_label: Label of x-axis
    :param Optional[str] y_label: Label of y-axis
    """
    super(SingleAxesFigure, self).__init__(width, height)
    self.axes = self._CreateAxes(self.left, self.bottom, self.right - self.left,
                              self.top - self.bottom)
    if x_label:
      self.axes.set_xlabel(x_label, labelpad=1)
    if y_label:
      self.axes.set_ylabel(y_label, labelpad=1)


class PrimarySecondaryAxesFigure(Figure):
  """Figure that is split horizontally.

  The figure shows a primary pair of Axes above a secondary pair. Both share
  the same x-axis, but have separate y-axis labels.
  """
  def __init__(self, width, prim_height, second_height, x_label, prim_label,
               second_label):
    """
    :param int width: Width of image in pixels.
    :param int prim_height: Height of primary axes in pixels.
    :param int second_height: Height of secondary axes in pixels.
    :param Optional[str] x_label: Label of shared x-axis
    :param Optional[str] prim_label: Label of primary y-axis
    :param Optional[str] second_label: Label of secondary y-axis
    """
    overall_height = prim_height + second_height
    super(PrimarySecondaryAxesFigure, self).__init__(width, overall_height)

    axes_width = self.right - self.left
    axes_height = self.top - self.bottom

    # Add secondary axes at the bottom
    second_height_ratio = float(second_height) / float(overall_height)
    second_height = second_height_ratio * axes_height
    self.second_axes = self._CreateAxes(self.left, self.bottom, axes_width,
                                     second_height)
    if x_label:
      self.second_axes.set_xlabel(x_label, labelpad=4)
    if second_label:
      self.second_axes.set_ylabel(second_label, labelpad=8)

    # Add primary axes above
    prim_bottom = self.bottom + second_height
    prim_height = axes_height * (1 - second_height_ratio)
    self.prim_axes = self._CreateAxes(self.left, prim_bottom, axes_width,
                                   prim_height)
    if prim_label:
      self.prim_axes.set_ylabel(prim_label, labelpad=8)
    self.prim_axes.tick_params(axis="x", labelbottom="off")


class TimeSeriesAxes(object):
  """Wrapper around matplotlib.axes.Axes for visualizing time-series data.

  Provides methods to plot time-series data and limit the view of data to a
  certain time range. It also takes care of converting time values from high
  speed camera frames into milliseconds.

  All style parameters are a dictionary of strings mapping to strings that
  are passed directly as keyword parameters to the matplotlib plotting
  functions.
  """
  __metaclass__ = TypecheckMeta

  X_AXIS_PADDING = 0.01
  """X axis padding as a factor of the full x axis range."""

  Y_AXIS_PADDING = 0.05
  """Y axis padding as a factor of the full y axis range."""

  def __init__(self, mpl_axes, ms_per_frame):
    """
    :param matplotlib.axes.Axes mpl_axes: matplotlib axes to wrap.
    :param float ms_per_frame: milliseconds per high speed camera frame.
    """
    self.mpl_axes = mpl_axes
    self.ms_per_frame = ms_per_frame
    self.begin_frame = None
    self.end_frame = None
    self.no_data_label = None

  def AddVerticalLine(self, frame_index, style):
    """Draw vertical line at specified time.

    :param int frame_index: time in camera frames.
    :param Dict[str, Any] style: Dictionary of style parameters.
    """
    time = self._InMS(frame_index)
    self.mpl_axes.axvline(time, **style)

  def AddCenteredText(self, text, style):
    """Draw text in the center of the axes.

    :param str text: text to draw
    :param Dict[str, Any] style: Dictionary of style parameters.
    """
    self.mpl_axes.text(0.5, 0.5, text, ha="center", va="center",
                   transform=self.mpl_axes.transAxes, **style)

  def AddText(self, frame_index, y, text, style):
    """Draw text at specified location

    :param int frame_index: time in camera frames.
    :param float y: y-location of text.
    :param str text: text to draw.
    :param Dict[str, Any] style: Dictionary of style parameters.
    """
    time = self._InMS(frame_index)
    self.mpl_axes.text(time, y, text, ha="center", va="center", **style)

  def SetLimits(self, begin_frame, end_frame):
    """Specify start and end time of axes.

    :param int begin_frame: begin time in camera frames.
    :param int end_frame: end time in camera frames.
    """
    self.begin_frame = begin_frame
    self.end_frame = end_frame

  def UpdateAxes(self):
    """Update axes format.

    This method is to be called after all plotting and setting of limits is
    done.
    """
    self._UpdateLimits()
    if self.no_data_label:
      self.no_data_label.remove()
      self.no_data_label = None
    if not self.mpl_axes.get_lines():
      self.no_data_label = self.mpl_axes.text(0.5, 0.5, "no data",
                                          ha="center", va="center",
                                          transform=self.mpl_axes.transAxes,
                                          **_styles.MESSAGE_STYLE)

  def _UpdateLimits(self):
    """Update limits of axes to show requested timeframe.

    The y-axis is automatically scaled to show all plot points.
    """
    if self.begin_frame and self.end_frame:
      begin_time = self._InMS(self.begin_frame)
      end_time = self._InMS(self.end_frame)
      padding = (end_time - begin_time) * self.X_AXIS_PADDING
      self.mpl_axes.set_xlim(begin_time - padding, end_time + padding)

    (min_value, max_value) = self._GetMinMaxValue()
    padding = (max_value - min_value) * self.Y_AXIS_PADDING
    self.mpl_axes.set_ylim(min_value - padding, max_value + padding)

  def _GetMinMaxValue(self):
    """Returns min and max value of all plots of this axes.

    :rtype Tuple[float, float]
    """
    def _NonNaN(array):
      return array[~np.isnan(array)]
    values = []
    for lines in self.mpl_axes.get_lines():
      ydata = lines.get_ydata()
      begin = self.begin_frame or 0
      end = self.end_frame or len(ydata)
      values.extend(_NonNaN(ydata[begin:end]))

    (min_value, max_value) = (0, 1)
    if len(values) > 0:
      min_value = np.min(values)
      max_value = np.max(values)
      max_value = max([max_value, 1])
    return (min_value, max_value)

  def _InMS(self, frame_index):
    """Convert high speed camera frame index into milliseconds."""
    return np.asarray(frame_index) * self.ms_per_frame

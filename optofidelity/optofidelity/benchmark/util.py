# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from ._trace_figures import TraceOverviewFigure
from optofidelity.videoproc import DebugView

def DebugViewTrace(trace):
  figure = TraceOverviewFigure(1024, 512, 256, 1.0)
  figure.PlotTrace(trace, 0.0, 0.0)
  figure_img = figure.AsImage(False)
  DebugView(trace=figure_img)
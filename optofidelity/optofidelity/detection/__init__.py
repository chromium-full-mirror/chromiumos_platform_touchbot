# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Video processing module to detect events in video streams.

This package is responsible for doing multithreaded processing of videos
to detect events such as screen draws, flashing LEDs and robot finger movement
in the video stream.

The VideoProcessor class is responsible for the processing and a multithreaded
or singlethreaded variant is created using CreateVideoProcessor.

You will have to pass it a ScreenCalibration instance which describes the
location of the screen of the DUT.

The result of the video processing is a list of Event objects.
"""
from .events import (Event, FingerEvent, LEDEvent, LineDrawEvent,
                     ScreenDrawEvent)
from .mt_processor import MultithreadedVideoProcessor
from .processor import VideoProcessor
from .screen_calibration import ScreenCalibration
from .st_processor import SinglethreadedVideoProcessor
from .trace import Trace

# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of InteractiveVideoViewer."""
import cv2

from .io import VideoReader


class InteractiveVideoViewer(object):
  """Video Viewer with interactive mode for seeking through video.

    During playback the user can use the following two keys:
      - p to enter interactive mode.
      - q to quit viewer.
    When in interactive mode the following key commands become available:
      - j/k to move by 1 frame
      - h/l to move by 10 frames
      - g/; to move by 100 frames
      - c to continue playback
      - q to quit viewer

    Example usage:
      viewer = InteractiveVideoViewer()
      for i, frame in viewer.YieldFrames():
        processed = ProcessFrame(frame)
        viewer.DisplayFrame(processed)
  """
  def __init__(self):
    self._current_frame = None
    self._interactive = False

  def YieldFrames(self, video_reader):
    """Yields a tuples of (frame_index, frame_image).

    This method will yield frames until the end of the video is reached or
    the viewer is quit by the user.

    :type video_reader: VideoReader
    """
    print "Press p to enter interactive mode."
    print "Press q to quit viewer."

    frame_index = 0
    while True:
      if frame_index < 0 or frame_index >= video_reader.num_frames:
        break

      if not self._interactive and frame_index + 1 < video_reader.num_frames:
        video_reader.Prefetch(frame_index + 1)

      self._current_frame = video_reader.FrameAt(frame_index)
      yield frame_index, self._current_frame

      cv2.imshow("Interactive View Viewer", self._current_frame)
      frame_index = self._HandleUserInput(frame_index)

  def _HandleUserInput(self, frame_index):
    if self._interactive:
      # Pause and wait for user input
      key = chr(cv2.waitKey() & 0xFF)
      print repr(key)
      keymap = {
        "j":  1, "h":  10, "g":  100,
        "k": -1, "l": -10, ";": -100
      }
      if key in keymap:
        return frame_index + keymap[key]
      elif key == "c":
        self._interactive = False
        return frame_index + 1
      elif key == "q":
        return -1
      return frame_index
    else:
      # Get user input without pausing
      key = chr(cv2.waitKey(1) & 0xFF)
      if key == "p":
        self._interactive = True
        print "Entering Interactive Mode"
        print "  Press j/k to move by 1 frame"
        print "  Press h/l to move by 10 frames"
        print "  Press g/; to move by 100 frames"
        print "  Press c to continue playback"
        print "  Press q to quit viewer"
        return frame_index
      elif key == "q":
        return -1
      return frame_index + 1

  def DisplayFrame(self, frame):
    """Select frame to display during YieldFrames.

    Only to be called during YieldFrames. If it is not called, YieldFrames will
    display the raw frame as read from the VideoReader.

    :param np.ndarray frame: An RGB frame to display
    """
    self._current_frame = frame

  def EnableInteractive(self):
    """Programmatically enter interactive mode."""
    self._interactive = True

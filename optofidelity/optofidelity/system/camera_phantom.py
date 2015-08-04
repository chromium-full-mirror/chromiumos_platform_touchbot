# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of the HighSpeedCamera class for the Phantom camera."""

import logging
import re
import select
import socket
import time

import numpy as np
import skimage

from optofidelity.videoproc import VideoReader

from .camera import HighSpeedCamera

_log = logging.getLogger(__name__)


class _ImageRequest(object):
  """Class storing information about a requested chunk of images."""

  def __init__(self, phantom, start, num_frames):
    self.phantom = phantom
    self.num_frames = num_frames
    self.start = start
    self.shape = None

  def ReceiveAck(self):
    """Receive acknowledgement from camera on command channel.

    This has to be called before another image can be requested. Otherwise we
    might run into race conditions where the camera mixes up requests.
    """
    response = self.phantom._ReceiveCommandResponse()

    # Determine the resolution of the image and how many bytes to wait for
    RESOLUTION_REGEX = (".*Ok!\s*{\s*cine\s*:\s*\d+,\s*res\s*:\s*" +
                        "(?P<width>\d+)\s+x\s+(?P<height>\d+)\s*}")
    matches = re.match(RESOLUTION_REGEX, response)
    width = int(matches.group("width"))
    height = int(matches.group("height"))
    self.shape = (height, width)

  def Receive(self):
    """Receive image data."""
    if self.shape is None:
      self.ReceiveAck()
    return self.phantom._ReceiveImages(self.shape, self.num_frames)


class PhantomCamera(HighSpeedCamera):
  DATA_STREAM_PORT = 7116
  MAX_MESSAGE_SIZE = 65536
  MAX_PTFRAMES = 2245

  FLAGS = {
    "READY": "RDY", # A cine is ready to record into
    "COMPLETE": "STR", # A full cine is already recorded here
    "INVALID": "INV", # Invalid cine, can't be used for anything
    "WAITING": "WTR", # Waiting for a trigger to start recording
  }

  def __init__(self, ip, port=None, default_fps=None):
    """Set up all communications with the camera.

    When a new Phantom object is made it will broadcast out over the
    network to find the camera and initialize command and data TCP
    connections with it so that future interactions with the camera
    work.
    You can specify the ip and port of a camera to skip the discovery
    protocol.
    The debug flag will enable debug printouts during the operation
    of this class.
    """
    super(PhantomCamera, self).__init__(is_relative=False)

    self.default_fps = default_fps or 300
    port = port or 7115

    self._command_sent = False
    self._fps = None
    self._num_frames = None

    self._triggered = False
    self._prepared = False

    # Set up the command connection
    self._cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self._cmd_sock.connect((ip, port))

    # Set up the data connection
    self._data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self._data_sock.connect((ip, self.DATA_STREAM_PORT))
    data_port = self._data_sock.getsockname()[1]
    self._SendCommand("attach {port: %d}" % data_port)

  @classmethod
  def FromConfig(cls, attrib, children):
    return cls(attrib["host"], attrib.get("port"))

  def Prepare(self, duration, fps=None, exposure=None):
    self._fps = fps or self.default_fps
    if exposure is None:
      exposure = (1.0 / float(self._fps)) * 1000.0
    exposure_ns = exposure * 1000.0 * 1000.0

    self._num_frames = duration * self._fps / 1000
    if self._num_frames > self.MAX_PTFRAMES:
      raise ValueError("Cannot record more than %d frames" % self.MAX_PTFRAMES)

    _log.info("Preparing recording: fps=%d, exp=%d, num_frames=%d", self._fps,
              exposure_ns, self._num_frames)
    self._SetProperty("defc.rate", self._fps)
    self._SetProperty("defc.exp", exposure_ns)
    self._SetProperty("defc.edrexp", 0)
    self._SetProperty("defc.ptframes", self._num_frames)
    self._SendCommand("rec 1")

    ready_flag = "WTR" # "Waiting for TRigger"
    while ready_flag not in self._SendCommand("get c1.state"):
      time.sleep(0.1)
    self._prepared = True
    self._triggered = False

  def Trigger(self):
    if not self._prepared:
      raise Exception("Can't trigger without camera being prepared.")

    self._SendCommand("trig 1")
    ready_flag = "TRG" # "TRiGgered"
    while ready_flag not in self._SendCommand("get c1.state"):
      time.sleep(0.1)
    self._triggered = True

  def ReceiveVideo(self):
    if not self._triggered:
      raise Exception("Camera needs to be triggered before receiving video.")
    ready_flag = "STR" # "Cine SToRed"
    while ready_flag not in self._SendCommand("get c1.state"):
      time.sleep(0.1)
    return PhantomVideoReader(self, self._num_frames, self._fps)

  def _SendCommandAsync(self, cmd):
    """Send command without waiting for the response.

    You mast call ReceiveCommandResponse before calling this method again.
    """
    cmd += "\r"

    if self._command_sent:
      msg = "Cannot send two commands without receiving resposne first."
      raise Exception(msg)

    if len(cmd) >= self.MAX_MESSAGE_SIZE:
      raise ValueError("Message too long!")

    _log.debug("SEND(%d): %s", len(cmd), cmd)
    total_sent = 0
    while total_sent < len(cmd):
      sent = self._cmd_sock.send(cmd[total_sent:])
      if sent == 0:
        raise Exception("Cannot send command")
      total_sent += sent
    self._command_sent = True

  def _ReceiveCommandResponse(self):
    """Reveice response from a command sent with SendCommandAsync."""
    if not self._command_sent:
      raise Exception("No command has been sent.")
    recv = ""
    while True:
      block = self._cmd_sock.recv(self.MAX_MESSAGE_SIZE)
      recv += block
      if len(block) == 0 or (len(block) > 2 and block[-1] == "\n"
                            and block[-2] != "\\"):
        break
    if "ERR" in recv:
      raise Exception("Received error code:" + recv)
    _log.debug("RECV(%d): %s", len(recv), recv.strip())
    self._command_sent = False
    return recv

  def _SendCommand(self, cmd):
    """Send a command to the camera, and return the response."""
    self._SendCommandAsync(cmd)
    return self._ReceiveCommandResponse()

  def _RequestImages(self, start_frame, num_frames):
    """Request images from camera.

    Returns an ImageRequest instance that can be used to receive the
    images of this request.
    """
    # Send the request to the camera for the frame in question
    cmd = "img {cine:1, start:%d, cnt:%d}" % (start_frame, num_frames)
    self._SendCommandAsync(cmd)
    return _ImageRequest(self, start_frame, num_frames)

  def _ReceiveImages(self, shape, num_frames):
    """Receive previously requested images."""
    frame_size = shape[0] * shape[1]
    total_size = frame_size * num_frames

    # Wait for image data to come in
    img_data = ""
    while (len(img_data) < total_size):
      remaining_data = total_size - len(img_data)
      ready = select.select([self._data_sock], [], [], 5)
      if ready[0]:
        request_size = min([remaining_data, self.MAX_MESSAGE_SIZE])
        img_data += self._data_sock.recv(request_size)
      else:
        raise Exception("No data received")
    _log.debug("RECV_IMG(%d)", len(img_data))
    images = []
    for i in range(num_frames):
      image = np.zeros(shape)
      img_start = i * frame_size
      img_end = (i + 1) * frame_size
      img_string = img_data[img_start:img_end]

      image = np.fromstring(img_string, dtype=np.uint8).reshape(shape)
      images.append(image)

    return images

  def _SetProperty(self, name, value):
    cmd = "set %s %s" % (name, str(value))
    res = self._SendCommand(cmd)
    if not "Ok" in res:
      raise Exception("Cannot set %s to %s: %s" % (name, value, res))

  def _GetProperty(self, name):
    cmd = "get %s" % name
    res = self._SendCommand(cmd)
    regex = re.compile("\S+ : (\S+)")
    match = regex.search(res)
    if not match:
      raise Exception("Invalid response: %s", res)
    return match.group(1)


class PhantomVideoReader(VideoReader):
  """Implementation of a VideoReader streaming from a Phantom camera.

  This class works as a fully functional VideoReader, streaming frames
  directly from the camera via ethernet.
  Set perf=True to enable collection of performance measuring transfer times.
  """
  def __init__(self, phantom, num_frames, fps, perf=False):
    self.phantom = phantom
    self.prefetch = None
    self.prefetch_frame = None
    VideoReader.__init__(self, num_frames, fps, perf)

  def Close(self, frame_index):
    pass

  def _SeekTo(self, frame_index):
    self.current_frame = frame_index
    return True

  def _Read(self):
    # Clear prefetch if we got the wrong frame.
    if self.prefetch and self.prefetch.start != self.current_frame:
      self.ClearPrefetch()

    # Request the current image if we don"t have a prefetch for it.
    request = self.prefetch
    if not request:
      request = self.phantom._RequestImages(self.current_frame , 1)

    # Receive ack before making any new requests.
    request.ReceiveAck()

    # Prefetch next frame.
    if self.prefetch_frame:
      self.prefetch = self.phantom._RequestImages(self.prefetch_frame , 1)
      self.prefetch_frame = None
    else:
      self.prefetch = None

    # Receive current frame.
    images = request.Receive()
    return skimage.img_as_float(images[0])

  def Prefetch(self, frame_index):
    """Select frame to prefetch with next Read command.

    Prefetching has to be explicitly enabled to ensure frames that are
    prefetched, but not read, will be cleaned up. Prefetching can be enabled
    like this:
    >>> with reader.PrefetchEnabled():
    >>>    reader.Frames()
    """
    self.prefetch_frame = frame_index

  def _ClearPrefetch(self):
    """Clear any outstanding requested frames.

    It is important that this method is called, since the camera is left in
    a broken state if a frame is requested, but not received.
    """
    if self.prefetch:
      self.prefetch.Receive()
      self.prefetch = None

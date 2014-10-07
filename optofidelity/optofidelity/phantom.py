# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Phantom high-speed camera communication.

This script contains the Phantom class for communicating with Phantom HS
cameras.  There are various functions availible as these cameras are somewhat
complex and have many features.  To use these features, one need only import
the Phantom class and instantiate it on a machine that is on a LAN with the
camera, whos IP address is 100.100.100.1, and the discovery protocol should do
the rest.  Then you can communicate freely with the device.

However, this script can be run as a stand-alone appliance to do common tasks
with the camera.

  Record, transfer, save avi to disk:
    python phantom.py record [filename.avi]

  View a live preview of what the camera sees (space = pause/play, q = quit):
    python phantom.py preview
"""

import re
import select
import socket
import sys
import time

import cv2
import numpy as np
import skimage

from optofidelity.videoproc.io import AbstractVideoReader


class Phantom(object):
  HOST_IP = '100.100.100.1' # The host computer must have this IP

  LIVE_PREVIEW_CINE = 0
  DEFAULT_CINE = 1
  DATA_STREAM_PORT = 7116
  MAX_MESSAGE_SIZE = 65536
  LIVE_PREVIEW_WINDOW = 'Live Preview'
  MAX_PTFRAMES = 2245

  FLAGS = {
    'READY': 'RDY', # A cine is ready to record into
    'COMPLETE': 'STR', # A full cine is already recorded here
    'INVALID': 'INV', # Invalid cine, can't be used for anything
    'WAITING': 'WTR', # Waiting for a trigger to start recording
  }

  def __init__(self, ip=None, port=7115, debug=False):
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
    self.name = ""
    self.ip = ip
    self.port = port
    self.debug = debug

    if ip is None:
      # Find the camera on the network
      self.DebugPrint('Checking network for cameras...')
      self.Discover(Phantom.HOST_IP)
      self.DebugPrint(' * Camera "%s" found at %s, port %d' %
                      (self.name, self.ip, self.port))

    # Set up the command connection
    self.cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.cmd_sock.connect((self.ip, self.port))

    # Set up the data connection
    self.data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.data_sock.connect((self.ip, Phantom.DATA_STREAM_PORT))
    data_port = self.data_sock.getsockname()[1]
    self.SendCommand('attach {port: %d}' % data_port)

  def Partition(self, cine_count):
    """Partition camera memory to hold cine_count of cine_files"""
    self.SendCommand('partition %d' % cine_count)

  def DebugPrint(self, msg):
    """Print debug message if the debug flag is set."""
    if self.debug:
      print msg

  def Discover(self, host_ip):
    """Find the camera on the network, and note its contact information.

    Phantom cameras are equipped with a discovery protocol.  To find them,
    you need to send a broadcast UDP packet with the data 'phantom?' and
    wait for their response.  The camera will inform you which model camera
    it is as well as its ip address and communication port number.
    """
    BROADCAST_IP = '<broadcast>'
    DISCOVERY_PORT = 7380
    DISCOVERY_MESSAGE = 'phantom?'
    RECV_BUFFER_SIZE = 64
    RESPONSE_REGEX = ('PH16\s+(?P<port>\d+)\s+(?P<hwver>\d+)' +
                      '\s+(?P<serial>\d+)\s+"(?P<name>.*)"')

    # Set up a socket on the discovery protocol port
    discovery_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    discovery_sock.bind((host_ip, DISCOVERY_PORT))
    discovery_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # Send out the discovery message as a UDP broadcast message
    discovery_sock.sendto(DISCOVERY_MESSAGE, (BROADCAST_IP, DISCOVERY_PORT))

    # Wait for a response from the camera and parse the information
    # as well as save it for later reference
    # format:  PH16 port hwversion serialnumber "name"
    # example: PH16 7115 8001 13826 "chromeos-hw"
    matches = None
    while not matches:
      data, addr = discovery_sock.recvfrom(RECV_BUFFER_SIZE)
      matches = re.match(RESPONSE_REGEX, data)

    self.port = int(matches.group('port'))
    self.hwver = int(matches.group('hwver'))
    self.serial = int(matches.group('serial'))
    self.name = matches.group('name')
    self.ip = addr[0]

  @property
  def fps(self):
    return self._GetProperty("defc.rate")

  @fps.setter
  def fps(self, value):
    self._SetProperty("defc.rate", value)

  @property
  def exposure(self):
    return self._GetProperty("defc.exp")

  @exposure.setter
  def exposure(self, value):
    self._SetProperty("defc.exp", value)

  def _SetProperty(self, name, value):
    cmd = "set %s %s" % (name, str(value))
    res = self.SendCommand(cmd)
    if not "Ok" in res:
      raise Exception("Cannot set %s to %s: %s" % (name, value, res))

  def _GetProperty(self, name):
    cmd = "get %s" % name
    res = self.SendCommand(cmd)
    regex = re.compile("\S+ : (\S+)")
    match = regex.search(res)
    if not match:
      raise Exception("Invalid response: %s", res)
    return match.group(1)

  def IsReady(self, cine_number=DEFAULT_CINE):
    """True if the cine file is ready to be read or recorded into."""
    state = self.SendCommand('get c%d.state' % cine_number)
    return (Phantom.FLAGS['COMPLETE'] in state or
            Phantom.FLAGS['READY'] in state)

  def WaitUntilReady(self, cine_number=DEFAULT_CINE):
    """Sleep until the cine file is ready"""
    while not self.IsReady(cine_number):
      time.sleep(0.1)

  def Record(self, num_frames=MAX_PTFRAMES, cine_number=DEFAULT_CINE):
    """Record num_frames into the cine slot.

    This function will override any existing recording in this slot. The
    recording is prepared and immediately triggered, recording num_frames
    of frames after this function returns.
    """
    if num_frames > Phantom.MAX_PTFRAMES:
      raise ValueError('Cannot record more than %d frames' % MAX_PTFRAMES)

    #if not self.IsReady(cine_number):
    #  raise Exception('cine%d is not ready for recording' % cine_number)

    self._SetProperty("defc.ptframes", num_frames)
    self.SendCommand('rec %d' % cine_number)
    self.SendCommand('trig %d' % cine_number)

  def SendCommand(self, cmd):
    """Send a command to the camera, and return the response."""
    if len(cmd) >= Phantom.MAX_MESSAGE_SIZE - 1:
      raise ValueError('Message too long!')

    self.DebugPrint('SEND(%d): %s' %(len(cmd), cmd))
    self.cmd_sock.send('%s\r' % cmd)

    recv = ''
    while True:
      block = self.cmd_sock.recv(Phantom.MAX_MESSAGE_SIZE)
      recv += block
      if len(block) == 0 or (len(block) > 2 and block[-1] == '\n'
                            and block[-2] != '\\'):
        break
    self.DebugPrint('RECV(%d): %s' % (len(recv), recv))
    return recv

  def GetVideoReader(self, cine_number=DEFAULT_CINE):
    """Return a VideoReader that accesses a cine slot directly.

    The video reader fully supports seeking and reading of frames and
    will stream all frames directly over ethernet from the camera.
    """
    return PhantomVideoReader(self, cine_number)

  def GetImages(self, start_frame, num_frames, cine_number=DEFAULT_CINE):
    """Pull the selected images from a cine stored in ram.

    Given the cine to pull from and the range of frames, this function
    downloads the requested frames from the camera and then returns a list of
    images represented as numpy matrices. The images are assumed to be 8-bit
    grayscale images.
    """
    # Send the request to the camera for the frame in question
    cmd = ('img {cine:%d, start:%d, cnt:%d}' %
         (cine_number, start_frame, num_frames))
    data = self.SendCommand(cmd)

    # Determine the resolution of the image and how many bytes to wait for
    RESOLUTION_REGEX = ('.*Ok!\s*{\s*cine\s*:\s*\d+,\s*res\s*:\s*' +
                        '(?P<width>\d+)\s+x\s+(?P<height>\d+)\s*}')
    matches = re.match(RESOLUTION_REGEX, data)
    w = int(matches.group('width'))
    h = int(matches.group('height'))
    frame_size = w * h
    total_size = frame_size * num_frames

    # Wait for all the data to come in
    img_data = ''
    while (len(img_data) < total_size):
      ready = select.select([self.data_sock], [], [], 5)
      if ready[0]:
        img_data += self.data_sock.recv(Phantom.MAX_MESSAGE_SIZE)
      else:
        raise Exception('No data received')

    images = []
    for i in range(num_frames):
      image = np.zeros((h, w))
      img_start = i * frame_size
      img_end = (i + 1) * frame_size
      img_string = img_data[img_start:img_end]

      image = np.fromstring(img_string, dtype=np.uint8).reshape((h, w))
      images.append(image)

    return images

  def _JoinSplitLines(self, s):
    return s.replace('\\\r\n', '')

  def GetNumFrames(self, cine_number=DEFAULT_CINE):
    """Returns the number of frames that the cine file recorded."""
    return int(self._GetProperty('c%d.lastfr' % cine_number)) + 1

  def DownloadVideo(self, filename='out.avi', cine_number=DEFAULT_CINE):
    """Download a video from the camera and save it as an avi.

    The video is transfered in reasonable chunks of frames to the local
    machine over the network and compiled into an avi video saved to disk as
    the supplied filename.
    """
    # Figure out how many frames are in that video
    num_frames= self.GetNumFrames(cine_number)

    # Read in chunks of frames and add them to the video
    CHUNK_SIZE = 50
    out = None
    start = 0
    while start < num_frames:
      num_to_get = min([CHUNK_SIZE, num_frames])
      images = self.get_images(start, num_to_get)
      start += num_to_get

      if not out:
        h, w = images[0].shape
        out = cv2.VideoWriter(filename, cv2.cv.CV_FOURCC(*'XVID'),
                    20.0, (w, h))
      for i, image in enumerate(images):
        # Convert them to RGB numpy array images because that's the
        # only format VideoWriter on Linux likes
        out.write(cv2.cvtColor(image, cv2.COLOR_GRAY2RGB))

  def DisplayLivePreview(self):
    """Launch a window with a live stream of what the camera is seeing.

    By querying frames one at a time from the "live preview" cine, this
    function opens up a window to display a live feed of what the camera
    is currently recording.  This can be used to focus/aim the camera
    correctly and is not intended to be used while other clients are
    communicating with the camera.

    The window is paused/unpaused with the spacebar and pressing 'q' quits.
    """
    cv2.namedWindow(Phantom.LIVE_PREVIEW_WINDOW)

    key = None
    while key != ord('q') and key != ord('Q'):
      images = self.GetImages(0, 1, cine_number=Phantom.LIVE_PREVIEW_CINE)
      if len(images) != 1:
        break

      cv2.imshow(Phantom.LIVE_PREVIEW_WINDOW, images[0])

      key = cv2.waitKey(1) & 0xFF
      # If the user pressed space, pause until space is hit again
      if key == ord(' '):
        key2 = None
        while key2 != ord(' '):
          key2 = cv2.waitKey(0) & 0xFF

    cv2.destroyAllWindows()


class PhantomVideoReader(AbstractVideoReader):
  """Implementation of a VideoReader streaming from a Phantom camera.

  This class works as a fully functional VideoReader, streaming frames
  directly from the camera via ethernet.
  """
  def __init__(self, phantom, cine_number=Phantom.DEFAULT_CINE):
    self.phantom = phantom
    self.cine_number = cine_number
    AbstractVideoReader.__init__(self, phantom.GetNumFrames(cine_number))

  def _SeekTo(self, frame):
    self.current_frame = frame

  def Read(self):
    images = self.phantom.GetImages(self.current_frame, 1, self.cine_number)
    return skimage.img_as_float(images[0])


if __name__ == "__main__":
  def UsageAndExit():
    print 'Usage: python %s function function_args...' % __file__
    print
    print 'Recording:\tpython %s record [filename.avi]' % __file__
    print 'Live Preview:\tpython %s preview' % __file__
    print 'Command Shell:\tpython %s shell' % __file__
    sys.exit(1)

  if len(sys.argv) < 2:
    UsageAndExit()

  cmd = sys.argv[1]
  if cmd.lower() == 'record':
    phantom = Phantom()
    phantom.Record()
    phantom.WaitForReady()
    phantom.DownloadVideo(sys.argv[2] if len(sys.argv) > 2 else 'out.avi')
  elif cmd.lower() == 'preview':
    Phantom().DisplayLivePreview()
  elif cmd.lower() == "shell":
    phantom = Phantom(debug=True)
    while True:
      print "Phantom >"
      cmd = sys.stdin.readline().strip()
      phantom.SendCommand(cmd)
  else:
    UsageAndExit()

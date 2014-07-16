# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Phantom high-speed camera communication

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
import Image
import numpy as np


class Phantom:
    HOST_IP = '100.100.100.1' # The host computer must have this IP

    LIVE_PREVIEW_CINE = 0
    DEFAULT_CINE = 1
    DATA_STREAM_PORT = 7116
    MAX_MESSAGE_SIZE = 65536
    LIVE_PREVIEW_WINDOW = 'Live Preview'

    FLAGS = {
        'READY': 'RDY', # A cine is ready to record into
        'COMPLETE': 'STR', # A full cine is already recorded here
        'INVALID': 'INV', # Invalid cine, can't be used for anything
        'WAITING': 'WTR', # Waiting for a trigger to start recording
    }

    def __init__(self):
        """ Set up all communications with the camera

        When a new Phantom object is made it will broadcast out over the
        network to find the camera and initialize command and data TCP
        connections with it so that future interactions with the camera
        work.
        """
        # Find the camera on the network
        print 'Checking network for cameras...'
        self.discover(Phantom.HOST_IP)
        print (' * Camera "%s" found at %s, port %d' %
               (self.name, self.ip, self.port))

        # Set up the command connection
        print 'Establishing command connection...'
        self.cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.cmd_sock.connect((self.ip, self.port))
        print ' * Ok!'

        # Set up the data connection
        print 'Opening data stream socket...'
        self.data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_sock.connect((self.ip, Phantom.DATA_STREAM_PORT))
        print ' * Ok!'
        data_port = self.data_sock.getsockname()[1]
        print 'Attaching camera data stream socket (port: %d)...' % data_port
        print ' * %s' % self.send_command('attach {port: %d}' % data_port)

    def discover(self, host_ip):
        """ Find the camera on the network, and note its contact information

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

    def prepare_cine_for_trigger(self, cine_number=DEFAULT_CINE):
        """ Prepare the given cine (in RAM) to be recorded onto

        This function will clear/delete any existing video in the slot and set
        it up to accept a software trigger to begin the actual recording.
        """
        flags = self._get_cine_state(cine_number)
        while (Phantom.FLAGS['READY'] not in flags and
               Phantom.FLAGS['WAITING'] not in flags):
            print 'Cine not ready, deleting...'
            # First release any locks on the cine that the camera may have
            self.send_command('rel %d' % cine_number)
            # Then delete the file from RAM
            self.send_command('del %d' % cine_number)
            flags = self._get_cine_state(cine_number)
            time.sleep(0.5)

    def _get_cine_state(self, cine_number=DEFAULT_CINE):
        return self.send_command('get c%d.state' % cine_number)

    def trigger_cine_recording(self, cine_number=DEFAULT_CINE):
        """ Configure and then immediately trigger recording of a video

        This function will first confirm the Cine is ready to be triggered.
        (This should be very fast if you already prepared the cine) then
        trigger a recording immediately by sending a software trigger to
        the camera.  The function then blocks until the "complete" flag is
        set for that cine, indicating that it has finished recording.
        """
        # Make sure the cine in question is ready to be recorded
        self.prepare_cine_for_trigger(cine_number)

        # Start recording
        self.send_command('rec %d' % cine_number)
        self.send_command('trig %d' % cine_number)

        # Block until the recording has completed
        flags = self._get_cine_state(cine_number)
        while Phantom.FLAGS['COMPLETE'] not in flags:
            time.sleep(1)
            flags = self._get_cine_state(cine_number)
            print 'Waiting for recording to complete (%s)...' % flags.rstrip()

    def send_command(self, cmd):
        """ Send a command to the camera, and return the response """
        if len(cmd) >= Phantom.MAX_MESSAGE_SIZE - 1:
            print 'Error, message too long!'
            return None
        self.cmd_sock.send('%s\r' % cmd)
        return self.cmd_sock.recv(Phantom.MAX_MESSAGE_SIZE)

    def get_images(self, start_frame, num_frames, cine_number=DEFAULT_CINE):
        """ Pull the selected images from a cine stored in ram

        Given the cine to pull from and the range of frames, this function
        downloads the requested frames from the camera and then reformats
        them into PIL Image objects that it returns in an array.  The images
        are assumed to be 8-bit grayscale images.
        """
        # Send the request to the camera for the frame in question
        print ('Requesting %d frames from cine %d starting at %d...' %
               (num_frames, cine_number, start_frame))
        cmd = ('img {cine:%d, start:%d, cnt:%d}' %
               (cine_number, start_frame, num_frames))
        data = self.send_command(cmd)
        print ' * %s' % data.rstrip()

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
            print '\r   Received data (%d/%d)' % (len(img_data), total_size),
            ready = select.select([self.data_sock], [], [], 5)
            if ready[0]:
                img_data += self.data_sock.recv(Phantom.MAX_MESSAGE_SIZE)
            else:
                print 'ERROR: no data received'
                print self.send_command('get status')
        print '\r   Received data (%d/%d)' % (len(img_data), total_size)

        images = []
        for i in range(num_frames):
            image = np.zeros((h, w))
            img_start = i * frame_size
            img_end = (i + 1) * frame_size
            img_string = img_data[img_start:img_end]

            image = np.fromstring(img_string, dtype=np.uint8).reshape((h, w))
            images.append(image)

        return images

    def _join_split_lines(self, s):
        return s.replace('\\\r\n', '')

    def get_frame_range(self, cine_number=DEFAULT_CINE):
        """ Find the frame numbers for the first and last frames in a cine

        This function requests the details for the specified cine (in ram) and
        parses them, looking for the first and last frame numbers.  This allows
        the user to determine the range of legal frame numbers to request for
        this cine.
        """
        FRAME_RANGE_REGEX = ('^.*firstfr\s*:\s*(?P<first_frame>[\-\d]+),.*' +
                             'lastfr\s*:\s*(?P<last_frame>\d+),.*$')

        cmd = 'get c%d' % cine_number
        details = self._join_split_lines(self.send_command(cmd))
        matches = re.match(FRAME_RANGE_REGEX, details)

        first = int(matches.group('first_frame'))
        last = int(matches.group('last_frame'))
        return first, last

    def download_video(self, filename='out.avi', cine_number=DEFAULT_CINE):
        """ Download a video from the camera and save it as an avi

        The video is transfered in reasonable chunks of frames to the local
        machine over the network and compiled into an avi video saved to disk as
        the supplied filename.
        """
        # Figure out how many frames are in that video
        first_frame, last_frame = self.get_frame_range(cine_number)

        # Read in chunks of frames and add them to the video
        CHUNK_SIZE = 50
        out = None
        start = first_frame
        while start < last_frame:
            num_to_get = min([CHUNK_SIZE, last_frame - start])
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

    def display_live_preview(self):
        """ Launch a window with a live stream of what the camera is seeing

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
            images = self.get_images(0, 1, cine_number=Phantom.LIVE_PREVIEW_CINE)
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



if __name__ == "__main__":
    def usage_and_exit():
        print 'Usage: python %s function function_args...' % __file__
        print
        print 'Recording:\tpython %s record [filename.avi]' % __file__
        print 'Live Preview:\tpython %s preview' % __file__
        sys.exit(1)

    if len(sys.argv) < 2:
        usage_and_exit()

    cmd = sys.argv[1]
    if cmd.lower() == 'record':
        phantom = Phantom()
        phantom.prepare_cine_for_trigger()
        phantom.trigger_cine_recording()
        phantom.download_video(sys.argv[2] if len(sys.argv) > 2 else 'out.avi')
    elif cmd.lower() == 'preview':
        Phantom().display_live_preview()
    else:
        usage_and_exit()

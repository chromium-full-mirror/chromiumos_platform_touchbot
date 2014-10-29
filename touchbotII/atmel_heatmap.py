# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This tool loads the raw data from an Atmel touchpad/touchscreen and displays
# a heatmap with those sensor readings to the terminal.  Press Ctrl+C to stop.
#
# Usage:   python atmel_heatmap.py i2c_address
# Example: python atmel_heatmap.py 0-004b

import optparse
import os
import signal
import sys


class AtmelDebugFile:
    DEBUG_PATH = '/sys/kernel/debug/atmel_mxt_ts/'
    SYSFS_PATH = '/sys/bus/i2c/devices/'

    def __init__(self, device_addr=''):
        dbgfs_path = os.path.join(AtmelDebugFile.DEBUG_PATH, device_addr)
        sysfs_path = os.path.join(AtmelDebugFile.SYSFS_PATH, device_addr)

        self.deltas_path = os.path.join(dbgfs_path, 'deltas')
        self.refs_path = os.path.join(dbgfs_path, 'refs')
        self.matrix_size_path = os.path.join(sysfs_path, 'matrix_size')
        self.paths = [self.deltas_path, self.refs_path, self.matrix_size_path]

        self.width, self.height = self.__getMatrixSize()

    def isValid(self):
        """ Check that required files exist. Print error messages if not. """
        for path in self.paths:
            if not os.path.exists(path):
                print 'ERROR: The required file "%s" does not exist' % path
                return False

        dimensions_are_valid = True
        for dim in (self.width, self.height):
            if dim == None or dim <= 0 or type(dim) != int:
                dimensions_are_valid = False
        if not dimensions_are_valid:
            print ('ERROR: Bad dimensions (%s, %s) read from "%s"' %
                    (str(self.width), str(self.height), self.matrix_size_path))
            return False

        return True

    def __signed_int(self, v, bits=16):
        """ Convert from an unsigned int to a signed int. """
        return v if v < 2 ** (bits - 1) else v - 2 ** bits

    def __getValues(self, path):
        """ Parse the contents of path and return a flat array of those ints """
        with open(path, 'r') as fo:
            str_data = fo.read()
        if not str_data:
            print 'ERROR: unable to open the debug file'
        raw = map(ord, str_data)

        # Reformat the data into the actual values.  The data are 16-bit signed
        # integers so you group them in pairs and convert.
        values = [self.__signed_int(raw[i * 2] + (raw[i * 2 + 1] << 8))
                  for i in range(len(raw) / 2)]

        return values

    def __getMatrixSize(self):
        """ Read the matrix_size sysfs entry to determine height and width. """
        width = height = None
        if os.path.isfile(self.matrix_size_path):
            with open(self.matrix_size_path, 'r') as fo:
                width, height = [int(v) for v in fo.read().split()]
        return width, height

    def getDeltas(self):
        return self.__getValues(self.deltas_path)

    def getRefs(self):
        return self.__getValues(self.refs_path)

    def __grayscale(self, string, shade):
        """ Wrap a string with the code for a shade of gray from 0.0->1.0. """
        BLACK = 232
        WHITE = 255
        shade = max(min(shade, 1.0), 0.0)  # Clip the value to 0.0-1.0
        color = int(BLACK + (WHITE - BLACK) * shade)
        return '\x1b[48;5;%dm%s\x1b[0m' % (color, string)

    def __displayValues(self, values):
        """ Given an array of sensor values, display them as a heatmap. """
        # Values that are exactly 0.0 are likely disconnected lines
        min_val = min([v for v in values if v != 0.0])
        max_val = max(values)

        for y in range(self.height):
            for x in range(self.width):
                value = values[y + x * self.height]
                shade = float(value - min_val) / float(max_val - min_val)
                print self.__grayscale('%04d' % value, shade),
            print

    def displayDeltas(self):
        self.__displayValues(self.getDeltas())

    def displayRefs(self):
        self.__displayValues(self.getRefs())


def main(i2c_address, options):
    # First, setup the debug file
    dbg = AtmelDebugFile(i2c_address)
    if not dbg.isValid():
        sys.exit(1)

    # When the user hits Ctrl+C set a flag to indicate they want to stop.  This
    # tries to prevent the cursor ending in a random spot when you're done.
    should_exit = False
    def handler(signal, frame):
        should_exit = True
    signal.signal(signal.SIGINT, handler)

    # Actually display the live feed
    while True:
        if options.data_choice == 'refs':
            dbg.displayRefs()
        else:
            dbg.displayDeltas()

        if should_exit:
            # If the user hit Ctrl+C, stop here and don't start a new frame
            print '\033[0m'
            break
        else:
            # Return the cursor to the start to redraw the next frame over it
            print '\r\033[%dA' % (dbg.height + 1)


if __name__ == '__main__':
    parser = optparse.OptionParser(
        usage='Usage: python %prog i2c_address [options]')
    parser.add_option('-d', '--data', dest='data_choice', default='deltas',
                      help=('Select which data to visualize for this ' +
                            'device: "deltas" or "refs"'))
    (options, args) = parser.parse_args()

    if len(args) != 1:
        parser.error('Incorrect number of arguments')

    if not options.data_choice in ['deltas', 'refs']:
        parser.error('Invalid value for --data "%s". must be "refs" or "deltas"'
                        % options.data_choice)

    main(args[0], options)

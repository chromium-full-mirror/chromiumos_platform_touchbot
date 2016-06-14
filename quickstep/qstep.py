# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Runs the touchpad drag latency test using QuickStep v2
# Usage example:
#     $ python qstep.py 6
#     Input device   : /dev/input/event6
#     Serial device  : /dev/ttyACM1
#     Laser log file : /tmp/QuickStep_2016_01_21__1554_22_lsaer.log
#     evtest log file: /tmp/QuickStep_2016_01_21__1554_22_evtest.log
#     Clock zeroed at 1453409662 (rt 0.259ms)
#     ........................................
#     Processing data, may take a minute or two...
#     Drag latency (min method) = 19.62 ms
#     Average Maximum Minimum
#     0.0237723313845 0.0333168506622 0.0167829990387
#
# Note, before running this script, check that evtest can grab the device.

import argparse
import glob
import os
import subprocess
import sys
import tempfile
import time

import serial
import numpy

import latency_measurement as lm
import minimization


# Teensy commands (always singe char). Defined in QuickStep.ino
# TODO(kamrik): link to QuickStep.ino once it's opensourced.
CMD_RESET = 'F'
CMD_SYNC_ZERO = 'Z'
CMD_TIME_NOW = 'T'
CMD_AUTO_LASER_ON = 'L'
CMD_AUTO_LASER_OFF = 'l'

# Globals
debug_mode = False


def log(msg):
    if debug_mode:
        print(msg)


def sndrcv(ser, data):
    """ Send a 1-char command.
    Return the reply and how long it took.

    """
    t0 = time.time()
    ser.write(data)
    reply = ser.readline()
    t1 = time.time()
    dt = (t1 - t0) * 1000
    log('sndrcv(): round trip %.3fms, reply=%s' % (dt, reply.strip()))
    return dt, reply


def runCommStats(ser, N=100):
    """
    Measure the USB serial round trip time.
    Send CMD_TIME_NOW to the Teensy N times measuring the round trip each time.
    Prints out stats (min, median, max).

    """
    log('Running USB comm stats...')
    ser.flushInput()
    sndrcv(ser, CMD_SYNC_ZERO)
    tstart = time.time()
    times = numpy.zeros((N, 1))
    for i in range(N):
        dt, _ = sndrcv(ser, CMD_TIME_NOW)
        times[i] = dt
    t_tot = (time.time() - tstart)*1000

    median = numpy.median(times)
    stats = (times.min(), median, times.max(), N)
    log('USB comm round trip stats:')
    log('min=%.2fms, median=%.2fms, max=%.2fms N=%d' % stats)
    if (median > 2):
        print('ERROR: the median round trip is too high: %.2f' % median)
        sys.exit(2)


def zeroClock(ser, max_delay_ms=1.0, retries=10):
    """
    Tell the TeensyUSB to zero its clock (CMD_SYNC_ZERO).
    Returns the time when the command was sent.
    Verify that the response arrived within max_delay_ms.

    This is the simple zeroing used when the round trip is fast.
    It does not employ the same method as Android clock sync.
    """

    # Check that we get reasonable ping time with Teensy
    # this also 'warms up' the comms, first msg is often slower
    runCommStats(ser, N=10)

    ser.flushInput()

    for i in range(retries):
        t0 = time.time()
        dt, _ = sndrcv(ser, CMD_SYNC_ZERO)
        if dt < max_delay_ms:
            print('Clock zeroed at %.0f (rt %.3fms)' % (t0, dt))
            return t0
    print('Error, failed to zero the clock after %d retries')
    return -1


def parseTrigger(trigger_line):
    """ Parse a trigger line from QuickStep.

    Trigger events look like this: "G L 12902345 1 1"
    The parts:
     * G - common for all trigger events
     * L - means laser
     * 12902345 is timestamp in us since zeroed
     * 1st 1 or 0 is trigger value. 0 = changed to dark, 1 = changed to light,
     * 2nd 1 is counter of how many times this trigger happened since last
       readout, should always be 1 in our case

    """

    parts = trigger_line.strip().split()
    if len(parts) != 5:
        raise Exception('Malformed laser trigger line:\n' + trigger_line)
    t_us = int(parts[2])
    val = int(parts[3])
    return (t_us / 1e6, val)


def parse_args():
    temp_dir = tempfile.gettempdir()
    serial = '/dev/ttyACM0'

    # Try to autodetect the QuickStep serial port
    ls_ttyACM = glob.glob('/dev/ttyACM*')
    if len(ls_ttyACM) > 0:
        serial = ls_ttyACM[0]

    description = "Run the touchpad drag latency test using QuickStep v2"
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('input',
                        help='input device, e.g: 6 or /dev/input/event6')
    parser.add_argument('-s', '--serial', default=serial,
                        help='QuickStep serial port')
    parser.add_argument('-l', '--logdir', default=temp_dir,
                        help='where to store logs')
    parser.add_argument('-n', default=40, type=int,
                        help='Number of laser toggles to read')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='talk more')
    args = parser.parse_args()

    global debug_mode
    debug_mode = args.debug

    if args.input.isalnum():
        args.input = '/dev/input/event' + args.input

    return args


if __name__ == '__main__':
    args = parse_args()
    # Create names for log files
    prefix = time.strftime('QuickStep_%Y_%m_%d__%H%M_%S')
    laser_file_name = os.path.join(args.logdir,  prefix + '_lsaer.log')
    evtest_file_name = os.path.join(args.logdir,  prefix + '_evtest.log')

    print('Input device   : ' + args.input)
    print('Serial device  : ' + args.serial)
    print('Laser log file : ' + laser_file_name)
    print('evtest log file: ' + evtest_file_name)

    with serial.Serial(args.serial, 115200) as ser:
        sndrcv(ser, CMD_RESET)
        tstart = time.time()
        t_zero = zeroClock(ser)
        if t_zero < 0:
            print('Error: Couldn\'t zero clock, exitting')
            sys.exit(1)

        # Fire up the evtest process
        cmd = 'evtest %s > %s' % (args.input, evtest_file_name)
        evtest = subprocess.Popen(cmd, shell=True)

        # Turn on laser trigger auto-sending
        sndrcv(ser, CMD_AUTO_LASER_ON)
        trigger_count = 0
        while trigger_count < args.n:
            # The following line blocks until a message from QuickStep arrives
            trigger_line = ser.readline()
            trigger_count += 1
            log('#%d/%d - ' % (trigger_count, args.n) +
                trigger_line.strip())

            if not debug_mode:
                sys.stdout.write('.')
                sys.stdout.flush()

            t, val = parseTrigger(trigger_line)
            t += t_zero
            with open(laser_file_name, 'at') as flaser:
                flaser.write('%.3f %d\n' % (t, val))
        sndrcv(ser, CMD_AUTO_LASER_OFF)

    # Send SIGTERM to evtest process
    evtest.terminate()

    print "\nProcessing data, may take a minute or two..."
    lm.main(evtest_file_name, laser_file_name)

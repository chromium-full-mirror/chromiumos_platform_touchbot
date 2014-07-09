# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This file tells the HP 33120A waveform generater to output signals of the
# given shape, frequency, and amplitude. The serial communication uses standard
# SCPI over RS232 8N2.
#
# HP 33120A Manual:
# http://sdphca.ucsd.edu/Lab_Equip_Manuals/Agilent_33120a_Users.pdf
#
# Usage: python generate_noise.py [SQUARE/SINE/OFF] [frequency (Hz)]
#           [amplitude (Vpp)]
# Ex: python generate_noise.py SQUARE 3000 20
#
# Using Python 2.7
# ----------------------------------------------
# Mindy Huang (mindyh@google.com)

import serial
import sys
import time

# Constants
RESPONSE_DELAY_S = 0.3
HIGH_Z_THRESHOLD = 10


# Send and potentially receive a message from the fn generator.
def send_message(message, ser):
    # The newline at the end is necessary to terminate the message.
    ser.write(message + '\n')

    # The device will only respond if prompted with a '?'.
    if '?' in message:
        return ser.readline()

    # Give the function generator some time to react
    time.sleep(0.5)


def generate_function(form, freq, ampl, ser):
    # puts the generator in remote mode
    send_message('SYST:REM', ser)

    if(ampl > HIGH_Z_THRESHOLD):
        # This puts the generator into high impedance (high Z) mode
        # so it can reach up to 20Vpp.
        send_message('OUTP:LOAD INF', ser)
    else:
        # Keeps the generator in low impedance mode (default).
        send_message('OUTP:LOAD 50', ser)

    send_message('APPL:%s %E, %d' % (form, freq, ampl), ser)


def error_message():
    print("Usage: python generate_noise.py [SQUARE/SINE/OFF]" +
          " [frequency (Hz)] [amplitude (Vpp)]")
    print("Ex: python generate_noise.py SQUARE 3000 20")


def main():
    # Open a connection to the serial port.
    ser = serial.Serial(
        port='/dev/ttyUSB0',
        baudrate=9600,
        stopbits=serial.STOPBITS_TWO,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        timeout=1
    )

    ser.open()

    if(len(sys.argv) > 1):
        if (sys.argv[1] == 'OFF'):  # Turns the function generator off.
            send_message('APPL:DC 1, 1, 0', ser)

        elif (len(sys.argv) == 2):  # The script was given a custom command.
            print send_message(sys.argv[1], ser)

        elif(len(sys.argv) == 4):  # Generate a waveform.
            freq = int(sys.argv[2])
            ampl = int(sys.argv[3])
            form = 'SQU' if (sys.argv[1] == 'SQUARE') else 'SIN'

            generate_function(form, freq, ampl, ser)
    else:
        error_message()

    ser.close()


if __name__ == '__main__':
    main()

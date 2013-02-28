#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
#
# Toshiba Machine Co, LTD.
# ROIBOT
# BA Series
# CA10-M00
#
# Industrial robot interface mode control module
#

errorTable = {
    "12" : "Watchdog timer error",
    "13" : "Emergency stop",

    "20" : "Axis 1 communication error",
    "21" : "Axis 1 overspeed error",
    "22" : "Axis 1 overcurrent error",
    "23" : "Axis 1 overload error",
    "24" : "Axis 1 overflow",
    "25" : "Axis 1 BS servo amplifier alarm",
    "26" : "Axis 1 encoder error",
    "27" : "Axis 1 Home positioning error",
    "28" : "Axis 1 + soft limit exceeded (during execution)",
    "29" : "Axis 1 - soft limit exceeded (during execution)",
    "2A" : "Axis 1 overvoltage error",
    "2B" : "Axis 1 motor overheat error",
    "2C" : "Axis 1 encoder backup error",
    "2D" : "Axis 1 encoder switching error",
    "2F" : "Axis 1 driver error",
    "30" : "Axis 2 communication error",
    "31" : "Axis 2 overspeed error",
    "32" : "Axis 2 overcurrent error",
    "33" : "Axis 2 overload error",
    "34" : "Axis 2 overflow",
    "35" : "Axis 2 BS servo amplifier alarm",
    "36" : "Axis 2 encoder error",
    "37" : "Axis 2 Home positioning error",
    "38" : "Axis 2 + soft limit exceeded (during execution)",
    "39" : "Axis 2 - soft limit exceeded (during execution)",
    "3A" : "Axis 2 overvoltage error",
    "3B" : "Axis 2 motor overheat error",
    "3C" : "Axis 2 encoder backup error",
    "3D" : "Axis 2 encoder switching error",
    "3F" : "Axis 2 driver error",
    "40" : "Axis 3 communication error",
    "41" : "Axis 3 overspeed error",
    "42" : "Axis 3 overcurrent error",
    "43" : "Axis 3 overload error",
    "44" : "Axis 3 overflow",
    "45" : "Axis 3 BS servo amplifier alarm",
    "46" : "Axis 3 encoder error",
    "47" : "Axis 3 Home positioning error",
    "48" : "Axis 3 + soft limit exceeded (during execution)",
    "49" : "Axis 3 - soft limit exceeded (during execution)",
    "4A" : "Axis 3 overvoltage error",
    "4B" : "Axis 3 motor overheat error",
    "4C" : "Axis 3 encoder backup error",
    "4D" : "Axis 3 encoder switching error",
    "4F" : "Axis 3 driver error",
    "50" : "Axis 4 communication error",
    "51" : "Axis 4 overspeed error",
    "52" : "Axis 4 overcurrent error",
    "53" : "Axis 4 overload error",
    "54" : "Axis 4 overflow",
    "55" : "Axis 4 BS servo amplifier alarm",
    "56" : "Axis 4 encoder error",
    "57" : "Axis 4 Home positioning error",
    "58" : "Axis 4 + soft limit exceeded (during execution)",
    "59" : "Axis 4 - soft limit exceeded (during execution)",
    "5A" : "Axis 4 overvoltage error",
    "5B" : "Axis 4 motor overheat error",
    "5C" : "Axis 4 encoder backup error",
    "5D" : "Axis 4 encoder switching error",
    "5F" : "Axis 4 driver error",

    "60" : "Continuous execution failure",
    "61" : "Return to origin incoplete",
    "62" : "Unexecutable",
    "63" : "Task starting disabled",
    "64" : "Synchronized axes origin search incomplete",
    "65" : "Excessive synchronization error",
    "66" : "Synchronized axes parameter error",
    "67" : "Synchronized axes origin search error",

    "90" : "ID error",
    "91" : "Sequential program memory error",
    "92" : "Palletizing program memory error",
    "93" : "Parameter memory error",
    "94" : "Coordinate table memory error",
    "95" : "Speed table memory error",
    "96" : "Acceleration/deceleration table memory error",
    "97" : "MVMtable memory error",
    "98" : "Easy program memory error",
    "99" : "Slave ID error",

    "A0" : "Command error (impossible command)",
    "A1" : "Tag undefined",
    "A2" : "Tag duplicate definition",
    "A3" : "Stack overflow",
    "A4" : "Stack underflow",
    "A8" : "Parameter error",
    "B0" : "Step number error",
    "B1" : "Tag number error",
    "B2" : "Palletizibng program number error",
    "B3" : "Counter number error",
    "B4" : "Timer number error",
    "B5" : "Port number error",
    "B6" : "Table number error",
    "B7" : "Group number error",
    "B9" : "Easy program number error",
    "BA" : "Task number error",
    "C0" : "Axis 1 + soft limit exceeded",
    "C1" : "Axis 1 - soft limit exceeded",
    "C2" : "Axis 2 + soft limit exceeded",
    "C3" : "Axis 2 - soft limit exceeded",
    "C4" : "Axis 3 + soft limit exceeded",
    "C5" : "Axis 3 - soft limit exceeded",
    "C6" : "Axis 4 + soft limit exceeded",
    "C7" : "Axis 4 - soft limit exceeded",
    "E0" : "Other errors"
}

alarmTable = {
    "01" : "Overcurrent (OC)",
    "02" : "Overvoltage (OV)",
    "03" : "PN voltage drop (PNLV)",
    "04" : "Main power supply input error (ACINF)",
    "05" : "Charging resistor overheat (CROH)",
    "06" : "Disconnected resolver wire (RELV)",
    "07" : "Power status error (POWFAIL)",
    "08" : "Servo amplifier overheat (SOH)",
    "09" : "Revers-current absorbtion resister overheat (RGOH)",
    "0A" : "Revers-current absorbtion error (RGST)",
    "0B" : "Unspecified error 0B",
    "0C" : "DSP error (DSPERR)",
    "0D" : "ABS battery voltage drop (BLV)",
    "0E" : "Brake error (BERR)",
    "0F" : "Overcurrent detection (OCS)",
    "10" : "Speed Amplifier Saturation (VAS)",
    "11" : "Motor overload (MOL)",
    "12" : "Instant thermal (POL)",
    "13" : "Resolver phase error (RESERR)",
    "14" : "Overspeed (OSPD)",
    "15" : "Deviation counter exceeded (FULL)",
    "16" : "Resolver ABS phase error (ABSE)",
    "17" : "Resolver ABS disconnected wire (ACN)",
    "18" : "ABS battery alarm (ABSE)",
    "19" : "Option alarm (OPALM)",
    "1A" : "Parameter setting error (CERR)",
    "1B" : "Resolver ABS error (AEERR)",
    "1C" : "Link error (LINKERR)",
    "1D" : "Command value exceeded (CON.OV)",
    "1E" : "Current value exceeded (ACT.OV)",
    "1F" : "Unspecified error 1F",
    "20" : "Origin not stored error (MZE)",
    "21" : "ABS origin invalid (CLD)",
    "22" : "+ soft limit exceeded (SOTP)",
    "23" : "- soft limit exceeded (SOTM)",
    "24" : "ABS battery cable disconnected wire (ABT)",
    "25" : "Unbspecified error 25",
    "26" : "Overrun (OVTR)",
    "27" : "Unbspecified error 27",
    "28" : "Encoder disconnected wire (EREE)",
    "29" : "Encoder communication error (ETER)",
    "2A" : "Encoder backup error (ETER)",
    "2B" : "Encoder checksum error (ECKER)",
    "2C" : "Encoder battery alarm (EBAL)",
    "2D" : "Encoder AMS phase error (EABSE)",
    "2E" : "Encoder overspeed (EOSPD)",
    "2F" : "Encoder communication error (EWER)",
    "30" : "Encoder initialization error (EINIT)",
    "31" : "Encoder sensor phase error (PHSERR)",

    "36" : "Magnetic pole detection error (MPERR)",

    "FB" : "PON error (PONERR)",
    "FC" : "Control power supply input error (CACINF)"
}


def translate(errorCode, alarmCode="00"):
    """Translate an error code and optional alarm code to an error string.
       The alarm code is only meaningful for servo amplifier alarms."""
    if errorCode in errorTable:
        if errorCode in ['25', '35', '45', '55']:
            if alarmCode in alarmTable:
                error = errorTable[errorCode] + \
                    " (" + alarmTable[alarmCode] + ")"
            else:
                error = errorTable[errorCode] + \
                    " (unrecognized alarm code)"
        else:
            error = errorTable[errorCode]
    else:
        error = "Unrecognized error code " + errorCode
    return error


def statusReport(roibot):
    """Create a status report.  This function takes a robot handle as an
       argument and queries the robot for status reports 0, 2, 3, and 4,
       and returns a tuple of human readable values for each status report.
       In the special case that report 0 indicates an error, status report
       1 is queried as well, and the error is decoded and appended to the
       error element in the report 0 tuple."""
    report = []

    # SNO=0 status
    element = []
    report0 = roibot.modeRequestStatus(0)
    report0status1 = roibot.parseStatusCode(report0[1][1])
    if report0status1 & 0x01:
        # SNO=1 error code and optional amplifier alarm code
        report1 = roibot.modeRequestStatus(1)
        report1status1 = roibot.parseStatusCode(report1[1][1])
        report1status2 = roibot.parseStatusCode(report1[1][2])
        element.append("error=" + translate(report1status1, report1status2))
    for bit, message in ((0x02, "in execution"),
                         (0x04, "paused"),
                         (0x08, "in return to origin"),
                         (0x10, "Return to origin complete"),
                         (0x20, "Positioning complete"),
                         (0x40, "Undefined status bit 6"),
                         (0x80, "Parameter 2 changed"),
                        ):
        if report0status1 & bit:
            element.append(message)
    report.append(element)

    # SNO=2 Robot mode
    element = []
    report2 = roibot.modeRequestStatus(2)
    report2status1 = roibot.parseStatusCode(report2[1][1])
    # bits 0 1
    for value, message in ((0x00, "Sequential mode"),
                           (0x01, "Palletizing mode"),
                           (0x02, "Point mode"),
                           (0x03, "Easy mode"),
                          ):
        if (report2status1 & 0x03) == value:
            element.append(message)
    # bits 2 3
    for value, message in ((0x00, "Automatic mode"),
                           (0x04, "Step mode"),
                           (0x08, "Program mode"),
                           (0x0c, "Reserved mode value 11b"),
                          ):
        if (report2status1 & 0x0c) == value:
            element.append(message)
    # bits 4 5 6 7
    for bit, message in ((0x10, "Single movement mode"),
                         (0x20, "Reserved SNO=2 bit 0x20"),
                         (0x40, "Teach pendant ON"),
                         (0x80, "Host computer ON"),
                        ):
        if report2status1 & bit:
            element.append(message)
    report.append(element)

    # SNO=3 Servo, slave, and card status (if memory card option is installed)
    element = []
    report3 = roibot.modeRequestStatus(3)
    report3status1 = roibot.parseStatusCode(report3[1][1])
    # bits 0 1 2 3
    for bit, message in ((0x01, "Servo ON"),
                         (0x02, "Reserved SNO=3 bit 0x02"),
                         (0x04, "Reserved SNO=3 bit 0x04"),
                         (0x08, "Reserved SNO=3 bit 0x08"),
                        ):
        if report3status1 & bit:
            element.append(message)
    # bit 5
    if (report3status1 & 0x10) == 0x00:
        element.append("Slave not ready"),
    # bits 6 7 8
    for bit, message in ((0x20, "Card inserted"),
                         (0x40, "Reading card"),
                         (0x80, "Writing to card"),
                        ):
        if report3status1 & bit:
            element.append(message)
    report.append(element)

    # SNO=4 Input and output status
    element = []
    report4 = roibot.modeRequestStatus(4)
    report4status1 = roibot.parseStatusCode(report4[1][1])
    for bit, message in ((0x01, "Escape input ON"),
                         (0x02, "Continuous input ON"),
                         (0x04, "INPUT wait"),
                         (0x08, "Pause input ON"),
                         (0x10, "Ready output"),
                         (0x20, "Reserved SNO=4 bit 0x20"),
                         (0x40, "Reserved SNO=4 bit 0x40"),
                         (0x80, "Reserved SNO=4 bit 0x80"),
                        ):
        if report4status1 & bit:
            element.append(message)
    report.append(element)

    return report


# End

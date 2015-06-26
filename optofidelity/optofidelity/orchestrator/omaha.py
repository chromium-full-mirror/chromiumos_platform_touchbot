# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import csv
from datetime import datetime
import urllib2

_omaha_cache = None

def GetChromeVersionInfo():
  global _omaha_cache
  if _omaha_cache:
    return _omaha_cache

  url = "https://omahaproxy.appspot.com/history?os=android"
  request = urllib2.urlopen(url)
  reader = csv.reader(request)
  versions = {}
  for row in reader:
    if row[0] == "os":
      continue
    release_date = datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S.%f")
    timestamp = (release_date - datetime.utcfromtimestamp(0)).total_seconds()
    versions[row[2]] = (row[1], int(timestamp))
  _omaha_cache = versions
  return versions

def GetLatestChromeVersions(channel):
  return sorted(v for v, (c, t) in GetChromeVersionInfo().iteritems()
                  if c == channel)

def GetChromeBuildTimestamp(version):
  return GetChromeVersionInfo()[version][1]

# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contextlib import contextmanager
import logging
import os
import shutil
import subprocess
import tempfile

from optofidelity.util import ProgressBar

_log = logging.getLogger(__name__)


def GSFindUniqueFilename(folder_url, base_name):
  for i in range(999):
    filename = "%s_%03d" % (base_name, i)
    path = os.path.join(folder_url, filename)
    if not GSPathExists(path):
      return path, filename
  raise Exception("Cannot find unique results path")


def GSTouch(url):
  with GSOpenFile(url, "w") as file_obj:
    file_obj.write("exists")


def GSPathExists(url):
  if url.startswith("gs://"):
    return len(_GSList(url)) > 0
  else:
    return os.path.exists(url)


@contextmanager
def GSFolder(url, upload=True, download=False):
  if not url.startswith("gs://"):
    yield url
    return

  base_folder = tempfile.mkdtemp()
  target_folder = os.path.join(base_folder, os.path.basename(url))
  os.mkdir(target_folder)
  try:
    if download:
      with ProgressBar("Downloading %s" % url):
        _GSCopy(url, base_folder, recursive=True)
    try:
      yield target_folder
    finally:
      if upload:
        with ProgressBar("Uploading %s" % url):
          base_url = url[:-len(os.path.basename(url))]
          _GSCopy(target_folder, base_url, recursive=True)
  finally:
    shutil.rmtree(base_folder)


@contextmanager
def GSFile(url, upload=True, download=False):
  if not url.startswith("gs://"):
    yield url
    return

  suffix = os.path.basename(url)
  temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
  temp_file.close()
  try:
    if download:
      with ProgressBar("Downloading %s" % url):
        _GSCopy(url, temp_file.name)
    try:
      yield temp_file.name
    finally:
      if upload:
        with ProgressBar("Uploading %s" % url):
          _GSCopy(temp_file.name, url)
  finally:
    os.remove(temp_file.name)


@contextmanager
def GSOpenFile(url, mode):
  upload = "a" in mode or "w" in mode
  download = "a" in mode or "r" in mode
  with GSFile(url, upload, download) as gs_file:
    with open(gs_file, mode) as file_object:
      yield file_object


def _GSList(path):
  command = ["gsutil", "ls", path]
  _log.debug(" ".join(command))

  process = subprocess.Popen(command, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
  lines = process.stdout.readlines()
  process.communicate()
  if process.returncode == 0:
    return lines
  return []


def _GSCopy(from_path, to_path, recursive=False):
  if recursive:
    command = ["gsutil", "-m", "cp", "-r"]
  else:
    command = ["gsutil", "cp"]
  command += [from_path, to_path]

  _log.debug(" ".join(command))
  process = subprocess.Popen(command, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
  ret = process.communicate()
  if process.returncode > 0:
    raise Exception("'%s' returned with %d" % (" ".join(command),
                                               process.returncode))

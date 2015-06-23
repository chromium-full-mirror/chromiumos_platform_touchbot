# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of the BenchmarkSystem class."""

from collections import namedtuple
from copy import deepcopy
import cPickle as pickle
import itertools
import os
import re
import xml.etree.ElementTree as ElementTree

from safetynet import (Any, Dict, List, Optional, Tuple, TypecheckMeta,
                       typecheck)

from .detection import (MultithreadedVideoProcessor,
                        SinglethreadedVideoProcessor, VideoProcessor)
from .system import (BenchmarkSubject, BenchmarkSystem, HighSpeedCamera,
                     Navigator, RobotBackend, Updater)
from .system.backend_tnt import TnTRobotBackend
from .system.camera_phantom import PhantomCamera
from .system.fake import FakeHighSpeedCamera, FakeRobotBackend, FakeUpdater
from .system.navigator import (NativeADBNavigator, RobotNavigator,
                               WebADBNavigator)
from .system.system import FingerCalibDelay
from .system.updater import ChromeUpdater, ManualUpdater
from .util import const_property
from .benchmark import BenchmarkRunner
from .orchestrator import Dashboard, Orchestrator

@typecheck
def GetRequired(parent, element_name):
  """Returns child element, throws exception if it does not exist.

  :type parent: ElementTree.Element
  :type element_name: str
  :rtype: ElementTree.Element
  """
  element = parent.find(element_name)
  if element is None:
    raise Exception("Config error: %s element is required in %s" %
                    (element_name, parent.tag))
  return element

@typecheck
def MergeElement(base, merging):
  """Merges the element merging into the element base.

  The merging element will not override any values in the base element, but
  child elements will be appended with the exception of elements that have a
  name="" attribute. Those will be merged with the corresponding element with
  the same name attribute.

  :type base: ElementTree.Element
  :type merging: ElementTree.Element
  """

  for k, v in merging.attrib.items():
    if k not in base.attrib:
      base.attrib[k] = v

  for child in merging:
    child_name = child.get("name")
    existing_child = None

    if child_name:
      for candidate in base.iter(child.tag):
        if candidate.get("name") == child_name:
          existing_child = candidate

    if existing_child is not None:
      MergeElement(existing_child, child)
    else:
      base.append(deepcopy(child))


class SystemBuilder(object):
  """Factory for BenchmarkSystem, Orchestrator, BenchmarkRunner, etc.

  This class uses a config file to allow the components to be configured on
  creation.
  """
  __metaclass__ = TypecheckMeta

  COMPONENTS = {
    RobotBackend: {
      "tnt": TnTRobotBackend,
      "fake": FakeRobotBackend
    },
    HighSpeedCamera: {
      "phantom": PhantomCamera,
      "fake": FakeHighSpeedCamera
    },
    Updater: {
      "chrome": ChromeUpdater,
      "manual": ManualUpdater,
      "fake": FakeUpdater,
    },
    Navigator: {
      "robot": RobotNavigator,
      "web_adb": WebADBNavigator,
      "native_adb": NativeADBNavigator
    },
    VideoProcessor: {
      "multithreaded": MultithreadedVideoProcessor,
      "singlethreaded": SinglethreadedVideoProcessor,
      "default": MultithreadedVideoProcessor
    },
    Dashboard: {
      "chrome": Dashboard,
      "default": Dashboard
    },
    Orchestrator: {
      "default": Orchestrator
    }
  }

  def __init__(self, config_element, root_dir):
    """Initialize all components from the configuration in config_element.

    :type config_element: ElementTree.Element
    """
    self._root_dir = root_dir
    self._subject_types = self._ReadTypes(config_element, "subject-type")
    self._dut_types = self._ReadTypes(config_element, "dut-type")
    self._config_element = config_element

  @const_property
  def benchmark_system(self):
    element = GetRequired(self._config_element, "benchmark-system")
    system = self._BuildBenchmarkSystem(element)
    for dut_elem in self._config_element.iter("dut"):
      for subject in self._BuildDUTSubjects(dut_elem, system):
        system.subjects[subject.name] = subject
    return system

  @const_property
  def video_processor(self):
    element = self._config_element.find("video-processor")
    return self._CreateComponent(VideoProcessor, element, {})

  @const_property
  def benchmark_runner(self):
    return BenchmarkRunner(self.benchmark_system, self.video_processor)

  @const_property
  def dashboard(self):
    element = self._config_element.find("dashboard")
    return self._CreateComponent(Dashboard, element, {})

  @const_property
  def orchestrator(self):
    element = self._config_element.find("orchestrator")
    return self._CreateComponent(Orchestrator, element, {},
                                 self.benchmark_system, self.benchmark_runner,
                                 self.dashboard)

  @classmethod
  def FromFile(cls, config_file):
    """Initialize with config loaded from config_file."""
    root_dir = os.path.dirname(config_file)
    return cls(ElementTree.parse(config_file).getroot(), root_dir)

  @classmethod
  def FromString(cls, config_string):
    """Initialize with config from config_string."""
    return cls(ElementTree.fromstring(config_string), ".")

  def _BuildBenchmarkSystem(self, system_element):
    """Builds a BenchmarkSystem instance."""
    backend_element = GetRequired(system_element, "backend")
    backend = self._CreateComponent(RobotBackend, backend_element, dict())

    camera_element = GetRequired(system_element, "camera")
    camera = self._CreateComponent(HighSpeedCamera, camera_element, dict())

    system = BenchmarkSystem(backend, camera)

    finger_calib = system_element.find("finger-calibration")
    if finger_calib is not None:
      down = float(finger_calib.get("down-delay", 0.0))
      up = float(finger_calib.get("up-delay", 0.0))
      system.finger_calib_delay = FingerCalibDelay(down, up)

    calib_elem = system_element.find("led-calibration-subject")
    if calib_elem is not None:
      backend_name = calib_elem.get("backend-name", "calibration")
      dut_backend = system.backend.GetDUTBackend(backend_name)
      subject = BenchmarkSubject("calibration", dut_backend, system.camera)
      system.led_calibration_subject = subject
    return system

  def _BuildDUTSubjects(self, dut_elem, system):
    """Builds all BenchmarkSubject of a DUT from config."""
    self._InheritFromType(dut_elem, self._dut_types)

    dut_name = dut_elem.attrib["name"]

    backend_name = dut_elem.get("backend-name", dut_name)
    dut_backend = system.backend.GetDUTBackend(backend_name)

    for subject_elem in dut_elem.iter("subject"):
      yield self._BuildSubject(subject_elem, dut_elem, dut_backend, system)

  def _BuildSubject(self, subject_elem, dut_elem, dut_backend, system):
    """Builds BenchmarkSubject instance from config."""
    self._InheritFromType(subject_elem, self._subject_types)

    subject_name = subject_elem.attrib["name"]
    dut_name = dut_elem.attrib["name"]

    additional = dut_elem.attrib.copy()
    additional.update(subject_elem.attrib)

    navigator = self._CreateComponent(Navigator, subject_elem.find("navigator"),
                                      additional, dut_backend)
    updater = self._CreateComponent(Updater, subject_elem.find("updater"),
                                    additional, dut_backend)
    name = "%s/%s" % (dut_name, subject_name)
    subject = BenchmarkSubject(name, dut_backend, system.camera)
    subject.navigator = navigator
    subject.updater = updater
    return subject

  def _ReadTypes(self, root, element_name):
    """Puts all elements of element_name in a dict with type-name as a key.

    :type root: ElementTree.Element
    :type element_name: str
    :rtype Dict[str, ElementTree.Element]
    """
    type_dict = {}
    for type_elem in root.iter(element_name):
      type_name = type_elem.attrib["type-name"]
      type_dict[type_name] = type_elem
    return type_dict

  def _InheritFromType(self, element, types):
    """Inherit attributes and children from type.

    An element with a type="" attribute will inherit all attributes and children
    from the matching element in the types dictionary.
    Inheritance can be hierarchical when the type itself specifies a parent-type
    attribute.

    :type element: ElementTree.Element
    :type types: Dict[str, ElementTree.Element]
    """
    def BuildTypeHierarchy(type_element, parent_field_name):
      parent_name = type_element.get(parent_field_name)
      if parent_name:
        parent_element = types.get(parent_name)
        if parent_element is None:
          raise Exception("Unknown type %s" % parent_name)
        return [parent_element] + BuildTypeHierarchy(parent_element,
                                                     "parent-type")
      else:
        return []

    hierarchy = BuildTypeHierarchy(element, "type")
    for type_element in hierarchy:
      MergeElement(element, type_element)

    # Remove attributes used for inheritance
    remove_keys = ("type", "type-name", "parent-type")
    element.attrib = dict((k, v) for k, v in element.attrib.items()
                                 if k not in remove_keys)

  def _GetElementAttribs(self, element, additional):
    """Collects attributes and children attributes of an element.

    :type element: ElementTree.Element
    :rtype Tuple[Dict[str, str], List[(str, Dict[str, str])]]
    """
    attrib = additional.copy() if additional else dict()
    attrib.update(element.attrib)
    children = []
    for child in element:
      child_attrib = {k: self._ParseValue(v)
                      for k, v in child.attrib.iteritems()}
      children.append((child.tag, child_attrib))
    attrib = {k: self._ParseValue(v) for k, v in attrib.iteritems()}
    return attrib, children

  def _ParseValue(self, value):
    if value.startswith("file:"):
      value = value[len("file:"):]
      return os.path.join(self._root_dir, value)
    if value.startswith("filecontents:"):
      filename = value[len("filecontents:"):]
      path = os.path.join(self._root_dir, filename)
      with open(path, "r") as file_obj:
        return file_obj.read()
    return value

  def _CreateComponent(self, interface_type, element, additional, *extra_args):
    """Create instance of interface_type with config from element.

    The type attribute specified in the elment will pick the implementation to
    use from the COMPONENTS dictionary. The implementation will be created via
    it's FromConfig method.

    :type interface_type: type
    :type element: Optional[ElementTree.Element]
    :param Dict[str, str] additional: Additional attributes
    :param List[Any] extra_args: Extra arguments passes to FromConfig.
    """
    if element is None:
      if "default" in self.COMPONENTS[interface_type]:
        attrib, children = {}, []
      else:
        return None
    else:
      attrib, children = self._GetElementAttribs(element, additional)
    type_name = attrib.get("type") or "default"

    available = self.COMPONENTS[interface_type]
    if type_name not in available:
      raise Exception("Invalid type '%s' for interface '%s'" %
                      (type_name, interface_type))
    impl_type = available[type_name]
    return impl_type.FromConfig(attrib, children, *extra_args)

  def _ParseCoord(self, string):
    if string:
      match = re.match("\(\s*([0-9.]+)\s*\,\s*([0-9.]+)\)", string)
      return float(match.group(1)), float(match.group(2))
    return (0.0, 0.0)

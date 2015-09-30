# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Implementation of the BenchmarkSystem class."""

from copy import deepcopy
import cPickle as pickle
import json
import logging
import logging.config
import os
import re
import xml.etree.ElementTree as ElementTree

from safetynet import (Any, Dict, List, Optional, Tuple, TypecheckMeta,
                       typecheck)

from .benchmark import BenchmarkRunner
from .components import COMPONENTS
from .detection import VideoProcessor
from .orchestrator import (Access, Collector, Dashboard, Orchestrator,
                           OrchestratorSubject, SubjectSetup, Updater)
from .system import (BenchmarkSubject, BenchmarkSystem, HighSpeedCamera,
                     Navigator, RobotBackend)
from .system.system import FingerCalibDelay
from .util import CreateComponent, const_property


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
def MergeElement(base, merging, merge_tags=[]):
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

    if child_name or child.tag in merge_tags:
      for candidate in base.iter(child.tag):
        if candidate.get("name") == child_name or child.tag in merge_tags:
          existing_child = candidate
          break

    if existing_child is not None:
      MergeElement(existing_child, child, merge_tags)
    else:
      base.append(deepcopy(child))


class SystemBuilder(object):
  """Factory for BenchmarkSystem, Orchestrator, BenchmarkRunner, etc.

  This class uses a config file to allow the components to be configured on
  creation.
  """
  __metaclass__ = TypecheckMeta

  def __init__(self, config_element, root_dir, options):
    """Initialize all components from the configuration in config_element.

    :type config_element: ElementTree.Element
    """
    self._root_dir = root_dir
    self._ParseIncludes(config_element)
    self._subject_types = self._ReadTypes(config_element, "subject-type")
    self._dut_types = self._ReadTypes(config_element, "dut-type")
    self._config_element = config_element
    self._options = options
    self.attrib = config_element.attrib
    self._state_file = self.ParseValue(config_element.get("state-file"))
    self._SetupLogging()

  @const_property
  def benchmark_system(self):
    element = GetRequired(self._config_element, "benchmark-system")
    return self._BuildBenchmarkSystem(element)

  @const_property
  def video_processor(self):
    element = self._config_element.find("video-processor")
    return self._CreateComponent(VideoProcessor, element, self.attrib)

  @const_property
  def benchmark_runner(self):
    element = self._config_element.find("benchmark-runner")
    return self._CreateComponent(BenchmarkRunner, element, self.attrib,
                                 self.benchmark_system, self.video_processor)

  @const_property
  def orchestrator(self):
    element = self._config_element.find("orchestrator")
    orchestrator = self._CreateComponent(Orchestrator, element, self.attrib,
        self.benchmark_system, self.benchmark_runner)
    for dut_elem in self._config_element.iter("dut"):
      for subject in self._BuildDUTSubjects(dut_elem, self.benchmark_system):
        orchestrator.AddSubject(subject)
    return orchestrator

  @classmethod
  def FromFile(cls, config_file, options):
    """Initialize with config loaded from config_file."""
    root_dir = os.path.dirname(config_file)
    return cls(ElementTree.parse(config_file).getroot(), root_dir, options)

  @classmethod
  def FromString(cls, config_string, root_dir=".", options=object()):
    """Initialize with config from config_string."""
    return cls(ElementTree.fromstring(config_string), root_dir, options)

  def SaveState(self):
    """Save current state to file.

    This mostly includes locations of buttons and icons on devices.
    :param str state_file: File to save into.
    """
    if not self._state_file:
      return
    state = {"orchestrator": self.orchestrator.state}
    pickle.dump(state, open(self._state_file, "w"), protocol=-1)

  def LoadState(self):
    """Load state from file.

    This mostly includes locations of buttons and icons on devices.
    """
    if not self._state_file or not os.path.exists(self._state_file):
      return
    state = pickle.load(open(self._state_file, "r"))
    if "orchestrator" in state:
      self.orchestrator.state = state["orchestrator"]

  def _SetupLogging(self):
    log_config_file = self.ParseValue(self._config_element.get("log-config"))
    if log_config_file:
      with open(log_config_file, "r") as file_obj:
        log_dir = os.path.join(self._root_dir, "..", "logs")
        if not os.path.exists(log_dir):
          os.mkdir(log_dir)
        log_config = file_obj.read()
        log_config = log_config.replace("%LOG_DIR%", log_dir)
        dictionary = json.loads(log_config)
      logging.config.dictConfig(dictionary)
    else:
      logging.basicConfig(level=logging.INFO)
    logging.captureWarnings(True)

  def _ParseIncludes(self, config_element):
    for index, child in enumerate(list(config_element)):
      if child.tag != "include":
        continue
      filename = os.path.join(self._root_dir, child.attrib["file"])
      included = ElementTree.parse(filename).getroot()
      self._ParseIncludes(included)
      for included_element in included:
        config_element.append(included_element)
      config_element.attrib.update(included.attrib)

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

    context = dut_elem.attrib.copy()
    context.update(subject_elem.attrib)
    context["dut_name"] = dut_name
    context["subject_name"] = subject_name

    name = "%s/%s" % (dut_name, subject_name)
    navigator = self._CreateComponent(Navigator, subject_elem.find("navigator"),
                                      context, dut_backend)
    updater = self._CreateComponent(Updater, subject_elem.find("updater"),
                                    context)
    dashboard = self._CreateComponent(Dashboard, subject_elem.find("dashboard"),
                                      context, name)
    access = self._CreateComponent(Access, subject_elem.find("access"), context)

    subject = OrchestratorSubject(name, dut_backend, system.camera)
    subject.navigator = navigator
    subject.updater = updater
    subject.dashboard = dashboard
    subject.access = access

    for setup_elem in subject_elem.iter("setup"):
      setup = self._CreateComponent(SubjectSetup, setup_elem, context)
      subject.setups.append(setup)

    for setup_elem in subject_elem.iter("collector"):
      setup = self._CreateComponent(Collector, setup_elem, context)
      subject.collectors.append(setup)

    margin_attrib = subject_elem.get("margin")
    if margin_attrib:
      margin_attrib = self.ParseValue(margin_attrib, dut_elem.attrib)
      subject.margin = self._ParseCoord(margin_attrib)

    exposure = self.ParseValue(subject_elem.get("exposure"), dut_elem.attrib)
    if exposure:
      subject.exposure = float(exposure)

    subject.adb = self.ParseValue(dut_elem.get("adb"))

    test_plane = self.ParseValue(subject_elem.get("test-plane"),
                                  dut_elem.attrib)
    if test_plane:
      subject.test_plane_location = float(test_plane)


    if margin_attrib:
      margin_attrib = self.ParseValue(margin_attrib, context)
      subject.margin = self._ParseCoord(margin_attrib)

    for benchmark_elem in subject_elem.iter("benchmark"):
      attrib = {k: self.ParseValue(v)
                for k, v in benchmark_elem.attrib.iteritems()}
      subject.DefineBenchmark(attrib["name"], attrib["type"],
                              attrib["activity"], attrib)
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
      MergeElement(element, type_element, ["navigator", "updater", "dashboard"])

    # Remove attributes used for inheritance
    remove_keys = ("type", "type-name", "parent-type")
    element.attrib = dict((k, v) for k, v in element.attrib.items()
                                 if k not in remove_keys)

  def ParseValue(self, value, context=dict()):
    if value is None:
      return value

    if value.startswith("file:"):
      value = value[len("file:"):]
      return os.path.join(self._root_dir, value)
    if value.startswith("filecontents:"):
      filename = value[len("filecontents:"):]
      path = os.path.join(self._root_dir, filename)
      with open(path, "r") as file_obj:
        return file_obj.read()
    if value.startswith("option:"):
      option_name = value[len("option:"):]
      return str(getattr(self._options, option_name))
    if value.startswith("env:"):
      env_name = value[len("env:"):]
      return str(os.environ[env_name])
    if "{" in value and "}" in value:
      try:
        value = value.format(**context)
        value = self.ParseValue(value)
      except KeyError:
        return None
    return value

  def _CreateComponent(self, interface_type, element, context, *extra_args):
    """Create instance of interface_type with config from element.

    The type attribute specified in the elment will pick the implementation to
    use from the COMPONENTS dictionary. The implementation will be created via
    it's FromConfig method.

    :type interface_type: type
    :type element: Optional[ElementTree.Element]
    :param Dict[str, str] context: Additional attributes
    :param List[Any] extra_args: Extra arguments passes to FromConfig.
    """
    if element is None:
      if "default" in COMPONENTS[interface_type]:
        type_name = "default"
      else:
        return None
    else:
      type_name = element.attrib.get("type", "default")

    available_types = COMPONENTS[interface_type]
    if type_name not in available_types:
      raise Exception("Invalid type '%s' for interface '%s'" %
                      (type_name, interface_type))
    impl_type = available_types[type_name]
    value_filter = lambda v: self.ParseValue(v, context)
    return CreateComponent(impl_type, element, extra_args, value_filter)

  def _ParseCoord(self, string):
    if string:
      match = re.match("\(\s*([0-9.]+)\s*\,\s*([0-9.]+)\)", string)
      return float(match.group(1)), float(match.group(2))
    return (0.0, 0.0)

# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Unit tests for SystemBuilder"""

from collections import namedtuple
from tempfile import NamedTemporaryFile
import unittest
import xml.etree.ElementTree as ElementTree

from optofidelity.builder import MergeElement, SystemBuilder


simple_config = """\
<config>
  <benchmark-system>
    <backend type="fake" />
    <camera type="fake" />
  </benchmark-system>
  <orchestrator results="" />

  <dut name="test_dut">
    <subject name="test_subject">
      <navigator type="fake" />
      <updater type="fake" />
    </subject>
  </dut>
</config>
"""

subject_type_config = """\
<config>
  <benchmark-system>
    <backend type="fake" />
    <camera type="fake" />
  </benchmark-system>
  <orchestrator results="" />

  <subject-type type-name="test_subject_type">
    <updater type="fake" />
  </subject-type>

  <dut name="test_dut">
    <subject name="test_subject" type="test_subject_type">
      <navigator type="fake" />
    </subject>
  </dut>
</config>
"""

inheritance_config = """\
<config>
  <benchmark-system>
    <backend type="fake" />
    <camera type="fake" />
  </benchmark-system>
  <orchestrator results="" />

  <subject-type type-name="test_subject_base">
    <navigator type="fake" />
  </subject-type>

  <subject-type type-name="test_subject_type" parent-type="test_subject_base">
    <updater type="fake" />
  </subject-type>

  <dut name="test_dut">
    <subject name="test_subject" type="test_subject_type" />
  </dut>
</config>
"""

dut_type_config = """\
<config>
  <benchmark-system>
    <backend type="fake" />
    <camera type="fake" />
  </benchmark-system>
  <orchestrator results="" />

  <dut-type type-name="test_dut_type">
    <subject name="test_subject">
      <navigator type="fake" />
      <updater type="fake" />
    </subject>
  </dut-type>

  <dut name="test_dut" type="test_dut_type" />
</config>
"""

dut_attrib_inheritance_config = """\
<config>
  <benchmark-system>
    <backend type="fake" />
    <camera type="fake" />
  </benchmark-system>
  <orchestrator results="" />

  <dut name="test_dut" version="42.0">
    <subject name="test_subject">
      <navigator type="fake" />
      <updater type="manual" version="{dut.version}" />
    </subject>
  </dut>
</config>
"""

attrib_inheritance_config = """\
<config>
  <benchmark-system>
    <backend type="fake" />
    <camera type="fake" />
  </benchmark-system>
  <orchestrator results="" />

  <subject-type type-name="test_subject_base">
    <navigator type="fake" />
    <updater type="manual" />
  </subject-type>

  <subject-type type-name="test_subject_type" parent-type="test_subject_base">
    <updater version="42.0" />
  </subject-type>

  <dut name="test_dut">
    <subject name="test_subject" type="test_subject_type" />
  </dut>
</config>
"""

class SystemBuilderTest(unittest.TestCase):
  def testAttribMerging(self):
    base = ElementTree.fromstring("<test a='1' />")
    merging = ElementTree.fromstring("<test a='3' b='2' />")
    MergeElement(base, merging)
    expected = dict(a="1", b="2")
    self.assertEqual(base.attrib, expected)

  def testNamedChildrenMerging(self):
    base = ElementTree.fromstring(
        "<test><a name='test' a='1' /><b a='2' /></test>")
    merging = ElementTree.fromstring(
        "<test><a name='test' a='3' /><b a='4' /></test>")

    MergeElement(base, merging)
    self.assertEqual(len(list(base.iter("a"))), 1)
    self.assertEqual(len(list(base.iter("b"))), 2)
    self.assertEqual(base.find("a").attrib["a"], '1')

  def testNestedMerging(self):
    base = ElementTree.fromstring(
        "<test><a name='test' a='1'><b a='2' /></a></test>")
    merging = ElementTree.fromstring(
        "<test><a name='test' a='3'><b a='4' /></a></test>")

    MergeElement(base, merging)
    self.assertEqual(len(list(base.iter("a"))), 1)
    self.assertEqual(len(list(base.find("a").iter("b"))), 2)

  def testParseValue(self):
    options = namedtuple("options", ("test"))
    builder = SystemBuilder.FromString("<config />", "root", options("42"))
    def Parse(string, context=dict()):
      return builder.ParseValue(string, context)

    self.assertEqual(Parse("file:rel_path"), "root/rel_path")
    with NamedTemporaryFile() as tempfile:
      tempfile.write("42")
      tempfile.flush()
      self.assertEqual(Parse("filecontents:" + tempfile.name), "42")

    self.assertEqual(Parse("option:test"), "42")
    self.assertEqual(Parse("{test}", dict(test="42")), "42")
    self.assertEqual(Parse("42"), "42")

  def testSimpleConfig(self):
    builder = SystemBuilder.FromString(simple_config)
    self.assertSimpleConfig(builder)

  def testSubjectTypeConfig(self):
    builder = SystemBuilder.FromString(subject_type_config)
    self.assertSimpleConfig(builder)

  def testInheritanceConfig(self):
    builder = SystemBuilder.FromString(inheritance_config)
    self.assertSimpleConfig(builder)

  def testDUTTypeConfig(self):
    builder = SystemBuilder.FromString(dut_type_config)
    self.assertSimpleConfig(builder)

  def testDUTInheritanceConfig(self):
    builder = SystemBuilder.FromString(dut_attrib_inheritance_config)
    self.assertSimpleConfig(builder)
    subjects = builder.orchestrator._subjects
    updater = subjects.values()[0].updater
    self.assertEqual(updater.installed_version, "42.0")

  def testAttribInheritanceConfig(self):
    builder = SystemBuilder.FromString(attrib_inheritance_config)
    self.assertSimpleConfig(builder)
    subjects = builder.orchestrator._subjects
    updater = subjects.values()[0].updater
    self.assertEqual(updater.installed_version, "42.0")

  def testIncludeConfig(self):
    with NamedTemporaryFile() as tempfile:
      tempfile.write(simple_config)
      tempfile.flush()

      include_config = "<config><include file='%s' /></config>" % tempfile.name
      builder = SystemBuilder.FromString(include_config)
      self.assertSimpleConfig(builder)

  def testStateSavingAndLoading(self):
    with NamedTemporaryFile() as tempfile:
      builder = SystemBuilder.FromString(simple_config)
      builder._state_file = tempfile.name
      builder.orchestrator
      builder.SaveState()
      builder.LoadState()

  def assertSimpleConfig(self, builder):
    system = builder.benchmark_system
    self.assertIsNotNone(system.backend)
    self.assertIsNotNone(system.camera)

    subject = builder.orchestrator._subjects["test_dut/test_subject"]
    self.assertIsNotNone(subject)


system_config = """\
<config>
  <benchmark-system>
    <backend type="fake" />
    <camera type="fake" />
    <finger-calibration down-delay="42.0" up-delay="23.0" />
    <led-calibration-subject backend-name="calibration" />
  </benchmark-system>
</config>
"""

subject_config = """\
<config>
  <benchmark-system>
    <backend type="fake" />
    <camera type="fake" />
  </benchmark-system>
  <orchestrator results="" />

  <dut name="test_dut">
    <subject name="test_subject" margin="(42.0, 23.0)" exposure="42.0"
             test-plane="0.5">
      <navigator type="fake" />
      <updater type="fake" />
      <setup type="fake" />
      <benchmark name="name" type="type" activity="activity" />
    </subject>
  </dut>
</config>
"""

class ComponentConfigTests(unittest.TestCase):
  def testBenchmarkSystemConfig(self):
    builder = SystemBuilder.FromString(system_config)
    system = builder.benchmark_system

    self.assertIsNotNone(system.led_calibration_subject)
    self.assertEqual(system.led_calibration_subject.name, "calibration")

    self.assertEqual(system.finger_calib_delay, (42.0, 23.0))

  def testSubjectConfig(self):
    builder = SystemBuilder.FromString(subject_config)
    subject = builder.orchestrator._subjects["test_dut/test_subject"]

    self.assertIsNotNone(subject.navigator)
    self.assertIsNotNone(subject.updater)
    self.assertEqual(len(subject.setups), 1)
    self.assertEqual(subject.margin, (42.0, 23.0))
    self.assertEqual(subject.test_plane, subject.width * 0.5)

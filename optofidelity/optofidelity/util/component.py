# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import xml.etree.ElementTree as ElementTree

def CreateComponent(type_, element, extra_args=[], value_filter=None):
  """Create instance of type_ with config from element.

  :param type type_: Type instance to create. Must have a FromConfig method.
  :type element: Optional[ElementTree.Element]
  :param List[Any] extra_args: Extra arguments passes to FromConfig.
  :param value_filter: Method called to parse all config values.
  """
  if value_filter is None:
    value_filter = lambda v: v
  children = []
  attrib = {}
  if element is not None:
    for child in element:
      child_attrib = {k: value_filter(v) for k, v in child.attrib.iteritems()}
      children.append((child.tag, child_attrib))
    attrib = {k: value_filter(v) for k, v in element.attrib.iteritems()}
  return type_.FromConfig(attrib, children, *extra_args)


def CreateComponentFromXML(type_, xml_source, extra_args=[], value_filter=None):
  element = ElementTree.fromstring(xml_source)
  return CreateComponent(type_, element, extra_args, value_filter)

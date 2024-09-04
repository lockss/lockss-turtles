#!/usr/bin/env python3

# Copyright (c) 2000-2024, Board of Trustees of Leland Stanford Jr. University
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors
# may be used to endorse or promote products derived from this software without
# specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import importlib.resources
import io
import json
import re
import unittest

import jsonschema
import yaml

import lockss.turtles.resources
from lockss.turtles.plugin_set import PluginSet


class TestPluginSetSchema(unittest.TestCase):

    def setUp(self):
        with importlib.resources.path(lockss.turtles.resources, PluginSet.PLUGIN_SET_SCHEMA).open('r') as f:
            self.schema = json.load(f)

    def test_invalid_kind(self):
        self.assertRaisesRegex(jsonschema.ValidationError,
                               re.compile(r'''^'PluginSet' was expected'''),
                               jsonschema.validate,
                               yaml.safe_load(io.StringIO('''\
---
kind: InvalidKind
id: myid
name: My Name
builder: {}
''')),
                               self.schema)

    def test_no_id(self):
        self.assertRaisesRegex(jsonschema.ValidationError,
                               re.compile(r'''^'id' is a required property'''),
                               jsonschema.validate,
                               yaml.safe_load(io.StringIO('''\
---
kind: PluginSet
# id intentionally omitted
name: My Name
builder: {}
''')),
                               self.schema)

    def test_no_name(self):
        self.assertRaisesRegex(jsonschema.ValidationError,
                               re.compile(r'''^'name' is a required property'''),
                               jsonschema.validate,
                               yaml.safe_load(io.StringIO('''\
---
kind: PluginSet
id: myid
# name intentionally omitted
builder: {}
''')),
                               self.schema)

    def test_no_builder(self):
        self.assertRaisesRegex(jsonschema.ValidationError,
                               re.compile(r'''^'builder' is a required property'''),
                               jsonschema.validate,
                               yaml.safe_load(io.StringIO('''\
---
kind: PluginSet
id: myid
name: My Name
# builder intentionally omitted
''')),
                               self.schema)

    def test_no_builder_type(self):
        self.assertRaisesRegex(jsonschema.ValidationError,
                               re.compile(r'''^'type' is a required property'''),
                               jsonschema.validate,
                               yaml.safe_load(io.StringIO('''\
---
kind: PluginSet
id: myid
name: My Name
builder: {}
''')),
                               self.schema)

    def test_builder_type_enum(self):
        for typ in ['ant', 'mvn']:
            jsonschema.validate(yaml.safe_load(io.StringIO(f'''\
---
kind: PluginSet
id: myid
name: My Name
builder:
  type: {typ}
''')),
                                self.schema)

    def test_invalid_builder_type(self):
        self.assertRaisesRegex(jsonschema.ValidationError,
                               re.compile(r'''^'invalidtype' is not one of \['ant', 'mvn'\]'''),
                               jsonschema.validate,
                               yaml.safe_load(io.StringIO('''\
---
kind: PluginSet
id: myid
name: My Name
builder:
  type: invalidtype
''')),
                               self.schema)


if __name__ == '__main__':
    unittest.main()

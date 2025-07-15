#!/usr/bin/env python3

# Copyright (c) 2000-2025, Board of Trustees of Leland Stanford Jr. University
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

from . import PydanticTestCase
from lockss.turtles.plugin_set import AntPluginSetBuilder, MavenPluginSetBuilder, PluginSet, PluginSetBuilder


class TestPluginSet(PydanticTestCase):

    def setUp(self):
        pass

    def testPluginSet(self):
        self.assertPydanticMissing(lambda: PluginSet(), 'kind')
        self.assertPydanticLiteralError(lambda: PluginSet(kind='WrongKind'), 'kind', 'PluginSet')
        self.assertPydanticMissing(lambda: PluginSet(kind='PluginSet'), 'id')
        self.assertPydanticMissing(lambda: PluginSet(kind='PluginSet', id='myid'), 'name')
        self.assertPydanticMissing(lambda: PluginSet(kind='PluginSet', id='myset', name='My Set'), 'builder')
        PluginSet(kind='PluginSet', id='myset', name='My Set', builder=AntPluginSetBuilder(type='ant'))
        PluginSet(kind='PluginSet', id='myset', name='My Set', builder=MavenPluginSetBuilder(type='maven'))

class TestPluginSetBuilder(PydanticTestCase):

    def doTestPluginSetBuilder(self, Pbsc: type(PluginSetBuilder), typ: str, def_main: str, def_test: str) -> None:
        self.assertPydanticMissing(lambda: Pbsc(), 'type')
        self.assertPydanticLiteralError(lambda: Pbsc(type='BADTYPE'), 'type', typ)
        self.assertIsNone(Pbsc(type=typ)._root)
        self.assertEqual(Pbsc(type=typ)._get_main(), def_main)
        self.assertEqual(Pbsc(type=typ, main='mymain')._get_main(), 'mymain')
        self.assertEqual(Pbsc(type=typ)._get_test(), def_test)
        self.assertEqual(Pbsc(type=typ, test='mytest')._get_test(), 'mytest')

    def testPluginSetBuilder(self):
        self.doTestPluginSetBuilder(AntPluginSetBuilder, 'ant', 'plugins/src', 'plugins/test/src')
        self.doTestPluginSetBuilder(MavenPluginSetBuilder, 'maven', 'src/main/java', 'src/test/java')

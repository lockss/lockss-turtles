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

from pathlib import Path

from . import PydanticTestCase
from lockss.turtles.plugin_set import AntPluginSetBuilder, MavenPluginSetBuilder, PluginSet, PluginSetBuilder, PluginSetBuilderType


ROOT: Path = Path('.').absolute()


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

    def doTestPluginSetBuilder(self, Pbsc: type(PluginSetBuilder), typ: PluginSetBuilderType, def_main: Path, def_test: Path) -> None:
        self.assertPydanticMissing(lambda: Pbsc(), 'type')
        self.assertPydanticLiteralError(lambda: Pbsc(type='BADTYPE'), 'type', typ)
        self.assertIsNone(Pbsc(type=typ)._root)
        with self.assertRaises(ValueError):
            Pbsc(type=typ).get_root()
        self.assertEqual(Pbsc(type=typ).initialize(ROOT).get_root(), ROOT)
        with self.assertRaises(ValueError):
            Pbsc(type=typ, main='anything').get_main()
        self.assertEqual(Pbsc(type=typ).initialize(ROOT).get_main(), def_main)
        self.assertEqual(Pbsc(type=typ, main='mymain').initialize(ROOT).get_main(), ROOT.joinpath('mymain'))
        self.assertEqual(Pbsc(type=typ, main='/opt/main').initialize(ROOT).get_main(), Path('/opt/main'))
        with self.assertRaises(ValueError):
            Pbsc(type=typ, test='anything').get_test()
        self.assertEqual(Pbsc(type=typ).initialize(ROOT).get_test(), def_test)
        self.assertEqual(Pbsc(type=typ, test='mytest').initialize(ROOT).get_test(), ROOT.joinpath('mytest'))
        self.assertEqual(Pbsc(type=typ, test='/opt/test').initialize(ROOT).get_test(), Path('/opt/test'))

    def testPluginSetBuilder(self):
        self.doTestPluginSetBuilder(AntPluginSetBuilder, 'ant', ROOT.joinpath('plugins/src'), ROOT.joinpath('plugins/test/src'))
        self.doTestPluginSetBuilder(MavenPluginSetBuilder, 'maven', ROOT.joinpath('src/main/java'), ROOT.joinpath('src/test/java'))

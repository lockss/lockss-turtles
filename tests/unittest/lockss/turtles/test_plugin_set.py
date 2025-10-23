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

# Remove in Python 3.14
# See https://stackoverflow.com/questions/33533148/how-do-i-type-hint-a-method-with-the-type-of-the-enclosing-class/33533514#33533514
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from . import PydanticTestCase, ROOT
from lockss.turtles.plugin_set import AntPluginSetBuilder, BasePluginSetBuilder, MavenPluginSetBuilder, PluginSet, PluginSetBuilderType, PluginSetCatalog


class TestPluginSetCatalog(PydanticTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.valid_absolute = PluginSetCatalog(**{'kind': 'PluginSetCatalog',
                                                  'plugin-set-files': [
                                                      '/tmp/one.yaml'
                                                  ]}).initialize(ROOT)
        self.valid_relative = PluginSetCatalog(**{'kind': 'PluginSetCatalog',
                                                  'plugin-set-files': [
                                                      'one.yaml'
                                                  ]}).initialize(ROOT)
        self.valid = [self.valid_absolute, self.valid_relative]

    def test_missing_kind(self) -> None:
        self.assertPydanticMissing(lambda: PluginSetCatalog(),
                                   'kind')

    def test_null_kind(self) -> None:
        self.assertPydanticLiteralError(lambda: PluginSetCatalog(kind=None),
                                        'kind',
                                        'PluginSetCatalog')

    def test_wrong_kind(self) -> None:
        self.assertPydanticLiteralError(lambda: PluginSetCatalog(kind='WrongKind'),
                                        'kind',
                                        'PluginSetCatalog')

    def test_missing_plugin_registry_files(self) -> None:
        self.assertPydanticMissing(lambda: PluginSetCatalog(),
                                   'plugin-set-files')

    def test_null_plugin_registry_files(self) -> None:
        self.assertPydanticListType(lambda: PluginSetCatalog(**{'plugin-set-files': None}),
                                    'plugin-set-files')

    def test_empty_plugin_registry_files(self) -> None:
        self.assertPydanticTooShort(lambda: PluginSetCatalog(**{'plugin-set-files': []}),
                                    'plugin-set-files')

    def test_uninitialized(self) -> None:
        psc = PluginSetCatalog(**{'kind': 'PluginSetCatalog',
                                  'plugin-set-files': ['whatever']})
        self.assertRaises(ValueError, lambda: psc.get_root())
        self.assertRaises(ValueError, lambda: psc.get_plugin_set_files())

    def test_kind(self) -> None:
        for valid in self.valid:
            self.assertEqual(valid.kind, 'PluginSetCatalog')

    def test_get_plugin_set_files(self) -> None:
        self.assertListEqual(self.valid_absolute.get_plugin_set_files(),
                             [Path('/tmp/one.yaml')])
        self.assertListEqual(self.valid_relative.get_plugin_set_files(),
                             [ROOT.joinpath('one.yaml')])


# Important: see "del _BasePluginSetBuilderTestCase" at the end
class _BasePluginSetBuilderTestCase(ABC, PydanticTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.valid_absolute = self.instance(type=self.type(),
                                            main='/tmp/maindir',
                                            test='/tmp/testdir').initialize(ROOT)
        self.valid_relative = self.instance(type=self.type(),
                                            main='maindir',
                                            test='testdir').initialize(ROOT)
        self.valid = [self.valid_absolute, self.valid_relative]

    @abstractmethod
    def instance(self, **kwargs) -> BasePluginSetBuilder:
        pass

    @abstractmethod
    def type(self) -> PluginSetBuilderType:
        pass

    @abstractmethod
    def default_main(self) -> str:
        pass

    @abstractmethod
    def default_test(self) -> str:
        pass

    def test_missing_type(self) -> None:
        self.assertPydanticMissing(lambda: self.instance(),
                                   'type')

    def test_null_type(self) -> None:
        self.assertPydanticLiteralError(lambda: self.instance(type=None),
                                       'type',
                                        self.type())

    def test_default_main(self) -> None:
        self.assertEqual(getattr(self.instance(type=self.type()), '_get_main')(),
                         self.default_main())

    def test_null_main(self) -> None:
        self.assertPydanticStringType(lambda: self.instance(main=None),
                                      'main')

    def test_default_test(self) -> None:
        self.assertEqual(getattr(self.instance(type=self.type()), '_get_test')(),
                         self.default_test())

    def test_null_test(self) -> None:
        self.assertPydanticStringType(lambda: self.instance(test=None),
                                      'test')

    def test_uninitialized(self) -> None:
        psb = self.instance(type=self.type(),
                            main='mainpath',
                            test='testpath')
        self.assertRaises(ValueError, lambda: psb.get_root())
        self.assertRaises(ValueError, lambda: psb.get_main())
        self.assertRaises(ValueError, lambda: psb.get_test())

    def test_get_type(self) -> None:
        for valid in self.valid:
            self.assertEqual(valid.get_type(), self.type())

    def test_get_main(self) -> None:
        self.assertEqual(self.valid_absolute.get_main(), Path('/tmp/maindir'))
        self.assertEqual(self.valid_relative.get_main(), ROOT.joinpath('maindir'))

    def test_get_test(self) -> None:
        self.assertEqual(self.valid_absolute.get_test(), Path('/tmp/testdir'))
        self.assertEqual(self.valid_relative.get_test(), ROOT.joinpath('testdir'))

class TestMavenPluginSetBuilder(_BasePluginSetBuilderTestCase):

    def instance(self, **kwargs) -> MavenPluginSetBuilder:
        return MavenPluginSetBuilder(**kwargs)

    def type(self) -> PluginSetBuilderType:
        return 'maven'

    def default_main(self) -> str:
        return 'src/main/java'

    def default_test(self) -> str:
        return 'src/test/java'


class TestAntPluginSetBuilder(_BasePluginSetBuilderTestCase):

    def instance(self, **kwargs) -> AntPluginSetBuilder:
        return AntPluginSetBuilder(**kwargs)

    def type(self) -> PluginSetBuilderType:
        return 'ant'

    def default_main(self) -> str:
        return 'plugins/src'

    def default_test(self) -> str:
        return 'plugins/test/src'


class TestPluginSet(PydanticTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.valid_builder = MavenPluginSetBuilder(type='maven')
        self.valid = PluginSet(kind='PluginSet',
                               id='myid',
                               name='My Name',
                               builder=self.valid_builder).initialize(ROOT)

    def test_missing_kind(self) -> None:
        self.assertPydanticMissing(lambda: PluginSet(),
                                   'kind')

    def test_null_kind(self) -> None:
        self.assertPydanticLiteralError(lambda: PluginSet(kind=None),
                                        'kind',
                                        'PluginSet')

    def test_wrong_kind(self) -> None:
        self.assertPydanticLiteralError(lambda: PluginSet(kind='WrongKind'),
                                        'kind',
                                        'PluginSet')

    def test_missing_identifier(self) -> None:
        self.assertPydanticMissing(lambda: PluginSet(),
                                   'id')

    def test_null_identifier(self) -> None:
        self.assertPydanticStringType(lambda: PluginSet(id=None),
                                      'id')

    def test_missing_name(self) -> None:
        self.assertPydanticMissing(lambda: PluginSet(),
                                   'name')

    def test_null_name(self) -> None:
        self.assertPydanticStringType(lambda: PluginSet(name=None),
                                      'name')

    def test_missing_builder(self) -> None:
        self.assertPydanticMissing(lambda: PluginSet(),
                                   'builder')

    def test_null_builder(self) -> None:
        self.assertPydanticModelAttributesType(lambda: PluginSet(builder=None),
                                               'builder')

    def test_uninitialized(self) -> None:
        ps = PluginSet(kind='PluginSet',
                       id='myid',
                       name='My Name',
                       builder=MavenPluginSetBuilder(type='maven'))
        self.assertRaises(ValueError, lambda: ps.get_builder().get_root())

    def test_kind(self) -> None:
        self.assertEqual(self.valid.kind, 'PluginSet')

    def test_get_id(self) -> None:
        self.assertEqual(self.valid.get_id(), 'myid')

    def test_get_name(self) -> None:
        self.assertEqual(self.valid.get_name(), 'My Name')

    def test_get_builder(self) -> None:
        self.assertEqual(self.valid.get_builder(), self.valid_builder)


#
# See https://stackoverflow.com/a/43353680
#
del _BasePluginSetBuilderTestCase

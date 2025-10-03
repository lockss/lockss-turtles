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

from lockss.turtles.plugin_registry import BasePluginRegistryLayout, DirectoryPluginRegistryLayout, PluginRegistry, PluginRegistryCatalog, PluginRegistryLayer, PluginRegistryLayoutFileNamingConvention, RcsPluginRegistryLayout

from . import PydanticTestCase, ROOT


class TestPluginRegistryCatalog(PydanticTestCase):

    def test_missing_kind(self) -> None:
        self.assertPydanticMissing(lambda: PluginRegistryCatalog(),
                                   'kind')

    def test_null_kind(self) -> None:
        self.assertPydanticLiteralError(lambda: PluginRegistryCatalog(kind=None),
                                        'kind',
                                        'PluginRegistryCatalog')

    def test_wrong_kind(self) -> None:
        self.assertPydanticLiteralError(lambda: PluginRegistryCatalog(kind='WrongKind'),
                                        'kind',
                                        'PluginRegistryCatalog')

    def test_missing_plugin_registry_files(self) -> None:
        self.assertPydanticMissing(lambda: PluginRegistryCatalog(),
                                   'plugin-registry-files')

    def test_null_plugin_registry_files(self) -> None:
        self.assertPydanticListType(lambda: PluginRegistryCatalog(**{'plugin-registry-files': None}),
                                    'plugin-registry-files')

    def test_empty_plugin_registry_files(self) -> None:
        self.assertPydanticTooShort(lambda: PluginRegistryCatalog(**{'plugin-registry-files': []}),
                                    'plugin-registry-files')

    def test_uninitialized(self) -> None:
        prc = PluginRegistryCatalog(**{'kind': 'PluginRegistryCatalog',
                                       'plugin-registry-files': ['whatever']})
        self.assertRaises(ValueError, lambda: prc.get_root())
        self.assertRaises(ValueError, lambda: prc.get_plugin_registry_files())

    def test_absolute_path(self) -> None:
        prc = PluginRegistryCatalog(**{'kind': 'PluginRegistryCatalog',
                                       'plugin-registry-files': ['/tmp/one.yaml']}).initialize(ROOT)
        self.assertEqual(len(prf := prc.get_plugin_registry_files()), 1)
        self.assertEqual(prf[0], Path('/tmp/one.yaml'))

    def test_relative_path(self) -> None:
        prc = PluginRegistryCatalog(**{'kind': 'PluginRegistryCatalog',
                                       'plugin-registry-files': ['one.yaml']}).initialize(ROOT)
        self.assertEqual(len(prf := prc.get_plugin_registry_files()), 1)
        self.assertEqual(prf[0], ROOT.joinpath('one.yaml'))


# Important: see "del _BasePluginRegistryLayoutTestCase" at the end
class _BasePluginRegistryLayoutTestCase(ABC, PydanticTestCase):

    @abstractmethod
    def instance(self, **kwargs) -> BasePluginRegistryLayout:
        pass

    @abstractmethod
    def type(self) -> str:
        pass

    def test_missing_type(self) -> None:
        self.assertPydanticMissing(lambda: self.instance(),
                                   'type')

    def test_null_type(self) -> None:
        self.assertPydanticLiteralError(lambda: self.instance(type=None),
                                       'type',
                                        self.type())

    def test_invalid_type(self) -> None:
        self.assertPydanticLiteralError(lambda: self.instance(type='invalid'),
                                       'type',
                                        self.type())

    def test_missing_file_naming_convention(self) -> None:
        self.assertEqual(self.instance(type=self.type()).get_file_naming_convention(),
                         BasePluginRegistryLayout.FILE_NAMING_CONVENTION_DEFAULT)

    def test_null_file_naming_convention(self) -> None:
        self.assertPydanticLiteralError(lambda: self.instance(**{'file-naming-convention': None}),
                                       'file-naming-convention',
                                        PluginRegistryLayoutFileNamingConvention.__args__)

    def test_invalid_file_naming_convention(self) -> None:
        self.assertPydanticLiteralError(lambda: self.instance(**{'file-naming-convention': 'invalid'}),
                                       'file-naming-convention',
                                        PluginRegistryLayoutFileNamingConvention.__args__)

    def test_file_naming_conventions(self) -> None:
        self.assertTupleEqual(('abbreviated', 'identifier', 'underscore'),
                              PluginRegistryLayoutFileNamingConvention.__args__)

    def test_get_dstfile(self) -> None:
        for fnc in PluginRegistryLayoutFileNamingConvention.__args__:
            bprl = self.instance(**{'type': self.type(),
                                    'file-naming-convention': fnc})
            self.assertEqual(bprl.get_file_naming_convention(), fnc)
            ret = getattr(bprl, '_get_dstfile')('org.myproject.plugin.MyPlugin')
            if fnc == 'identifier':
                self.assertEqual(ret, 'org.myproject.plugin.MyPlugin.jar')
            elif fnc == 'abbreviated':
                self.assertEqual(ret, 'MyPlugin.jar')
            elif fnc == 'underscore':
                self.assertEqual(ret, 'org_myproject_plugin_MyPlugin.jar')
            else:
                self.fail(f'Internal error: {fnc}')


class TestDirectoryPluginRegistryLayout(_BasePluginRegistryLayoutTestCase):

    def instance(self, **kwargs) -> DirectoryPluginRegistryLayout:
        return DirectoryPluginRegistryLayout(**kwargs)

    def type(self) -> str:
        return 'directory'


class TestRcsPluginRegistryLayout(_BasePluginRegistryLayoutTestCase):

    def instance(self, **kwargs) -> RcsPluginRegistryLayout:
        return RcsPluginRegistryLayout(**kwargs)

    def type(self) -> str:
        return 'rcs'


class TestPluginRegistryLayer(PydanticTestCase):

    class _FakePluginRegistry:
        def get_root(self) -> Path:
            return ROOT

    def test_missing_identifier(self) -> None:
        self.assertPydanticMissing(lambda: PluginRegistryLayer(),
                                   'id')

    def test_null_identifier(self) -> None:
        self.assertPydanticStringType(lambda: PluginRegistryLayer(id=None),
                                      'id')

    def test_missing_name(self) -> None:
        self.assertPydanticMissing(lambda: PluginRegistryLayer(),
                                   'name')

    def test_null_name(self) -> None:
        self.assertPydanticStringType(lambda: PluginRegistryLayer(name=None),
                                      'name')

    def test_missing_path(self) -> None:
        self.assertPydanticMissing(lambda: PluginRegistryLayer(),
                                   'path')

    def test_null_path(self) -> None:
        self.assertPydanticStringType(lambda: PluginRegistryLayer(path=None),
                                      'path')

    def test_uninitialized(self) -> None:
        prl = PluginRegistryLayer(id='myid',
                                  name='My Name',
                                  path='whatever')
        self.assertRaises(ValueError, lambda: prl.get_plugin_registry())
        self.assertRaises(ValueError, lambda: prl.get_path())

    def test_absolute_path(self) -> None:
        prl = PluginRegistryLayer(id='myid',
                                  name='My Name',
                                  path='/tmp/mydir').initialize(TestPluginRegistryLayer._FakePluginRegistry())
        self.assertEqual(prl.get_path(), Path('/tmp/mydir'))

    def test_relative_path(self) -> None:
        prl = PluginRegistryLayer(id='myid',
                                  name='My Name',
                                  path='mydir').initialize(TestPluginRegistryLayer._FakePluginRegistry())
        self.assertEqual(prl.get_path(), ROOT.joinpath('mydir'))


class TestPluginRegistry(PydanticTestCase):

    def test_missing_kind(self) -> None:
        self.assertPydanticMissing(lambda: PluginRegistry(),
                                   'kind')

    def test_null_kind(self) -> None:
        self.assertPydanticLiteralError(lambda: PluginRegistry(kind=None),
                                       'kind',
                                        'PluginRegistry')

    def test_wrong_kind(self) -> None:
        self.assertPydanticLiteralError(lambda: PluginRegistry(kind='WrongKind'),
                                       'kind',
                                        'PluginRegistry')

    def test_missing_identifier(self) -> None:
        self.assertPydanticMissing(lambda: PluginRegistry(),
                                   'id')

    def test_null_identifier(self) -> None:
        self.assertPydanticStringType(lambda: PluginRegistry(id=None),
                                     'id')

    def test_missing_name(self) -> None:
        self.assertPydanticMissing(lambda: PluginRegistry(id='myid'),
                                   'name')

    def test_null_name(self) -> None:
        self.assertPydanticStringType(lambda: PluginRegistry(name=None),
                                     'name')

    def test_missing_layout(self) -> None:
        self.assertPydanticMissing(lambda: PluginRegistry(),
                                   'layout')

    def test_null_layout(self) -> None:
        self.assertPydanticModelAttributesType(lambda: PluginRegistry(layout=None),
                                   'layout')

    def test_missing_layers(self) -> None:
        self.assertPydanticMissing(lambda: PluginRegistry(),
                                   'layers')

    def test_null_layers(self) -> None:
        self.assertPydanticListType(lambda: PluginRegistry(layers=None),
                                   'layers')

    def test_empty_layers(self) -> None:
        self.assertPydanticTooShort(lambda: PluginRegistry(layers=[]),
                                   'layers')

    def test_missing_plugin_identifiers(self) -> None:
        self.assertPydanticMissing(lambda: PluginRegistry(),
                                   'plugin-identifiers')


    def test_null_plugin_identifiers(self) -> None:
        self.assertPydanticListType(lambda: PluginRegistry(**{'plugin-identifiers': None}),
                                    'plugin-identifiers')

    def test_empty_plugin_identifiers(self) -> None:
        self.assertPydanticTooShort(lambda: PluginRegistry(**{'plugin-identifiers': []}),
                                    'plugin-identifiers')


#
# See https://stackoverflow.com/a/43353680
#
del _BasePluginRegistryLayoutTestCase

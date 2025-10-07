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

    def setUp(self) -> None:
        super().setUp()
        self.valid_absolute = PluginRegistryCatalog(**{'kind': 'PluginRegistryCatalog',
                                                       'plugin-registry-files': [
                                                           '/tmp/one.yaml',
                                                       ]}).initialize(ROOT)
        self.valid_relative = PluginRegistryCatalog(**{'kind': 'PluginRegistryCatalog',
                                                       'plugin-registry-files': [
                                                           'one.yaml',
                                                       ]}).initialize(ROOT)

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

    def test_kind(self) -> None:
        self.assertEqual(self.valid_absolute.kind, 'PluginRegistryCatalog')
        self.assertEqual(self.valid_relative.kind, 'PluginRegistryCatalog')

    def test_get_plugin_registry_files(self) -> None:
        self.assertListEqual(self.valid_absolute.get_plugin_registry_files(),
                             [Path('/tmp/one.yaml')])
        self.assertListEqual(self.valid_relative.get_plugin_registry_files(),
                             [ROOT.joinpath('one.yaml')])


# Important: see "del _BasePluginRegistryLayoutTestCase" at the end
class _BasePluginRegistryLayoutTestCase(ABC, PydanticTestCase):

    def setUp(self) -> None:
        class _FakePluginRegistry:
            def get_root(self) -> Path:
                return ROOT

        super().setUp()
        self.fake_plugin_registry = _FakePluginRegistry()
        self.valid_identifier = self.instance(**{'type': self.type(),
                                                 'file-naming-convention': 'identifier'}).initialize(self.fake_plugin_registry)
        self.valid_abbreviated = self.instance(**{'type': self.type(),
                                                  'file-naming-convention': 'abbreviated'}).initialize(self.fake_plugin_registry)
        self.valid_underscore = self.instance(**{'type': self.type(),
                                                 'file-naming-convention': 'underscore'}).initialize(self.fake_plugin_registry)
        self.valid = [self.valid_identifier, self.valid_abbreviated, self.valid_underscore]

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

    def test_file_naming_conventions(self) -> None:
        self.assertTupleEqual(('abbreviated', 'identifier', 'underscore'),
                              PluginRegistryLayoutFileNamingConvention.__args__)

    def test_default_file_naming_convention(self) -> None:
        self.assertEqual(self.instance(type=self.type()).get_file_naming_convention(),
                         'identifier')

    def test_null_file_naming_convention(self) -> None:
        self.assertPydanticLiteralError(lambda: self.instance(**{'file-naming-convention': None}),
                                       'file-naming-convention',
                                        PluginRegistryLayoutFileNamingConvention.__args__)

    def test_invalid_file_naming_convention(self) -> None:
        self.assertPydanticLiteralError(lambda: self.instance(**{'file-naming-convention': 'invalid'}),
                                       'file-naming-convention',
                                        PluginRegistryLayoutFileNamingConvention.__args__)

    def test_get_type(self) -> None:
        for valid in self.valid:
            self.assertEqual(valid.get_type(), self.type())

    def test_get_file_naming_convention(self) -> None:
        self.assertEqual(self.valid_identifier.get_file_naming_convention(), 'identifier')
        self.assertEqual(self.valid_abbreviated.get_file_naming_convention(), 'abbreviated')
        self.assertEqual(self.valid_underscore.get_file_naming_convention(), 'underscore')

    def test_get_dstfile(self) -> None:
        plugid = 'org.myproject.plugin.MyPlugin'
        self.assertEqual(getattr(self.valid_identifier, '_get_dstfile')(plugid),
                         'org.myproject.plugin.MyPlugin.jar')
        self.assertEqual(getattr(self.valid_abbreviated, '_get_dstfile')(plugid),
                         'MyPlugin.jar')
        self.assertEqual(getattr(self.valid_underscore, '_get_dstfile')(plugid),
                         'org_myproject_plugin_MyPlugin.jar')

    def test_get_plugin_registry(self) -> None:
        for valid in self.valid:
            self.assertEqual(valid.get_plugin_registry(), self.fake_plugin_registry)


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

    def setUp(self) -> None:
        class _FakePluginRegistry:
            def get_root(self) -> Path:
                return ROOT

        super().setUp()
        self.fake_plugin_registry = _FakePluginRegistry()
        self.valid_absolute = PluginRegistryLayer(id='mylayer',
                                                  name='My Layer',
                                                  path='/tmp/layerdir').initialize(self.fake_plugin_registry)
        self.valid_relative = PluginRegistryLayer(id='mylayer',
                                                  name='My Layer',
                                                  path='layerdir').initialize(self.fake_plugin_registry)
        self.valid = [self.valid_absolute, self.valid_relative]

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

    def test_get_id(self) -> None:
        for valid in self.valid:
            self.assertEqual(valid.get_id(), 'mylayer')

    def test_get_name(self) -> None:
        for valid in self.valid:
            self.assertEqual(valid.get_name(), 'My Layer')

    def test_get_path(self) -> None:
        self.assertEqual(self.valid_absolute.get_path(), Path('/tmp/layerdir'))
        self.assertEqual(self.valid_relative.get_path(), ROOT.joinpath('layerdir'))

    def test_get_plugin_registry(self) -> None:
        for valid in self.valid:
            self.assertEqual(valid.get_plugin_registry(), self.fake_plugin_registry)


class TestPluginRegistry(PydanticTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.valid_layout = DirectoryPluginRegistryLayout(type='directory')
        self.valid_layer = PluginRegistryLayer(id='mylayer',
                                               name='My Layer',
                                               path='layerpath')
        self.valid = PluginRegistry(**{'kind': 'PluginRegistry',
                                       'id': 'myid',
                                       'name': 'My Name',
                                       'layout': self.valid_layout,
                                       'layers': [
                                           self.valid_layer
                                       ],
                                       'plugin-identifiers': [
                                           'org.myproject.plugin.MyPlugin'
                                       ],
                                       'suppressed-plugin-identifiers': [
                                           'org.myproject.plugin.BadPlugin'
                                       ]}).initialize(ROOT)

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

    def test_missing_suppressed_plugin_identifiers(self) -> None:
        PluginRegistry(**{'kind': 'PluginRegistry',
                          'id': 'myid',
                          'name': 'My Name',
                          'layout': self.valid_layout,
                          'layers': [
                              self.valid_layer,
                          ],
                          'plugin-identifiers': [
                              'whatever',
                          ]})

    def test_null_suppressed_plugin_identifiers(self) -> None:
        self.assertPydanticListType(lambda: PluginRegistry(**{'suppressed-plugin-identifiers': None}),
                                    'suppressed-plugin-identifiers')

    def test_empty_plugin_identifiers(self) -> None:
        PluginRegistry(**{'kind': 'PluginRegistry',
                          'id': 'myid',
                          'name': 'My Name',
                          'layout': self.valid_layout,
                          'layers': [
                              self.valid_layer,
                          ],
                          'plugin-identifiers': [
                              'whatever',
                          ],
                          'suppressed-plugin-identifiers': []
                          })

    def test_kind(self) -> None:
        self.assertEqual(self.valid.kind, 'PluginRegistry')

    def test_get_id(self) -> None:
        self.assertEqual(self.valid.get_id(), 'myid')

    def test_get_name(self) -> None:
        self.assertEqual(self.valid.get_name(), 'My Name')

    def test_get_layout(self) -> None:
        self.assertEqual(self.valid.get_layout(), self.valid_layout)

    def test_get_layers(self) -> None:
        self.assertListEqual(self.valid.get_layers(), [self.valid_layer])

    def test_get_layer(self) -> None:
        self.assertEqual(self.valid.get_layer('mylayer'), self.valid_layer)
        self.assertIsNone(self.valid.get_layer('invalidlayer'))

    def test_get_layer_ids(self) -> None:
        self.assertListEqual(self.valid.get_layer_ids(), ['mylayer'])

    def test_get_plugin_identifiers(self) -> None:
        self.assertListEqual(self.valid.get_plugin_identifiers(),
                             ['org.myproject.plugin.MyPlugin'])

    def test_get_suppressed_plugin_identifiers(self) -> None:
        self.assertListEqual(self.valid.get_suppressed_plugin_identifiers(),
                             ['org.myproject.plugin.BadPlugin'])


#
# See https://stackoverflow.com/a/43353680
#
del _BasePluginRegistryLayoutTestCase

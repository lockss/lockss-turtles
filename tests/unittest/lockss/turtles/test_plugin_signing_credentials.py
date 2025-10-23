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
from lockss.turtles.plugin_signing_credentials import PluginSigningCredentials

class TestPluginSigningCredentials(PydanticTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.valid_absolute = PluginSigningCredentials(**{'kind': 'PluginSigningCredentials',
                                                          'plugin-signing-keystore': '/tmp/keystore.txt',
                                                          'plugin-signing-alias': 'myalias'}).initialize(ROOT)
        self.valid_relative = PluginSigningCredentials(**{'kind': 'PluginSigningCredentials',
                                                          'plugin-signing-keystore': 'keystore.txt',
                                                          'plugin-signing-alias': 'myalias'}).initialize(ROOT)
        self.valid = [self.valid_absolute, self.valid_relative]

    def test_missing_kind(self) -> None:
        self.assertPydanticMissing(lambda: PluginSigningCredentials(),
                                   'kind')

    def test_null_kind(self) -> None:
        self.assertPydanticLiteralError(lambda: PluginSigningCredentials(kind=None),
                                        'kind',
                                        'PluginSigningCredentials')

    def test_wrong_kind(self) -> None:
        self.assertPydanticLiteralError(lambda: PluginSigningCredentials(kind='WrongKind'),
                                        'kind',
                                        'PluginSigningCredentials')

    def test_missing_plugin_signing_alias(self) -> None:
        self.assertPydanticMissing(lambda: PluginSigningCredentials(),
                                   'plugin-signing-alias')

    def test_null_plugin_signing_alias(self) -> None:
        self.assertPydanticStringType(lambda: PluginSigningCredentials(**{'plugin-signing-alias': None}),
                                      'plugin-signing-alias')

    def test_missing_plugin_signing_keystore(self) -> None:
        self.assertPydanticMissing(lambda: PluginSigningCredentials(),
                                   'plugin-signing-keystore')

    def test_null_plugin_signing_keystore(self) -> None:
        self.assertPydanticStringType(lambda: PluginSigningCredentials(**{'plugin-signing-keystore': None}),
                                      'plugin-signing-keystore')

    def test_uninitialized(self) -> None:
        psc = PluginSigningCredentials(**{'kind': 'PluginSigningCredentials',
                                          'plugin-signing-keystore': '/tmp/keystore.txt',
                                          'plugin-signing-alias': 'myalias'})
        self.assertRaises(ValueError, lambda: psc.get_root())
        self.assertRaises(ValueError, lambda: psc.get_plugin_signing_keystore())

    def test_kind(self) -> None:
        for valid in self.valid:
            self.assertEqual(valid.kind, 'PluginSigningCredentials')

    def test_get_plugin_signing_alias(self) -> None:
        for valid in self.valid:
            self.assertEqual(valid.get_plugin_signing_alias(), 'myalias')

    def test_get_plugin_signing_keystore(self) -> None:
        self.assertEqual(self.valid_absolute.get_plugin_signing_keystore(),
                         Path('/tmp/keystore.txt'))
        self.assertEqual(self.valid_relative.get_plugin_signing_keystore(),
                         ROOT.joinpath('keystore.txt'))

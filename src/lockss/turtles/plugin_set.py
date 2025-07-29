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
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Annotated, Any, ClassVar, Literal, Optional, Union

from pydantic import BaseModel, Field

from .plugin import Plugin, PluginIdentifier
from .util import BaseModelWithRoot


PluginSetCatalogKind = Literal['PluginSetCatalog']


class PluginSetCatalog(BaseModelWithRoot):
    kind: PluginSetCatalogKind = Field(description="This object's kind")
    plugin_set_files: list[str] = Field(min_length=1, description="A non-empty list of plugin set files", title='Plugin Set Files', alias='plugin-set-files')

    def get_plugin_set_files(self) -> list[Path]:
        return [self._get_root().joinpath(p) for p in self.plugin_set_files]


PluginSetBuilderType = Literal['ant', 'maven']


class BasePluginSetBuilder(BaseModelWithRoot, ABC):
    TYPE_FIELD: ClassVar[dict[str, str]] = dict(description='A plugin builder type', title='Plugin Builder Type')
    MAIN_FIELD: ClassVar[dict[str, str]] = dict(description="The path to the plugins' source code, relative to the root of the project", title='Main Code Path')
    TEST_FIELD: ClassVar[dict[str, str]] = dict(description="The path to the plugins' unit tests, relative to the root of the project", title='Test Code Path')

    @abstractmethod
    def build_plugin(self, plugin_id: PluginIdentifier, keystore_path: Path, keystore_alias: str, keystore_password=None) -> tuple[Path, Plugin]:
        pass

    def get_main(self) -> Path:
        return self._get_root().joinpath(self._get_main())

    def get_test(self) -> Path:
        return self._get_root().joinpath(self._get_test())

    def get_type(self) -> PluginSetBuilderType:
        return getattr(self, 'type')

    def has_plugin(self, plugin_id: PluginIdentifier) -> bool:
        return self._plugin_path(plugin_id).is_file()

    def make_plugin(self, plugin_id: PluginIdentifier) -> Plugin:
        return Plugin.from_path(self._plugin_path(plugin_id))

    def _get_main(self) -> str:
        return getattr(self, 'main')

    def _get_test(self) -> str:
        return getattr(self, 'test')

    def _plugin_path(self, plugin_id: PluginIdentifier) -> Path:
        return self.get_main_path().joinpath(Plugin.id_to_file(plugin_id))


class AntPluginSetBuilder(BasePluginSetBuilder):
    DEFAULT_MAIN: ClassVar[str] = 'plugins/src'
    DEFAULT_TEST: ClassVar[str] = 'plugins/test/src'

    type: Literal['ant'] = Field(**BasePluginSetBuilder.TYPE_FIELD)
    main: Optional[str] = Field(DEFAULT_MAIN, **BasePluginSetBuilder.MAIN_FIELD)
    test: Optional[str] = Field(DEFAULT_TEST, **BasePluginSetBuilder.TEST_FIELD)

    _built: bool

    def build_plugin(self, plugin_id: PluginIdentifier, keystore_path: Path, keystore_alias: str, keystore_password=None) -> tuple[Path, Plugin]:
        # Prerequisites
        if 'JAVA_HOME' not in os.environ:
            raise Exception('error: JAVA_HOME must be set in your environment')
        # Big build (maybe)
        self._big_build()
        # Little build
        return self._little_build(plugin_id, keystore_path, keystore_alias, keystore_password=keystore_password)

    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)
        self._built = False

    def _big_build(self) -> None:
        if not self._built:
            # Do build
            subprocess.run('ant load-plugins',
                           shell=True, cwd=self._get_root(), check=True, stdout=sys.stdout, stderr=sys.stderr)
            self._built = True

    def _little_build(self, plugin_id: PluginIdentifier, keystore_path: Path, keystore_alias: str, keystore_password: str=None) -> tuple[Path, Plugin]:
        orig_plugin = None
        cur_id = plugin_id
        # Get all directories for jarplugin -d
        dirs = list()
        while cur_id is not None:
            cur_plugin = self.make_plugin(cur_id)
            orig_plugin = orig_plugin or cur_plugin
            cur_dir = Plugin.id_to_dir(cur_id)
            if cur_dir not in dirs:
                dirs.append(cur_dir)
            for aux_package in cur_plugin.get_aux_packages():
                aux_dir = Plugin.id_to_dir(f'{aux_package}.FAKEPlugin')
                if aux_dir not in dirs:
                    dirs.append(aux_dir)
            cur_id = cur_plugin.get_parent_identifier()
        # Invoke jarplugin
        jar_fstr = Plugin.id_to_file(plugin_id)
        jar_path = self._get_root().joinpath('plugins/jars', f'{plugin_id}.jar')
        jar_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ['test/scripts/jarplugin',
               '-j', str(jar_path),
               '-p', str(jar_fstr)]
        for d in dirs:
            cmd.extend(['-d', d])
        subprocess.run(cmd, cwd=self._get_root(), check=True, stdout=sys.stdout, stderr=sys.stderr)
        # Invoke signplugin
        cmd = ['test/scripts/signplugin',
               '--jar', str(jar_path),
               '--alias', keystore_alias,
               '--keystore', str(keystore_path)]
        if keystore_password is not None:
            cmd.extend(['--password', keystore_password])
        try:
            subprocess.run(cmd, cwd=self._get_root(), check=True, stdout=sys.stdout, stderr=sys.stderr)
        except subprocess.CalledProcessError as cpe:
            raise self._sanitize(cpe)
        if not jar_path.is_file():
            raise FileNotFoundError(str(jar_path))
        return jar_path, orig_plugin

    def _plugin_path(self, plugin_id: PluginIdentifier) -> Path:
        return self.get_main_path().joinpath(Plugin.id_to_file(plugin_id))

    def _sanitize(self, called_process_error: subprocess.CalledProcessError) -> subprocess.CalledProcessError:
        cmd = called_process_error.cmd[:]
        for i in range(1, len(cmd)):
            if cmd[i - 1] == '--password':
                cmd[i] = '<password>'
        called_process_error.cmd = ' '.join([shlex.quote(c) for c in cmd])
        return called_process_error


class MavenPluginSetBuilder(BasePluginSetBuilder):
    DEFAULT_MAIN: ClassVar[str] = 'src/main/java'
    DEFAULT_TEST: ClassVar[str] = 'src/test/java'

    type: Literal['maven'] = Field(**BasePluginSetBuilder.TYPE_FIELD)
    main: Optional[str] = Field(DEFAULT_MAIN, **BasePluginSetBuilder.MAIN_FIELD)
    test: Optional[str] = Field(DEFAULT_TEST, **BasePluginSetBuilder.TEST_FIELD)

    _built: bool

    def build_plugin(self, plugin_id: PluginIdentifier, keystore_path: Path, keystore_alias: str, keystore_password=None) -> tuple[Path, Plugin]:
        self._big_build(keystore_path, keystore_alias, keystore_password=keystore_password)
        return self._little_build(plugin_id)

    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)
        self._built = False

    def _big_build(self, keystore_path: Path, keystore_alias: str, keystore_password: str=None) -> None:
        if not self._built:
            # Do build
            cmd = ['mvn', 'package',
                   f'-Dkeystore.file={keystore_path!s}',
                   f'-Dkeystore.alias={keystore_alias}',
                   f'-Dkeystore.password={keystore_password}']
            try:
                subprocess.run(cmd, cwd=self._get_root(), check=True, stdout=sys.stdout, stderr=sys.stderr)
            except subprocess.CalledProcessError as cpe:
                raise self._sanitize(cpe)
            self._built = True

    def _little_build(self, plugin_id: PluginIdentifier) -> tuple[Path, Plugin]:
        jar_path = self._get_root().joinpath('target', 'pluginjars', f'{plugin_id}.jar')
        if not jar_path.is_file():
            raise Exception(f'{plugin_id}: built JAR not found: {jar_path!s}')
        return jar_path, Plugin.from_jar(jar_path)

    def _sanitize(self, called_process_error: subprocess.CalledProcessError) -> subprocess.CalledProcessError:
        cmd = called_process_error.cmd[:]
        for i in range(len(cmd)):
            if cmd[i].startswith('-Dkeystore.password='):
                cmd[i] = '-Dkeystore.password=<password>'
        called_process_error.cmd = ' '.join([shlex.quote(c) for c in cmd])
        return called_process_error


PluginSetBuilder = Annotated[Union[AntPluginSetBuilder, MavenPluginSetBuilder], Field(discriminator='type')]


PluginSetKind = Literal['PluginSet']


PluginSetIdentifier = str


class PluginSet(BaseModel):
    kind: PluginSetKind = Field(description="This object's kind")
    id: PluginSetIdentifier = Field(description='An identifier for the plugin set')
    name: str = Field(description='A name for the plugin set')
    builder: PluginSetBuilder = Field(description='A builder for the plugin set', title='Plugin Set Builder')

    def build_plugin(self, plugin_id: PluginIdentifier, keystore_path: Path, keystore_alias: str, keystore_password=None) -> tuple[Path, Plugin]:
        return self.builder.build_plugin(plugin_id, keystore_path, keystore_alias, keystore_password)

    def get_builder(self) -> PluginSetBuilder:
        return self.builder

    def get_id(self) -> PluginSetIdentifier:
        return self.id

    def get_name(self) -> str:
        return self.name

    def has_plugin(self, plugin_id: PluginIdentifier) -> bool:
        return self.get_builder().has_plugin(plugin_id)

    def make_plugin(self, plugin_id: PluginIdentifier) -> Plugin:
        return self.get_builder().make_plugin(plugin_id)

    def _initialize(self, root: Path) -> PluginSet:
        self.get_builder()._initialize(root)
        return self

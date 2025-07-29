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
import subprocess
from typing import Annotated, Any, ClassVar, Literal, Optional, Union

from lockss.pybasic.errorutil import InternalError
from lockss.pybasic.fileutil import path
from pydantic import BaseModel, Field

from .plugin import Plugin, PluginIdentifier
from .util import BaseModelWithRoot



PluginRegistryCatalogKind = Literal['PluginRegistryCatalog']


class PluginRegistryCatalog(BaseModelWithRoot):
    kind: PluginRegistryCatalogKind = Field(description="This object's kind")
    plugin_registry_files: list[str] = Field(min_length=1, description="A non-empty list of plugin registry files", title='Plugin Registry Files', alias='plugin-registry-files')

    def get_plugin_registry_files(self) -> list[Path]:
        return [self._get_root().joinpath(pstr) for pstr in self.plugin_registry_files]


PluginRegistryLayoutType = Literal['directory', 'rcs']


PluginRegistryLayoutFileNamingConvention = Literal['abbreviated', 'identifier', 'underscore']


class BasePluginRegistryLayout(BaseModel, ABC):
    TYPE_FIELD: ClassVar[dict[str, str]] = dict(title='Plugin Registry Layout Type', description='A plugin registry layout type')
    FILE_NAMING_CONVENTION_DEFAULT: ClassVar[PluginRegistryLayoutFileNamingConvention] = 'identifier'
    FILE_NAMING_CONVENTION_FIELD: ClassVar[dict[str, str]] = dict(title='Plugin Registry Layout File Naming Convention', description='A file naming convention for the plugin registry layout', alias='file-naming-convention')

    _plugin_registry: Optional[PluginRegistry]

    def deploy_plugin(self, plugin_id: PluginIdentifier, layer: PluginRegistryLayer, src_path: Path, interactive: bool=False) -> Optional[tuple[Path, Plugin]]:
        src_path = path(src_path)  # in case it's a string
        dst_path = self._get_dstpath(plugin_id, layer)
        if not self._proceed_copy(src_path, dst_path, layer, interactive=interactive):
            return None
        self._copy_jar(src_path, dst_path, interactive=interactive)
        return dst_path, Plugin.from_jar(src_path)

    def get_file_for(self, plugin_id, layer: PluginRegistryLayer) -> Optional[Path]:
        jar_path = self._get_dstpath(plugin_id, layer)
        return jar_path if jar_path.is_file() else None

    def get_file_naming_convention(self) -> PluginRegistryLayoutFileNamingConvention:
        return getattr(self, 'file_naming_convention')

    def get_plugin_registry(self) -> PluginRegistry:
        if self._plugin_registry is None:
            raise RuntimeError('Uninitialized plugin registry')
        return self._plugin_registry

    def get_type(self) -> PluginRegistryLayoutType:
        return getattr(self, 'type')

    def initialize(self, plugin_registry: PluginRegistry) -> BasePluginRegistryLayout:
        self._plugin_registry = plugin_registry
        return self

    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)
        self._plugin_registry = None

    @abstractmethod
    def _copy_jar(self, src_path: Path, dst_path: Path, interactive: bool=False) -> None:
        pass

    def _get_dstfile(self, plugin_id: PluginIdentifier) -> str:
        if (conv := self.get_file_naming_convention()) == 'abbreviated':
            return f'{plugin_id.split(".")[-1]}.jar'
        elif conv == 'identifier':
            return f'{plugin_id}.jar'
        elif conv == 'underscore':
            return f'{plugin_id.replace(".", "_")}.jar'
        else:
            raise InternalError()

    def _get_dstpath(self, plugin_id: PluginIdentifier, layer: PluginRegistryLayer) -> Path:
        return layer.get_path().joinpath(self._get_dstfile(plugin_id))

    def _proceed_copy(self, src_path: Path, dst_path: Path, layer: PluginRegistryLayer, interactive: bool=False) -> bool:
        if not dst_path.exists():
            if interactive:
                i = input(f'{dst_path} does not exist in {self.get_plugin_registry().get_id()}:{layer.get_id()} ({layer.get_name()}); create it (y/n)? [n] ').lower() or 'n'
                if i != 'y':
                    return False
        return True


class DirectoryPluginRegistryLayout(BasePluginRegistryLayout):
    type: Literal['directory'] = Field(**BasePluginRegistryLayout.TYPE_FIELD)
    file_naming_convention: Optional[PluginRegistryLayoutFileNamingConvention] = Field(BasePluginRegistryLayout.FILE_NAMING_CONVENTION_DEFAULT, **BasePluginRegistryLayout.FILE_NAMING_CONVENTION_FIELD)

    def _copy_jar(self, src_path: Path, dst_path: Path, interactive: bool=False) -> None:
        basename = dst_path.name
        subprocess.run(['cp', str(src_path), str(dst_path)], check=True, cwd=self.get_path())
        if subprocess.run('command -v selinuxenabled > /dev/null && selinuxenabled && command -v chcon > /dev/null', shell=True).returncode == 0:
            cmd = ['chcon', '-t', 'httpd_sys_content_t', basename]
            subprocess.run(cmd, check=True, cwd=self.get_path())


class RcsPluginRegistryLayout(DirectoryPluginRegistryLayout):
    type: Literal['rcs'] = Field(**BasePluginRegistryLayout.TYPE_FIELD)
    file_naming_convention: Optional[PluginRegistryLayoutFileNamingConvention] = Field(BasePluginRegistryLayout.FILE_NAMING_CONVENTION_DEFAULT, **BasePluginRegistryLayout.FILE_NAMING_CONVENTION_FIELD)

    def _copy_jar(self, src_path: Path, dst_path: Path, interactive: bool=False) -> None:
        basename = dst_path.name
        plugin = Plugin.from_jar(src_path)
        rcs_path = self.get_path().joinpath('RCS', f'{basename},v')
        # Maybe do co -l before the parent's copy
        if dst_path.exists() and rcs_path.is_file():
            cmd = ['co', '-l', basename]
            subprocess.run(cmd, check=True, cwd=self.get_path())
        # Do the parent's copy
        super()._copy_jar(src_path, dst_path)
        # Do ci -u after the parent's copy
        cmd = ['ci', '-u', f'-mVersion {plugin.get_version()}']
        if not rcs_path.is_file():
            cmd.append(f'-t-{plugin.get_name()}')
        cmd.append(basename)
        subprocess.run(cmd, check=True, cwd=self.get_path())


PluginRegistryLayout = Annotated[Union[DirectoryPluginRegistryLayout, RcsPluginRegistryLayout], Field(discriminator='type')]


PluginRegistryLayerIdentifier = str


class PluginRegistryLayer(BaseModel, ABC):
    PRODUCTION: ClassVar[str] = 'production'
    TESTING: ClassVar[str] = 'testing'

    id: PluginRegistryLayerIdentifier = Field(title='Plugin Registry Layer Identifier', description='An identifier for the plugin registry layer')
    name: str = Field(title='Plugin Registry Layer Name', description='A name for the plugin registry layer')
    path: str = Field(title='Plugin Registry Layer Path', description='A root path for the plugin registry layer')

    def get_id(self) -> PluginRegistryLayerIdentifier:
        return self.id

    def get_jars(self) -> list[Path]:
        return sorted(self.get_path().glob('*.jar'))

    def get_name(self) -> str:
        return self.name

    def get_path(self) -> Path:
        return path(self.path)


PluginRegistryKind = Literal['PluginRegistry']


PluginRegistryIdentifier = str


class PluginRegistry(BaseModelWithRoot):
    kind: PluginRegistryKind = Field(description="This object's kind")
    id: PluginRegistryIdentifier = Field(title='Plugin Registry Identifier', description='An identifier for the plugin set')
    name: str = Field(title='Plugin Registry Name', description='A name for the plugin set')
    layout: PluginRegistryLayout = Field(title='Plugin Registry Layout', description='A layout for the plugin registry')
    layers: list[PluginRegistryLayer] = Field(min_length=1, title='Plugin Registry Layers', description="A non-empty list of plugin registry layers", alias='plugin-registry-layers')
    plugin_identifiers: list[PluginIdentifier] = Field(min_length=1, title='Plugin Identifiers', description="A non-empty list of plugin identifiers", alias='plugin-identifiers')
    suppressed_plugin_identifiers: list[PluginIdentifier] = Field([], title='Suppressed Plugin Identifiers', description="A list of suppressed plugin identifiers", alias='suppressed-plugin-identifiers')

    def get_id(self) -> PluginRegistryIdentifier:
        return self.id

    def get_layer(self, layer_id: PluginRegistryLayerIdentifier) -> Optional[PluginRegistryLayer]:
        for layer in self.get_layers():
            if layer.get_id() == layer_id:
                return layer
        return None

    def get_layer_ids(self) -> list[PluginRegistryLayerIdentifier]:
        return [layer.get_id() for layer in self.get_layers()]

    def get_layers(self) -> list[PluginRegistryLayer]:
        return self.layers

    def get_layout(self) -> BasePluginRegistryLayout:
        return self.layout

    def get_name(self) -> str:
        return self.name

    def get_plugin_identifiers(self) -> list[PluginIdentifier]:
        return self.plugin_identifiers

    def get_suppressed_plugin_identifiers(self) -> list[PluginIdentifier]:
        return self.suppressed_plugin_identifiers

    def has_plugin(self, plugin_id: PluginIdentifier) -> bool:
        return plugin_id in self.get_plugin_identifiers()

    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)
        self.get_layout().initialize(self)

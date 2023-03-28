#!/usr/bin/env python3

# Copyright (c) 2000-2023, Board of Trustees of Leland Stanford Jr. University
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
from pathlib import Path
import subprocess

from lockss.turtles.plugin import Plugin
import lockss.turtles.resources
from lockss.turtles.util import _load_and_validate, _path


class PluginRegistryCatalog(object):

    PLUGIN_REGISTRY_CATALOG_SCHEMA = 'plugin-registry-catalog-schema.json'

    @staticmethod
    def from_path(plugin_registry_catalog_path):
        plugin_registry_catalog_path = _path(plugin_registry_catalog_path)
        with importlib.resources.path(lockss.turtles.resources, PluginRegistryCatalog.PLUGIN_REGISTRY_CATALOG_SCHEMA) as plugin_registry_catalog_schema_path:
            parsed = _load_and_validate(plugin_registry_catalog_schema_path, plugin_registry_catalog_path)
            return PluginRegistryCatalog(parsed)

    def __init__(self, parsed):
        super().__init__()
        self._parsed = parsed

    def get_plugin_registry_files(self):
        return self._parsed['plugin-registry-files']


class PluginRegistry(object):

    PLUGIN_REGISTRY_SCHEMA = 'plugin-registry-schema.json'

    @staticmethod
    def from_path(plugin_registry_file_path):
        plugin_registry_file_path = _path(plugin_registry_file_path)
        with importlib.resources.path(lockss.turtles.resources, PluginRegistry.PLUGIN_REGISTRY_SCHEMA) as plugin_registry_schema_path:
           lst = _load_and_validate(plugin_registry_schema_path, plugin_registry_file_path, multiple=True)
           return [PluginRegistry._from_obj(parsed, plugin_registry_file_path) for parsed in lst]

    @staticmethod
    def _from_obj(parsed, plugin_registry_file_path):
        typ = parsed['layout']['type']
        if typ == DirectoryPluginRegistry.LAYOUT:
            return DirectoryPluginRegistry(parsed)
        elif typ == RcsPluginRegistry.LAYOUT:
            return RcsPluginRegistry(parsed)
        else:
            raise RuntimeError(f'{plugin_registry_file_path!s}: unknown layout type: {typ}')

    def __init__(self, parsed):
        super().__init__()
        self._parsed = parsed

    def get_id(self):
        return self._parsed['id']

    def get_layer(self, layer_id):
        for layer in self.get_layers():
            if layer.get_id() == layer_id:
                return layer
        return None

    def get_layer_ids(self):
        return [layer.get_id() for layer in self.get_layers()]

    def get_layers(self):
        return [self._make_layer(layer_elem) for layer_elem in self._parsed['layers']]

    def get_layout_type(self):
        return self._parsed['layout']['type']

    def get_name(self):
        return self._parsed['name']

    def get_plugin_identifiers(self):
        return self._parsed['plugin-identifiers']

    def has_plugin(self, plugin_id):
        return plugin_id in self.get_plugin_identifiers()

    def _make_layer(self, parsed):
        raise NotImplementedError('_make_layer')


class PluginRegistryLayer(object):

    PRODUCTION = 'production'

    TESTING = 'testing'

    def __init__(self, plugin_registry, parsed):
        super().__init__()
        self._parsed = parsed
        self._plugin_registry = plugin_registry

    # Returns (dst_path, plugin)
    def deploy_plugin(self, plugin_id, jar_path, interactive=False):
        raise NotImplementedError('deploy_plugin')

    def get_file_for(self, plugin_id):
        raise NotImplementedError('get_file_for')

    def get_id(self):
        return self._parsed['id']

    def get_jars(self):
        raise NotImplementedError('get_jars')

    def get_name(self):
        return self._parsed['name']

    def get_path(self):
        return _path(self._parsed['path'])

    def get_plugin_registry(self):
        return self._plugin_registry


class DirectoryPluginRegistry(PluginRegistry):

    LAYOUT = 'directory'

    FILE_NAMING_CONVENTION_ABBREVIATED = 'abbreviated'

    FILE_NAMING_CONVENTION_IDENTIFIER = 'identifier'

    FILE_NAMING_CONVENTION_UNDERSCORE = 'underscore'

    DEFAULT_FILE_NAMING_CONVENTION = FILE_NAMING_CONVENTION_IDENTIFIER

    def __init__(self, parsed):
        super().__init__(parsed)

    def _make_layer(self, parsed):
        return DirectoryPluginRegistryLayer(self, parsed)


class DirectoryPluginRegistryLayer(PluginRegistryLayer):

    def __init__(self, plugin_registry, parsed):
        super().__init__(plugin_registry, parsed)

    def deploy_plugin(self, plugin_id, src_path, interactive=False):
        src_path = _path(src_path)  # in case it's a string
        dst_path = self._get_dstpath(plugin_id)
        if not self._proceed_copy(src_path, dst_path, interactive=interactive):
            return None
        self._copy_jar(src_path, dst_path, interactive=interactive)
        return (dst_path, Plugin.from_jar(src_path))

    def get_file_for(self, plugin_id):
        jar_path = self._get_dstpath(plugin_id)
        return jar_path if jar_path.is_file() else None

    def get_file_naming_convention(self):
        return self.get_plugin_registry()._parsed['layout'].get('file-naming-convention', DirectoryPluginRegistry.DEFAULT_FILE_NAMING_CONVENTION)

    def get_jars(self):
        return sorted(self.get_path().glob('*.jar'))

    def _copy_jar(self, src_path, dst_path, interactive=False):
        basename = dst_path.name
        subprocess.run(['cp', str(src_path), str(dst_path)], check=True, cwd=self.get_path())
        if subprocess.run('command -v selinuxenabled > /dev/null && selinuxenabled && command -v chcon > /dev/null', shell=True).returncode == 0:
            cmd = ['chcon', '-t', 'httpd_sys_content_t', basename]
            subprocess.run(cmd, check=True, cwd=self.get_path())

    def _get_dstpath(self, plugin_id):
        return Path(self.get_path(), self._get_dstfile(plugin_id))

    def _get_dstfile(self, plugin_id):
        conv = self.get_file_naming_convention()
        if conv == DirectoryPluginRegistry.FILE_NAMING_CONVENTION_IDENTIFIER:
            return f'{plugin_id}.jar'
        elif conv == DirectoryPluginRegistry.FILE_NAMING_CONVENTION_UNDERSCORE:
            return f'{plugin_id.replace(".", "_")}.jar'
        elif conv == DirectoryPluginRegistry.FILE_NAMING_CONVENTION_ABBREVIATED:
            return f'{plugin_id.split(".")[-1]}.jar'
        else:
            raise RuntimeError(f'{self.get_plugin_registry().get_id()}: unknown file naming convention: {conv}')

    def _proceed_copy(self, src_path, dst_path, interactive=False):
        if not dst_path.exists():
            if interactive:
                i = input(f'{dst_path} does not exist in {self.get_plugin_registry().get_id()}:{self.get_id()} ({self.get_name()}); create it (y/n)? [n] ').lower() or 'n'
                if i != 'y':
                    return False
        return True


class RcsPluginRegistry(DirectoryPluginRegistry):

    LAYOUT = 'rcs'

    def __init__(self, parsed):
        super().__init__(parsed)

    def _make_layer(self, parsed):
        return RcsPluginRegistryLayer(self, parsed)


class RcsPluginRegistryLayer(DirectoryPluginRegistryLayer):

    def __init__(self, plugin_registry, parsed):
        super().__init__(plugin_registry, parsed)

    def _copy_jar(self, src_path, dst_path, interactive=False):
        basename = dst_path.get_name
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

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
        plugin_registry_catalog_schema_path = importlib.resources.path(lockss.turtles.resources, PluginRegistryCatalog.PLUGIN_REGISTRY_CATALOG_SCHEMA)
        parsed = _load_and_validate(plugin_registry_catalog_schema_path, plugin_registry_catalog_path)
        return PluginRegistryCatalog(parsed)

    def __init__(self, parsed):
        super().__init__()
        self._parsed = parsed

    def plugin_registry_files(self):
        return self._parsed['plugin-registry-files']


class PluginRegistry(object):

    PLUGIN_REGISTRY_SCHEMA = 'plugin-registry-schema.json'

    @staticmethod
    def from_path(plugin_registry_file_path):
        plugin_registry_file_path = _path(plugin_registry_file_path)
        plugin_registry_schema_path = importlib.resources.path(lockss.turtles.resources, PluginRegistry.PLUGIN_REGISTRY_SCHEMA)
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

    def get_layer(self, layer_id):
        for layer in self.get_layers():
            if layer.id() == layer_id:
                return layer
        return None

    def get_layer_ids(self):
        return [layer.id() for layer in self.get_layers()]

    def get_layers(self):
        return [self._make_layer(layer_elem) for layer_elem in self._parsed['layers']]

    def has_plugin(self, plugin_id):
        return plugin_id in self.plugin_identifiers()

    def id(self):
        return self._parsed['id']

    def layout_type(self):
        return self._parsed['layout']['type']

    def layout_options(self):
        return self._parsed['layout'].get('options', dict())

    def name(self):
        return self._parsed['name']

    def plugin_identifiers(self):
        return self._parsed['plugin-identifiers']

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

    def get_jars(self):
        raise NotImplementedError('get_jars')

    def id(self):
        return self._parsed['id']

    def name(self):
        return self._parsed['name']

    def path(self):
        return _path(self._parsed['path'])

    def plugin_registry(self):
        return self._plugin_registry


class DirectoryPluginRegistry(PluginRegistry):
    LAYOUT = 'directory'

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

    def get_jars(self):
        return sorted(self.path().glob('*.jar'))

    def _copy_jar(self, src_path, dst_path, interactive=False):
        basename = dst_path.name
        subprocess.run(['cp', str(src_path), str(dst_path)], check=True, cwd=self.path())
        if subprocess.run('command -v selinuxenabled > /dev/null && selinuxenabled && command -v chcon > /dev/null',
                          shell=True).returncode == 0:
            cmd = ['chcon', '-t', 'httpd_sys_content_t', basename]
            subprocess.run(cmd, check=True, cwd=self.path())

    def _get_dstpath(self, plugin_id):
        return Path(self.path(), self._get_dstfile(plugin_id))

    def _get_dstfile(self, plugin_id):
        return f'{plugin_id}.jar'

    def _proceed_copy(self, src_path, dst_path, interactive=False):
        if not dst_path.exists():
            if interactive:
                i = input(
                    f'{dst_path} does not exist in {self.plugin_registry().id()}:{self.id()} ({self.name()}); create it (y/n)? [n] ').lower() or 'n'
                if i != 'y':
                    return False
        return True


class RcsPluginRegistry(DirectoryPluginRegistry):

    IDENTIFIER = 'identifier'

    ABBREVIATED = 'abbreviated'

    def __init__(self, parsed):
        super().__init__(parsed)

    def _make_layer(self, parsed):
        return RcsPluginRegistryLayer(self, parsed)


class RcsPluginRegistryLayer(DirectoryPluginRegistryLayer):

    def __init__(self, plugin_registry, parsed):
        super().__init__(plugin_registry, parsed)

    def _copy_jar(self, src_path, dst_path, interactive=False):
        basename = dst_path.name
        plugin = Plugin.from_jar(src_path)
        rcs_path = self.path().joinpath('RCS', f'{basename},v')
        # Maybe do co -l before the parent's copy
        if dst_path.exists() and rcs_path.is_file():
            cmd = ['co', '-l', basename]
            subprocess.run(cmd, check=True, cwd=self.path())
        # Do the parent's copy
        super()._copy_jar(src_path, dst_path)
        # Do ci -u after the aprent's copy
        cmd = ['ci', '-u', f'-mVersion {plugin.version()}']
        if not rcs_path.is_file():
            cmd.append(f'-t-{plugin.name()}')
        cmd.append(basename)
        subprocess.run(cmd, check=True, cwd=self.path())

    def _get_dstfile(self, plugid):
        conv = self.plugin_registry().layout_options().get('file-naming-convention')
        if conv == RcsPluginRegistry.ABBREVIATED:
            return f'{plugid.split(".")[-1]}.jar'
        elif conv == RcsPluginRegistry.IDENTIFIER or conv is None:
            return super()._get_dstfile(plugid)
        else:
            raise RuntimeError(
                f'{self.plugin_registry().id()}: unknown file naming convention in layout options: {conv}')

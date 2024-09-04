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
import os
from pathlib import Path
import shlex
import subprocess
import sys

from lockss.turtles.plugin import Plugin
import lockss.turtles.resources
from lockss.turtles.util import _load_and_validate, _path


class PluginSetCatalog(object):

    PLUGIN_SET_CATALOG_SCHEMA = 'plugin-set-catalog-schema.json'

    @staticmethod
    def from_path(plugin_set_catalog_path):
        plugin_set_catalog_path = _path(plugin_set_catalog_path)
        with importlib.resources.path(lockss.turtles.resources, PluginSetCatalog.PLUGIN_SET_CATALOG_SCHEMA) as plugin_set_catalog_schema_path:
            parsed = _load_and_validate(plugin_set_catalog_schema_path, plugin_set_catalog_path)
            return PluginSetCatalog(parsed)

    def __init__(self, parsed):
        super().__init__()
        self._parsed = parsed

    def get_plugin_set_files(self):
        return self._parsed['plugin-set-files']


class PluginSet(object):

    PLUGIN_SET_SCHEMA = 'plugin-set-schema.json'

    @staticmethod
    def from_path(plugin_set_file_path):
        plugin_set_file_path = _path(plugin_set_file_path)
        with importlib.resources.path(lockss.turtles.resources, PluginSet.PLUGIN_SET_SCHEMA) as plugin_set_schema_path:
            lst = _load_and_validate(plugin_set_schema_path, plugin_set_file_path, multiple=True)
            return [PluginSet._from_obj(parsed, plugin_set_file_path) for parsed in lst]

    @staticmethod
    def _from_obj(parsed, plugin_set_file_path):
        typ = parsed['builder']['type']
        if typ == AntPluginSet.TYPE:
            return AntPluginSet(parsed, plugin_set_file_path)
        elif typ == MavenPluginSet.TYPE:
            return MavenPluginSet(parsed, plugin_set_file_path)
        else:
            raise Exception(f'{plugin_set_file_path!s}: unknown builder type: {typ}')

    def __init__(self, parsed):
        super().__init__()
        self._parsed = parsed

    # Returns (jar_path, plugin)
    def build_plugin(self, plugin_id, keystore_path, keystore_alias, keystore_password=None):
        raise NotImplementedError('build_plugin')

    def get_builder_type(self):
        return self._parsed['builder']['type']

    def get_id(self):
        return self._parsed['id']

    def get_name(self):
        return self._parsed['name']

    def has_plugin(self, plugin_id):
        raise NotImplementedError('has_plugin')

    def make_plugin(self, plugin_id):
        raise NotImplementedError('make_plugin')


class AntPluginSet(PluginSet):

    TYPE = 'ant'

    DEFAULT_MAIN = 'plugins/src'

    DEFAULT_TEST = 'plugins/test/src'

    def __init__(self, parsed, path):
        super().__init__(parsed)
        self._built = False
        self._root = path.parent

    # Returns (jar_path, plugin)
    def build_plugin(self, plugin_id, keystore_path, keystore_alias, keystore_password=None):
        # Prerequisites
        if 'JAVA_HOME' not in os.environ:
            raise Exception('error: JAVA_HOME must be set in your environment')
        # Big build (maybe)
        self._big_build()
        # Little build
        return self._little_build(plugin_id, keystore_path, keystore_alias, keystore_password=keystore_password)

    def get_main(self):
        return self._parsed.get('main', AntPluginSet.DEFAULT_MAIN)

    def get_main_path(self):
        return self.get_root_path().joinpath(self.get_main())

    def get_root(self):
        return self._root

    def get_root_path(self):
        return Path(self.get_root()).expanduser().resolve()

    def get_test(self):
        return self._parsed.get('test', AntPluginSet.DEFAULT_TEST)

    def get_test_path(self):
        return self.get_root_path().joinpath(self.get_test())

    def has_plugin(self, plugin_id):
        return self._plugin_path(plugin_id).is_file()

    def make_plugin(self, plugin_id):
        return Plugin.from_path(self._plugin_path(plugin_id))

    def _big_build(self):
        if not self._built:
            # Do build
            subprocess.run('ant load-plugins',
                           shell=True, cwd=self.get_root_path(), check=True, stdout=sys.stdout, stderr=sys.stderr)
            self._built = True

    # Returns (jar_path, plugin)
    def _little_build(self, plugin_id, keystore_path, keystore_alias, keystore_password=None):
        cur_id = plugin_id
        # Get all directories for jarplugin -d
        dirs = list()
        while cur_id is not None:
            cur_plugin = self.make_plugin(cur_id)
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
        jar_path = self.get_root_path().joinpath('plugins/jars', f'{plugin_id}.jar')
        jar_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ['test/scripts/jarplugin',
               '-j', str(jar_path),
               '-p', str(jar_fstr)]
        for d in dirs:
            cmd.extend(['-d', d])
        subprocess.run(cmd, cwd=self.get_root_path(), check=True, stdout=sys.stdout, stderr=sys.stderr)
        # Invoke signplugin
        cmd = ['test/scripts/signplugin',
               '--jar', str(jar_path),
               '--alias', keystore_alias,
               '--keystore', str(keystore_path)]
        if keystore_password is not None:
            cmd.extend(['--password', keystore_password])
        try:
            subprocess.run(cmd, cwd=self.get_root_path(), check=True, stdout=sys.stdout, stderr=sys.stderr)
        except subprocess.CalledProcessError as cpe:
            raise self._sanitize(cpe)
        if not jar_path.is_file():
            raise FileNotFoundError(str(jar_path))
        return (jar_path, plugin)

    def _plugin_path(self, plugin_id):
        return Path(self.get_main_path()).joinpath(Plugin.id_to_file(plugin_id))

    def _sanitize(self, called_process_error):
        cmd = called_process_error.cmd[:]
        i = 0
        for i in range(len(cmd)):
            if i > 1 and cmd[i - 1] == '--password':
                cmd[i] = '<password>'
        called_process_error.cmd = ' '.join([shlex.quote(c) for c in cmd])
        return called_process_error


class MavenPluginSet(PluginSet):

    TYPE = 'maven'

    DEFAULT_MAIN = 'src/main/java'

    DEFAULT_TEST = 'src/test/java'

    def __init__(self, parsed, path):
        super().__init__(parsed)
        self._built = False
        self._root = path.parent

    # Returns (jar_path, plugin)
    def build_plugin(self, plugin_id, keystore_path, keystore_alias, keystore_password=None):
        self._big_build(keystore_path, keystore_alias, keystore_password=keystore_password)
        return self._little_build(plugin_id)

    def get_main(self):
        return self._parsed.get('main', MavenPluginSet.DEFAULT_MAIN)

    def get_main_path(self):
        return self.get_root_path().joinpath(self.get_main())

    def get_root(self):
        return self._root

    def get_root_path(self):
        return Path(self.get_root()).expanduser().resolve()

    def get_test(self):
        return self._parsed.get('test', MavenPluginSet.DEFAULT_TEST)

    def get_test_path(self):
        return self.get_root_path().joinpath(self.get_test())

    def has_plugin(self, plugin_id):
        return self._plugin_path(plugin_id).is_file()

    def make_plugin(self, plugin_id):
        return Plugin.from_path(self._plugin_path(plugin_id))

    def _big_build(self, keystore_path, keystore_alias, keystore_password=None):
        if not self._built:
            # Do build
            cmd = ['mvn', 'package',
                   f'-Dkeystore.file={keystore_path!s}',
                   f'-Dkeystore.alias={keystore_alias}',
                   f'-Dkeystore.password={keystore_password}']
            try:
                subprocess.run(cmd, cwd=self.get_root_path(), check=True, stdout=sys.stdout, stderr=sys.stderr)
            except subprocess.CalledProcessError as cpe:
                raise self._sanitize(cpe)
            self._built = True

    # Returns (jar_path, plugin)
    def _little_build(self, plugin_id):
        jar_path = Path(self.get_root_path(), 'target', 'pluginjars', f'{plugin_id}.jar')
        if not jar_path.is_file():
            raise Exception(f'{plugin_id}: built JAR not found: {jar_path!s}')
        return (jar_path, Plugin.from_jar(jar_path))

    def _plugin_path(self, plugin_id):
        return Path(self.get_main_path()).joinpath(Plugin.id_to_file(plugin_id))

    def _sanitize(self, called_process_error):
        cmd = called_process_error.cmd[:]
        i = 0
        for i in range(len(cmd)):
            if cmd[i].startswith('-Dkeystore.password='):
                cmd[i] = '-Dkeystore.password=<password>'
        called_process_error.cmd = ' '.join([shlex.quote(c) for c in cmd])
        return called_process_error

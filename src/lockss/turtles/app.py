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

import xdg

from lockss.turtles.plugin import Plugin
from lockss.turtles.plugin_registry import PluginRegistry, PluginRegistryCatalog
from lockss.turtles.plugin_set import PluginSet, PluginSetCatalog
import lockss.turtles.resources
from lockss.turtles.util import _load_and_validate, _path


class TurtlesApp(object):

    XDG_CONFIG_DIR = xdg.xdg_config_home().joinpath(__package__)

    USR_CONFIG_DIR = Path('/usr/local/share', __package__)

    ETC_CONFIG_DIR = Path('/etc', __package__)

    CONFIG_DIRS = [XDG_CONFIG_DIR, USR_CONFIG_DIR, ETC_CONFIG_DIR]

    PLUGIN_REGISTRY_CATALOG = 'plugin-registry-catalog.yaml'

    PLUGIN_SET_CATALOG = 'plugin-set-catalog.yaml'

    PLUGIN_SIGNING_CREDENTIALS = 'plugin-signing-credentials.yaml'

    PLUGIN_SIGNING_CREDENTIALS_SCHEMA = 'plugin-signing-credentials-schema.json'

    @staticmethod
    def _default_files(file_str):
        return [dir_path.joinpath(file_str) for dir_path in TurtlesApp.CONFIG_DIRS]

    @staticmethod
    def _select_file(file_str, preselected=None):
        if preselected:
            preselected = _path(preselected)
            if not preselected.is_file():
                raise FileNotFoundError(str(preselected))
            return preselected
        choices = TurtlesApp._default_files(file_str)
        ret = next(filter(Path.is_file, choices), None)
        if ret is None:
            raise FileNotFoundError(' or '.join(map(str, choices)))
        return ret

    def __init__(self):
        super().__init__()
        self._password = None
        self._plugin_registries = None
        self._plugin_sets = None
        self._plugin_signing_credentials = None

    # Returns plugin_id -> (set_id, jar_path, plugin)
    def build_plugin(self, plugin_ids):
        return {plugin_id: self._build_one_plugin(plugin_id) for plugin_id in plugin_ids}

    def default_plugin_registry_catalogs(self):
        return TurtlesApp._default_files(TurtlesApp.PLUGIN_REGISTRY_CATALOG)

    def default_plugin_set_catalogs(self):
        return TurtlesApp._default_files(TurtlesApp.PLUGIN_SET_CATALOG)

    def default_plugin_signing_credentials(self):
        return TurtlesApp._default_files(TurtlesApp.PLUGIN_SIGNING_CREDENTIALS)

    # Returns (src_path, plugin_id) -> list of (registry_id, layer_id, dst_path, plugin)
    def deploy_plugin(self, src_paths, layer_ids, interactive=False):
        plugin_ids = [Plugin.id_from_jar(src_path) for src_path in src_paths]
        return {(src_path, plugin_id): self._deploy_one_plugin(src_path,
                                                               plugin_id,
                                                               layer_ids,
                                                               interactive=interactive) for src_path, plugin_id in zip(src_paths, plugin_ids)}

    def load_plugin_registries(self, plugin_registry_catalog_path=None):
        if self._plugin_registries is None:
            plugin_registry_catalog = PluginRegistryCatalog.from_path(self.select_plugin_registry_catalog(plugin_registry_catalog_path))
            self._plugin_registries = list()
            for plugin_registry_file in plugin_registry_catalog.get_plugin_registry_files():
                self._plugin_registries.extend(PluginRegistry.from_path(plugin_registry_file))

    def load_plugin_sets(self, plugin_set_catalog_path=None):
        if self._plugin_sets is None:
            plugin_set_catalog = PluginSetCatalog.from_path(self.select_plugin_set_catalog(plugin_set_catalog_path))
            self._plugin_sets = list()
            for plugin_set_file in plugin_set_catalog.get_plugin_set_files():
                self._plugin_sets.extend(PluginSet.from_path(plugin_set_file))

    def load_plugin_signing_credentials(self, plugin_signing_credentials_path=None):
        if self._plugin_signing_credentials is None:
            plugin_signing_credentials_path = _path(plugin_signing_credentials_path) if plugin_signing_credentials_path else self._select_file(TurtlesApp.PLUGIN_SIGNING_CREDENTIALS)
            with importlib.resources.path(lockss.turtles.resources, TurtlesApp.PLUGIN_SIGNING_CREDENTIALS_SCHEMA) as plugin_signing_credentials_schema_path:
                self._plugin_signing_credentials = _load_and_validate(plugin_signing_credentials_schema_path, plugin_signing_credentials_path)

    # Returns plugin_id -> list of (registry_id, layer_id, dst_path, plugin)
    def release_plugin(self, plugin_ids, layer_ids, interactive=False):
        # ... plugin_id -> (set_id, jar_path, plugin)
        ret1 = self.build_plugin(plugin_ids)
        jar_paths = [jar_path for set_id, jar_path, plugin in ret1.values()]
        # ... (src_path, plugin_id) -> list of (registry_id, layer_id, dst_path, plugin)
        ret2 = self.deploy_plugin(jar_paths,
                                  layer_ids,
                                  interactive=interactive)
        return {plugin_id: val for (jar_path, plugin_id), val in ret2.items()}

    def select_plugin_registry_catalog(self, preselected=None):
        return TurtlesApp._select_file(TurtlesApp.PLUGIN_REGISTRY_CATALOG, preselected)

    def select_plugin_set_catalog(self, preselected=None):
        return TurtlesApp._select_file(TurtlesApp.PLUGIN_SET_CATALOG, preselected)

    def select_plugin_signing_credentials(self, preselected=None):
        return TurtlesApp._select_file(TurtlesApp.PLUGIN_SIGNING_CREDENTIALS, preselected)

    def set_password(self, pw):
        self._password = pw if callable(pw) else lambda x: pw

    # Returns (set_id, jar_path, plugin)
    def _build_one_plugin(self, plugin_id):
        for plugin_set in self._plugin_sets:
            if plugin_set.has_plugin(plugin_id):
                return (plugin_set.get_id(),
                        *plugin_set.build_plugin(plugin_id,
                                                 self._get_plugin_signing_keystore(),
                                                 self._get_plugin_signing_alias(),
                                                 self._get_plugin_signing_password()))
        raise Exception(f'{plugin_id}: not found in any plugin set')

    # Returns list of (registry_id, layer_id, dst_path, plugin)
    def _deploy_one_plugin(self, src_jar, plugin_id, layer_ids, interactive=False):
        ret = list()
        for plugin_registry in self._plugin_registries:
            if plugin_registry.has_plugin(plugin_id):
                for layer_id in layer_ids:
                    layer = plugin_registry.get_layer(layer_id)
                    if layer is not None:
                        ret.append((plugin_registry.get_id(),
                                    layer.get_id(),
                                    *layer.deploy_plugin(plugin_id,
                                                         src_jar,
                                                         interactive=interactive)))
        if len(ret) == 0:
            raise Exception(f'{src_jar}: {plugin_id} not declared in any plugin registry')
        return ret

    def _get_password(self):
        return self._password() if self._password else None

    def _get_plugin_signing_alias(self):
        return self._plugin_signing_credentials['plugin-signing-alias']

    def _get_plugin_signing_keystore(self):
        return self._plugin_signing_credentials['plugin-signing-keystore']

    def _get_plugin_signing_password(self):
        return self._get_password()

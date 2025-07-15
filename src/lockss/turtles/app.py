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

from collections.abc import Callable
import importlib.resources as IR
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple, Union

import yaml
from lockss.pybasic.fileutil import path
from pydantic import BaseModel, Field
import xdg

from . import resources as __resources__
from .plugin import Plugin
from .plugin_registry import PluginRegistry, PluginRegistryCatalog
from .plugin_set import PluginSet, PluginSetCatalog
from .util import YamlT, load_and_validate


class PluginSigningCredentials(BaseModel):
    kind: Literal['PluginSigningCredentials'] = Field(description="This object's kind")
    plugin_signing_keystore: str = Field(title='Plugin Signing Keystore', description='A path to the plugin signing keystore')
    plugin_signing_alias: str = Field(title='Plugin Signing Alias', description='The plugin signing alias to use')

    def get_plugin_signing_alias(self) -> str:
        return self.plugin_signing_alias

    def get_plugin_signing_keystore(self) -> Path:
        return path(self.plugin_signing_keystore)


class TurtlesApp(object):

    CONFIG_DIR_NAME = 'lockss-turtles'

    XDG_CONFIG_DIR: Path = xdg.xdg_config_home().joinpath(CONFIG_DIR_NAME)

    USR_CONFIG_DIR: Path = Path('/usr/local/share', CONFIG_DIR_NAME)

    ETC_CONFIG_DIR: Path = Path('/etc', CONFIG_DIR_NAME)

    CONFIG_DIRS: List[Path] = [XDG_CONFIG_DIR, USR_CONFIG_DIR, ETC_CONFIG_DIR]

    PLUGIN_REGISTRY_CATALOG: str = 'plugin-registry-catalog.yaml'

    PLUGIN_SET_CATALOG: str = 'plugin-set-catalog.yaml'

    PLUGIN_SIGNING_CREDENTIALS: str = 'plugin-signing-credentials.yaml'

    PLUGIN_SIGNING_CREDENTIALS_SCHEMA: str = 'plugin-signing-credentials-schema.json'

    def __init__(self) -> None:
        super().__init__()
        self._password: Optional[Callable[[], str]] = None
        self._plugin_registries: Optional[List[PluginRegistry]] = None
        self._plugin_sets: Optional[List[PluginSet]] = None
        self._plugin_signing_credentials: Optional[PluginSigningCredentials] = None

    def build_plugin(self, plugin_ids: List[str]) -> Dict[str, Tuple[str, Path, Plugin]]:
        return {plugin_id: self._build_one_plugin(plugin_id) for plugin_id in plugin_ids}

    def deploy_plugin(self, src_paths: List[Path], layer_ids: List[str], interactive: bool=False) -> Dict[Tuple[Path, str], List[Tuple[str, str, Optional[Path], Optional[Plugin]]]]:
        plugin_ids = [Plugin.id_from_jar(src_path) for src_path in src_paths]
        return {(src_path, plugin_id): self._deploy_one_plugin(src_path,
                                                               plugin_id,
                                                               layer_ids,
                                                               interactive=interactive) for src_path, plugin_id in zip(src_paths, plugin_ids)}

    def load_plugin_registries(self, plugin_registry_catalog_path: Optional[Union[Path, str]]=None) -> None:
        if self._plugin_registries is None:
            with self.select_plugin_registry_catalog(plugin_registry_catalog_path).open('r') as fprc:
                plugin_registry_catalog = PluginRegistryCatalog(**yaml.safe_load(fprc))._initialize(plugin_registry_catalog_path)
            self._plugin_registries = list()
            for plugin_registry_file in plugin_registry_catalog.get_plugin_registry_files():
                with plugin_registry_file.open('r') as fpr:
                    for pr in yaml.safe_load_all(fpr):
                        self._plugin_registries.append(PluginRegistry(**pr))

    def load_plugin_sets(self, plugin_set_catalog_path: Optional[Union[Path, str]]=None) -> None:
        plugin_set_catalog_path = path(plugin_set_catalog_path)
        if self._plugin_sets is None:
            with self.select_plugin_set_catalog(plugin_set_catalog_path) as fpsc:
                plugin_set_catalog = PluginSetCatalog(**yaml.safe_load(fpsc))._initialize(plugin_set_catalog_path)
            self._plugin_sets = list()
            for plugin_set_file in plugin_set_catalog.get_plugin_set_files():
                with plugin_set_file.open('r') as fps:
                    for ps in yaml.safe_load_all(fps):
                        self._plugin_sets.append(PluginSet(**ps)._initialize(plugin_set_file))

    def load_plugin_signing_credentials(self, plugin_signing_credentials_path: Optional[Union[Path, str]]=None) -> None:
        if self._plugin_signing_credentials is None:
            with self.select_plugin_signing_credentials(plugin_signing_credentials_path).open('r') as fpsc:
                self._plugin_signing_credentials = PluginSigningCredentials(**yaml.safe_load(fpsc))

    def release_plugin(self, plugin_ids: List[str], layer_ids: List[str], interactive: bool=False) -> Dict[str, List[Tuple[str, str, Path, Plugin]]]:
        # ... plugin_id -> (set_id, jar_path, plugin)
        ret1 = self.build_plugin(plugin_ids)
        jar_paths = [jar_path for set_id, jar_path, plugin in ret1.values()]
        # ... (src_path, plugin_id) -> list of (registry_id, layer_id, dst_path, plugin)
        ret2 = self.deploy_plugin(jar_paths,
                                  layer_ids,
                                  interactive=interactive)
        return {plugin_id: val for (jar_path, plugin_id), val in ret2.items()}

    def select_plugin_registry_catalog(self, preselected: Optional[Union[Path, str]]=None) -> Path:
        return TurtlesApp._select_file(TurtlesApp.PLUGIN_REGISTRY_CATALOG, preselected)

    def select_plugin_set_catalog(self, preselected: Optional[Union[Path, str]]=None) -> Path:
        return TurtlesApp._select_file(TurtlesApp.PLUGIN_SET_CATALOG, preselected)

    def select_plugin_signing_credentials(self, preselected: Optional[Union[Path, str]]=None) -> Path:
        return TurtlesApp._select_file(TurtlesApp.PLUGIN_SIGNING_CREDENTIALS, preselected)

    def set_password(self, pw: Union[Callable[[], str], str]) -> None:
        self._password = pw if callable(pw) else lambda: pw

    def _build_one_plugin(self, plugin_id: str) -> Tuple[str, Optional[Path], Optional[Plugin]]:
        for plugin_set in self._plugin_sets:
            if plugin_set.has_plugin(plugin_id):
                bp = plugin_set.build_plugin(plugin_id,
                                             self._get_plugin_signing_keystore(),
                                             self._get_plugin_signing_alias(),
                                             self._get_plugin_signing_password())
                return plugin_set.get_id(), bp[0] if bp else None, bp[1] if bp else None
        raise Exception(f'{plugin_id}: not found in any plugin set')

    def _deploy_one_plugin(self, src_jar: Path, plugin_id: str, layer_ids: List[str], interactive: bool=False) -> List[Tuple[str, str, Optional[Path], Optional[Plugin]]]:
        ret = list()
        for plugin_registry in self._plugin_registries:
            if plugin_registry.has_plugin(plugin_id):
                for layer_id in layer_ids:
                    layer = plugin_registry.get_layer(layer_id)
                    if layer is not None:
                        dp = layer.deploy_plugin(plugin_id,
                                                 src_jar,
                                                 interactive=interactive)
                        ret.append((plugin_registry.get_id(),
                                    layer.get_id(),
                                    dp[0] if dp else None,
                                    dp[1] if dp else None))
        if len(ret) == 0:
            raise Exception(f'{src_jar}: {plugin_id} not declared in any plugin registry')
        return ret

    def _get_password(self) -> Optional[str]:
        return self._password() if self._password else None

    def _get_plugin_signing_alias(self) -> str:
        return self._plugin_signing_credentials.get_plugin_signing_alias()

    def _get_plugin_signing_keystore(self) -> Path:
        return self._plugin_signing_credentials.get_plugin_signing_keystore()

    def _get_plugin_signing_password(self) -> str:
        return self._get_password()

    @staticmethod
    def default_plugin_registry_catalogs() -> List[Path]:
        return TurtlesApp._default_files(TurtlesApp.PLUGIN_REGISTRY_CATALOG)

    @staticmethod
    def default_plugin_set_catalogs() -> List[Path]:
        return TurtlesApp._default_files(TurtlesApp.PLUGIN_SET_CATALOG)

    @staticmethod
    def default_plugin_signing_credentials() -> List[Path]:
        return TurtlesApp._default_files(TurtlesApp.PLUGIN_SIGNING_CREDENTIALS)

    @staticmethod
    def _default_files(file_str) -> List[Path]:
        return [dir_path.joinpath(file_str) for dir_path in TurtlesApp.CONFIG_DIRS]

    @staticmethod
    def _select_file(file_str, preselected: Optional[Union[Path, str]]=None) -> Path:
        if preselected:
            preselected = path(preselected)
            if not preselected.is_file():
                raise FileNotFoundError(str(preselected))
            return preselected
        choices = TurtlesApp._default_files(file_str)
        ret = next(filter(lambda f: f.is_file(), choices), None)
        if ret is None:
            raise FileNotFoundError(' or '.join(map(str, choices)))
        return ret

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

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import ClassVar, Literal, Optional, Union

from exceptiongroup import ExceptionGroup
from lockss.pybasic.fileutil import path
from pydantic import Field, ValidationError
import xdg
import yaml

from .plugin import Plugin, PluginIdentifier
from .plugin_registry import PluginRegistry, PluginRegistryCatalog, PluginRegistryCatalogKind, PluginRegistryKind, PluginRegistryLayerIdentifier
from .plugin_set import PluginSet, PluginSetCatalog, PluginSetCatalogKind, PluginSetKind
from .util import BaseModelWithRoot, PathOrStr



PluginSigningCredentialsKind = Literal['PluginSigningCredentials']


class PluginSigningCredentials(BaseModelWithRoot):
    kind: PluginSigningCredentialsKind = Field(description="This object's kind")
    plugin_signing_keystore: str = Field(title='Plugin Signing Keystore', description='A path to the plugin signing keystore', alias='plugin-signing-keystore')
    plugin_signing_alias: str = Field(title='Plugin Signing Alias', description='The plugin signing alias to use', alias='plugin-signing-alias')

    def get_plugin_signing_alias(self) -> str:
        return self.plugin_signing_alias

    def get_plugin_signing_keystore(self) -> Path:
        return self.get_root().joinpath(self.plugin_signing_keystore)


class TurtlesApp(object):

    CONFIG_DIR_NAME: ClassVar[str] = 'lockss-turtles'

    XDG_CONFIG_DIR: ClassVar[Path] = Path(xdg.xdg_config_home(), CONFIG_DIR_NAME)

    USR_CONFIG_DIR: ClassVar[Path] = Path('/usr/local/share', CONFIG_DIR_NAME)

    ETC_CONFIG_DIR: ClassVar[Path] = Path('/etc', CONFIG_DIR_NAME)

    CONFIG_DIRS: ClassVar[tuple[Path, ...]] = (XDG_CONFIG_DIR, USR_CONFIG_DIR, ETC_CONFIG_DIR)

    PLUGIN_REGISTRY_CATALOG: ClassVar[str] = 'plugin-registry-catalog.yaml'

    PLUGIN_SET_CATALOG: ClassVar[str] = 'plugin-set-catalog.yaml'

    PLUGIN_SIGNING_CREDENTIALS: ClassVar[str] = 'plugin-signing-credentials.yaml'

    def __init__(self) -> None:
        super().__init__()
        self._password: Optional[Callable[[], str]] = None
        self._plugin_registries: list[PluginRegistry] = list()
        self._plugin_registry_catalogs: list[PluginRegistryCatalog] = list()
        self._plugin_set_catalogs: list[PluginSetCatalog] = list()
        self._plugin_sets: list[PluginSet] = list()
        self._plugin_signing_credentials: Optional[PluginSigningCredentials] = None

    def build_plugin(self, plugin_ids: list[PluginIdentifier]) -> dict[str, tuple[str, Path, Plugin]]:
        return {plugin_id: self._build_one_plugin(plugin_id) for plugin_id in plugin_ids}

    def deploy_plugin(self, src_paths: list[Path], layer_ids: list[PluginRegistryLayerIdentifier], interactive: bool=False) -> dict[tuple[Path, str], list[tuple[str, str, Optional[Path], Optional[Plugin]]]]:
        plugin_ids = [Plugin.id_from_jar(src_path) for src_path in src_paths]
        return {(src_path, plugin_id): self._deploy_one_plugin(src_path,
                                                               plugin_id,
                                                               layer_ids,
                                                               interactive=interactive) for src_path, plugin_id in zip(src_paths, plugin_ids)}

    def load_plugin_registries(self, plugin_registry_path_or_str: PathOrStr) -> TurtlesApp:
        plugin_registry_path = path(plugin_registry_path_or_str)
        if plugin_registry_path in map(lambda pr: pr.get_root(), self._plugin_registries):
            raise ValueError(f'Plugin registries already loaded from: {plugin_registry_path!s}')
        errs, at_least_one = [], False
        with plugin_registry_path.open('r') as fpr:
            for yaml_obj in yaml.safe_load_all(fpr):
                if isinstance(yaml_obj, dict) and yaml_obj.get('kind') in PluginRegistryKind.__args__:
                    try:
                        plugin_registry = PluginRegistry(**yaml_obj).initialize(plugin_registry_path.parent)
                        self._plugin_registries.append(plugin_registry)
                        at_least_one = True
                    except ValidationError as ve:
                        errs.append(ve)
        if errs:
            raise ExceptionGroup(f'Errors while loading plugin registries from: {plugin_registry_path!s}', errs)
        if not at_least_one:
            raise ValueError(f'No plugin registries found in: {plugin_registry_path!s}')
        return self

    def load_plugin_registry_catalogs(self, plugin_registry_catalog_path_or_str: PathOrStr) -> TurtlesApp:
        plugin_registry_catalog_path = path(plugin_registry_catalog_path_or_str)
        if plugin_registry_catalog_path in map(lambda prc: prc.get_root(), self._plugin_registry_catalogs):
            raise ValueError(f'Plugin registry catalogs already loaded from: {plugin_registry_catalog_path!s}')
        errs, at_least_one = [], False
        with plugin_registry_catalog_path.open('r') as fprc:
            for yaml_obj in yaml.safe_load_all(fprc):
                if isinstance(yaml_obj, dict) and yaml_obj.get('kind') in PluginRegistryCatalogKind.__args__:
                    try:
                        plugin_registry_catalog = PluginRegistryCatalog(**yaml_obj).initialize(plugin_registry_catalog_path.parent)
                        self._plugin_registry_catalogs.append(plugin_registry_catalog)
                        at_least_one = True
                        for plugin_registry_file in plugin_registry_catalog.get_plugin_registry_files():
                            try:
                                self.load_plugin_registries(plugin_registry_catalog_path.joinpath(plugin_registry_file))
                            except ValueError as ve:
                                errs.append(ve)
                            except ExceptionGroup as eg:
                                errs.extend(eg.exceptions)
                    except ValidationError as ve:
                        errs.append(ve)
        if errs:
            raise ExceptionGroup(f'Errors while loading plugin registry catalogs from: {plugin_registry_catalog_path!s}', errs)
        if not at_least_one:
            raise ValueError(f'No plugin registry catalogs found in: {plugin_registry_catalog_path!s}')
        return self

    def load_plugin_set_catalogs(self, plugin_set_catalog_path_or_str: PathOrStr) -> TurtlesApp:
        plugin_set_catalog_path = path(plugin_set_catalog_path_or_str)
        if plugin_set_catalog_path in map(lambda psc: psc.get_root(), self._plugin_set_catalogs):
            raise ValueError(f'Plugin set catalogs already loaded from: {plugin_set_catalog_path!s}')
        errs, at_least_one = [], False
        with plugin_set_catalog_path.open('r') as fpsc:
            for yaml_obj in yaml.safe_load_all(fpsc):
                if isinstance(yaml_obj, dict) and yaml_obj.get('kind') in PluginSetCatalogKind.__args__:
                    try:
                        plugin_set_catalog = PluginSetCatalog(**yaml_obj).initialize(plugin_set_catalog_path.parent)
                        self._plugin_set_catalogs.append(plugin_set_catalog)
                        at_least_one = True
                        for plugin_set_file in plugin_set_catalog.get_plugin_set_files():
                            try:
                                self.load_plugin_sets(plugin_set_catalog_path.joinpath(plugin_set_file))
                            except ValueError as ve:
                                errs.append(ve)
                            except ExceptionGroup as eg:
                                errs.extend(eg.exceptions)
                    except ValidationError as ve:
                        errs.append(ve)
        if errs:
            raise ExceptionGroup(f'Errors while loading plugin set catalogs from: {plugin_set_catalog_path!s}', errs)
        if not at_least_one:
            raise ValueError(f'No plugin set catalogs found in: {plugin_set_catalog_path!s}')
        return self

    def load_plugin_sets(self, plugin_set_path_or_str: PathOrStr) -> TurtlesApp:
        plugin_set_path = path(plugin_set_path_or_str)
        if plugin_set_path in map(lambda ps: ps.get_root(), self._plugin_sets):
            raise ValueError(f'Plugin sets already loaded from: {plugin_set_path!s}')
        errs, at_least_one = [], False
        with plugin_set_path.open('r') as fps:
            for yaml_obj in yaml.safe_load_all(fps):
                if isinstance(yaml_obj, dict) and yaml_obj.get('kind') in PluginSetKind.__args__:
                    try:
                        plugin_set = PluginSet(**yaml_obj).initialize(plugin_set_path.parent)
                        self._plugin_sets.append(plugin_set)
                        at_least_one = True
                    except ValidationError as ve:
                        errs.append(ve)
        if errs:
            raise ExceptionGroup(f'Errors while loading plugin sets from: {plugin_set_path!s}', errs)
        if not at_least_one:
            raise ValueError(f'No plugin sets found in: {plugin_set_path!s}')
        return self

    def load_plugin_signing_credentials(self, plugin_signing_credentials_path_or_str: PathOrStr) -> TurtlesApp:
        plugin_signing_credentials_path = path(plugin_signing_credentials_path_or_str)
        if self._plugin_signing_credentials:
            raise ValueError(f'Plugin signing credentials already loaded from: {self._plugin_signing_credentials.get_root()!s}')
        found = 0
        with plugin_signing_credentials_path.open('r') as fpsc:
            for yaml_obj in yaml.safe_load_all(fpsc):
                if isinstance(yaml_obj, dict) and yaml_obj.get('kind') in PluginSigningCredentialsKind.__args__:
                    found = found + 1
                    if not self._plugin_signing_credentials:
                        try:
                            plugin_signing_credentials = PluginSigningCredentials(**yaml.safe_load(fpsc)).initialize(plugin_signing_credentials_path.parent)
                            self._plugin_signing_credentials = plugin_signing_credentials
                        except ValidationError as ve:
                            raise ExceptionGroup(f'Errors while loading plugin signing credentials from: {plugin_signing_credentials_path!s}', [ve])
        if found == 0:
            raise ValueError(f'No plugin signing credentials found in: {plugin_signing_credentials_path!s}')
        if found > 1:
            raise ValueError(f'Multiple plugin signing credentials found in: {plugin_signing_credentials_path!s}')
        return self

    def release_plugin(self, plugin_ids: list[PluginIdentifier], layer_ids: list[PluginRegistryLayerIdentifier], interactive: bool=False) -> dict[str, list[tuple[str, str, Path, Plugin]]]:
        # ... plugin_id -> (set_id, jar_path, plugin)
        ret1 = self.build_plugin(plugin_ids)
        jar_paths = [jar_path for set_id, jar_path, plugin in ret1.values()]
        # ... (src_path, plugin_id) -> list of (registry_id, layer_id, dst_path, plugin)
        ret2 = self.deploy_plugin(jar_paths,
                                  layer_ids,
                                  interactive=interactive)
        return {plugin_id: val for (jar_path, plugin_id), val in ret2.items()}

    def set_password(self, pw: Union[Callable[[], str], str]) -> None:
        self._password = pw if callable(pw) else lambda: pw

    def _build_one_plugin(self, plugin_id: str) -> tuple[str, Optional[Path], Optional[Plugin]]:
        for plugin_set in self._plugin_sets:
            if plugin_set.has_plugin(plugin_id):
                bp = plugin_set.build_plugin(plugin_id,
                                             self._get_plugin_signing_keystore(),
                                             self._get_plugin_signing_alias(),
                                             self._get_plugin_signing_password())
                return plugin_set.get_id(), bp[0] if bp else None, bp[1] if bp else None
        raise Exception(f'{plugin_id}: not found in any plugin set')

    def _deploy_one_plugin(self, src_jar: Path, plugin_id: PluginIdentifier, layer_ids: list[PluginRegistryLayerIdentifier], interactive: bool=False) -> list[tuple[str, str, Optional[Path], Optional[Plugin]]]:
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
    def default_plugin_registry_catalog_choices() -> tuple[Path, ...]:
        return TurtlesApp._default_files(TurtlesApp.PLUGIN_REGISTRY_CATALOG)

    @staticmethod
    def default_plugin_set_catalog_choices() -> tuple[Path, ...]:
        return TurtlesApp._default_files(TurtlesApp.PLUGIN_SET_CATALOG)

    @staticmethod
    def default_plugin_signing_credentials_choices() -> tuple[Path, ...]:
        return TurtlesApp._default_files(TurtlesApp.PLUGIN_SIGNING_CREDENTIALS)

    @staticmethod
    def select_default_plugin_registry_catalog() -> Optional[Path]:
        return TurtlesApp._select_file(TurtlesApp.default_plugin_registry_catalog_choices())

    @staticmethod
    def select_default_plugin_set_catalog() -> Optional[Path]:
        return TurtlesApp._select_file(TurtlesApp.default_plugin_set_catalog_choices())

    @staticmethod
    def select_default_plugin_signing_credentials() -> Optional[Path]:
        return TurtlesApp._select_file(TurtlesApp.default_plugin_signing_credentials_choices())

    @staticmethod
    def _default_files(file_str) -> tuple[Path, ...]:
        return tuple(dir_path.joinpath(file_str) for dir_path in TurtlesApp.CONFIG_DIRS)

    @staticmethod
    def _select_file(choices: Iterable[Path]) -> Optional[Path]:
        for p in choices:
            if p.is_file():
                return p
        return None

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

"""
Module to represent Turtles operations.
"""

# Remove in Python 3.14; see https://stackoverflow.com/a/33533514
from __future__ import annotations

# Remove in Python 3.11; see https://docs.python.org/3.11/library/exceptions.html#exception-groups
from exceptiongroup import ExceptionGroup

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import ClassVar, Optional, Union

from lockss.pybasic.fileutil import path
from pydantic import ValidationError
import xdg
import yaml

from .plugin import Plugin, PluginIdentifier
from .plugin_registry import PluginRegistry, PluginRegistryCatalog, PluginRegistryCatalogKind, PluginRegistryIdentifier, PluginRegistryKind, PluginRegistryLayerIdentifier
from .plugin_set import PluginSet, PluginSetCatalog, PluginSetCatalogKind, PluginSetKind
from .plugin_signing_credentials import PluginSigningCredentials, PluginSigningCredentialsKind
from .util import PathOrStr


#: Type alias for the result of a single plugin building operation.
#: First item (index 0): identifier of the plugin set that had the given plugin.
#: Second item (index 1): plugin JAR file path (or None if not built).
#: Third item (index 2): plugin object (or None if not built).
BuildPluginResult = tuple[str, Optional[Path], Optional[Plugin]]


#: Type alias for the result of a single plugin deployment operation to a given
#: plugin registry layer.
#: First item (index 0):
#: Second item (index 1):
#: Third item (index 2): deployed JAR file path (or None if not deployed).
#: Fourth item (index 3): plugin object (or None if not deployed).
DeployPluginResult = tuple[PluginRegistryIdentifier, PluginRegistryLayerIdentifier, Optional[Path], Optional[Plugin]]


class Turtles(object):
    """
    A Turtles command object, which can be used to execute Turtles operations.
    """

    #: The name of a Turtles configuration directory.
    CONFIG_DIR_NAME: ClassVar[str] = 'lockss-turtles'

    #: The Turtles configuration directory under ``$XDG_CONFIG_HOME`` (by
    # default ``$HOME/.config``, which is typically ``/home/$USER/.config``).
    XDG_CONFIG_DIR: ClassVar[Path] = Path(xdg.xdg_config_home(), CONFIG_DIR_NAME)

    #: The Turtles configuration directory under ``/etc``.
    ETC_CONFIG_DIR: ClassVar[Path] = Path('/etc', CONFIG_DIR_NAME)

    #: The Turtles configuration directory under ``/usr/local/share``.
    USR_CONFIG_DIR: ClassVar[Path] = Path('/usr/local/share', CONFIG_DIR_NAME)

    #: The Turtles configuration directories in order of preference:
    #: ``XDG_CONFIG_DIR``, ``ETC_CONFIG_DIR``, ``USR_CONFIG_DIR``
    CONFIG_DIRS: ClassVar[tuple[Path, ...]] = (XDG_CONFIG_DIR, ETC_CONFIG_DIR, USR_CONFIG_DIR)

    #: The default plugin registry catalog file name.
    PLUGIN_REGISTRY_CATALOG: ClassVar[str] = 'plugin-registry-catalog.yaml'

    #: The default plugin set catalog file name.
    PLUGIN_SET_CATALOG: ClassVar[str] = 'plugin-set-catalog.yaml'

    #: The default plugin signing credentials file name.
    PLUGIN_SIGNING_CREDENTIALS: ClassVar[str] = 'plugin-signing-credentials.yaml'

    def __init__(self) -> None:
        """
        Constructor.
        """
        super().__init__()
        self._plugin_signing_password_callable: Optional[Callable[[], str]] = None
        self._plugin_registries: list[PluginRegistry] = list()
        self._plugin_registry_catalogs: list[PluginRegistryCatalog] = list()
        self._plugin_set_catalogs: list[PluginSetCatalog] = list()
        self._plugin_sets: list[PluginSet] = list()
        self._plugin_signing_credentials: Optional[PluginSigningCredentials] = None

    def build_plugin(self,
                     plugin_id_or_plugin_ids: Union[PluginIdentifier, list[PluginIdentifier]]) -> dict[str, BuildPluginResult]:
        """
        Builds zero or more plugins.

        :param plugin_id_or_plugin_ids: Either one plugin identifier, or a list
                                        of plugin identifiers.
        :type plugin_id_or_plugin_ids: Union[PluginIdentifier, list[PluginIdentifier]]
        :return: A mapping from plugin identifier to build plugin result; if no
                 plugin identifiers were given, the result is an empty mapping.
        :rtype: dict[str, BuildPluginResult]
        :raises Exception: If a given plugin identifier is not found in any
                           loaded plugin set.
        """
        plugin_ids: list[PluginIdentifier] = plugin_id_or_plugin_ids if isinstance(plugin_id_or_plugin_ids, list) else [plugin_id_or_plugin_ids]
        return {plugin_id: self._build_one_plugin(plugin_id) for plugin_id in plugin_ids}

    def deploy_plugin(self,
                      src_path_or_src_paths: Union[Path, list[Path]],
                      layer_id_or_layer_ids: Union[PluginRegistryLayerIdentifier, list[PluginRegistryLayerIdentifier]],
                      interactive: bool=False) -> dict[tuple[Path, PluginIdentifier], list[DeployPluginResult]]:
        """
        Deploys zero or more plugins.

        :param src_path_or_src_paths: Either one signed JAR file paths or a list
                                      of signed JAR file paths.
        :type src_path_or_src_paths: Union[Path, list[Path]]
        :param layer_id_or_layer_ids: Either one plugin registry layer
                                      identifier or a list of plugin registry
                                      layer identifiers.
        :type layer_id_or_layer_ids: Union[PluginRegistryLayerIdentifier, list[PluginRegistryLayerIdentifier]]
        :param interactive: Whether interactive prompts are allowed (default
                            False).
        :type interactive: bool
        :return: A mapping from tuples of signed JAR file path and corresponding
                 plugin identifier to a list of build deployment results (one
                 per plugin registry layer); if no signed JAR file paths were
                 given, the result is an empty mapping.
        :rtype: dict[tuple[Path, PluginIdentifier], list[DeployPluginResult]]
        :raises Exception: If a given plugin is not declared in any loaded
                           plugin registry.
        """
        src_paths: list[Path] = src_path_or_src_paths if isinstance(src_path_or_src_paths, list) else [src_path_or_src_paths]
        layer_ids: list[PluginRegistryLayerIdentifier] = layer_id_or_layer_ids if isinstance(layer_id_or_layer_ids, list) else [layer_id_or_layer_ids]
        plugin_ids = [Plugin.id_from_jar(src_path) for src_path in src_paths] # FIXME: should go down to _deploy_one_plugin?
        return {(src_path, plugin_id): self._deploy_one_plugin(src_path,
                                                               plugin_id,
                                                               layer_ids,
                                                               interactive=interactive) for src_path, plugin_id in zip(src_paths, plugin_ids)}

    def load_plugin_registries(self,
                               plugin_registry_path_or_str: PathOrStr) -> Turtles:
        """
        Processes the given YAML file, loading all plugin registry definitions
        it contains, ignoring other YAML objects.

        :param plugin_registry_path_or_str: A file path (or string).
        :type plugin_registry_path_or_str: PathOrStr
        :return: This Turtles object (for chaining).
        :rtype: Turtles
        :raises ExceptionGroup: If one or more errors occur while loading plugin
                                registry definitions.
        :raises ValueError: If the given file has already been processed or if
                            it contains no plugin registry definitions.
        """
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

    def load_plugin_registry_catalogs(self,
                                      plugin_registry_catalog_path_or_str: PathOrStr) -> Turtles:
        """
        Processes the given YAML file, loading all plugin registry catalog
        definitions it contains and in turn all plugin registry definitions they
        reference, ignoring other YAML objects.

        :param plugin_registry_catalog_path_or_str: A file path (or string).
        :type plugin_registry_catalog_path_or_str: PathOrStr
        :return: This Turtles object (for chaining).
        :rtype: Turtles
        :raises ExceptionGroup: If one or more errors occur while loading plugin
                                registry catalog definitions or the plugin
                                registry definitions they reference.
        :raises ValueError: If the given file has already been processed or if
                            it contains no plugin registry catalog definitions.
        """
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

    def load_plugin_set_catalogs(self,
                                 plugin_set_catalog_path_or_str: PathOrStr) -> Turtles:
        """
        Processes the given YAML file, loading all plugin set catalog
        definitions it contains and in turn all plugin set definitions they
        reference, ignoring other YAML objects.

        :param plugin_set_catalog_path_or_str: A file path (or string).
        :type plugin_set_catalog_path_or_str: PathOrStr
        :return: This Turtles object (for chaining).
        :rtype: Turtles
        :raises ExceptionGroup: If one or more errors occur while loading plugin
                                set catalog definitions or the plugin set
                                definitions they reference.
        :raises ValueError: If the given file has already been processed or if
                            it contains no plugin set catalog definitions.
        """
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

    def load_plugin_sets(self,
                         plugin_set_path_or_str: PathOrStr) -> Turtles:
        """
        Processes the given YAML file, loading all plugin set definitions it
        contains, ignoring other YAML objects.

        :param plugin_set_path_or_str: A file path (or string).
        :type plugin_set_path_or_str: PathOrStr
        :return: This Turtles object (for chaining).
        :rtype: Turtles
        :raises ExceptionGroup: If one or more errors occur while loading plugin
                                set definitions.
        :raises ValueError: If the given file has already been processed or if
                            it contains no plugin set definitions.
        """
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

    def load_plugin_signing_credentials(self,
                                        plugin_signing_credentials_path_or_str: PathOrStr) -> Turtles:
        """
        Processes the given YAML file, loading all plugin set definitions it
        contains in search of exactly one, ignoring YAML objects of other kinds.

        :param plugin_signing_credentials_path_or_str: A file path (or string).
        :type plugin_signing_credentials_path_or_str: PathOrStr
        :return: This Turtles object (for chaining).
        :rtype: Turtles
        :raises ExceptionGroup: If one or more errors occur while loading plugin
                                signing credentials definitions.
        :raises ValueError: If the given file has already been processed, if it
                            contains no plugin signing credentials definitions,
                            or if it contains more than one plugin signing
                            credentials definitions.
        """
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
                            plugin_signing_credentials = PluginSigningCredentials(**yaml_obj).initialize(plugin_signing_credentials_path.parent)
                            self._plugin_signing_credentials = plugin_signing_credentials
                        except ValidationError as ve:
                            raise ExceptionGroup(f'Errors while loading plugin signing credentials from: {plugin_signing_credentials_path!s}', [ve])
        if found == 0:
            raise ValueError(f'No plugin signing credentials found in: {plugin_signing_credentials_path!s}')
        if found > 1:
            raise ValueError(f'Multiple plugin signing credentials found in: {plugin_signing_credentials_path!s}')
        return self

    def release_plugin(self,
                       plugin_id_or_plugin_ids: Union[PluginIdentifier, list[PluginIdentifier]],
                       layer_id_or_layer_ids: Union[PluginRegistryLayerIdentifier, list[PluginRegistryLayerIdentifier]],
                       interactive: bool=False) -> dict[PluginIdentifier, list[DeployPluginResult]]:
        """
        Releases (builds then deploys) zero or more plugins.

        :param plugin_id_or_plugin_ids: Either one plugin identifier, or a list
                                        of plugin identifiers.
        :type plugin_id_or_plugin_ids: Union[PluginIdentifier, list[PluginIdentifier]]
        :param layer_id_or_layer_ids: Either one plugin registry layer
                                      identifier or a list of plugin registry
                                      layer identifiers.
        :type layer_id_or_layer_ids: Union[PluginRegistryLayerIdentifier, list[PluginRegistryLayerIdentifier]]
        :param interactive: Whether interactive prompts are allowed (default
                            False).
        :type interactive: bool
        :return: A mapping from plugin identifier to plugin deployment result;
                 if no plugins were given, the result is an empty mapping.
        :rtype: dict[PluginIdentifier, list[DeployPluginResult]]
        :raises Exception: If a given plugin is not found in any plugin set or
                           is not declared in any loaded plugin registry.
        """
        plugin_ids: list[PluginIdentifier] = plugin_id_or_plugin_ids if isinstance(plugin_id_or_plugin_ids, list) else [plugin_id_or_plugin_ids]
        layer_ids: list[PluginRegistryLayerIdentifier] = layer_id_or_layer_ids if isinstance(layer_id_or_layer_ids, list) else [layer_id_or_layer_ids]
        # ... plugin_id -> (set_id, jar_path, plugin)
        ret1 = self.build_plugin(plugin_ids)
        jar_paths = [jar_path for set_id, jar_path, plugin in ret1.values()]
        # ... (src_path, plugin_id) -> list of (registry_id, layer_id, dst_path, plugin)
        ret2 = self.deploy_plugin(jar_paths,
                                  layer_ids,
                                  interactive=interactive)
        return {plugin_id: val for (jar_path, plugin_id), val in ret2.items()}

    def set_plugin_signing_password(self,
                                    callable_or_password: Union[str, Callable[[], str]]) -> None:
        """
        Sets the plugin signing password callable.

        :param callable_or_password: A callable returning a string (or simply a
                                     string).
        :type callable_or_password: Union[str, Callable[[], str]]
        """
        self._plugin_signing_password_callable = callable_or_password if callable(callable_or_password) else lambda: callable_or_password

    def _build_one_plugin(self,
                          plugin_id: PluginIdentifier) -> BuildPluginResult:
        """
        Builds one plugin.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :return: A plugin build result object; if the plugin set returned None,
                 the second and third items (index 1 and 2) are None.
        :rtype: BuildPluginResult
        :raises Exception: If the given plugin identifier is not found in any
                           loaded plugin set.
        """
        for plugin_set in self._plugin_sets:
            if plugin_set.has_plugin(plugin_id):
                bp = plugin_set.build_plugin(plugin_id,
                                             self._get_plugin_signing_keystore(),
                                             self._get_plugin_signing_alias(),
                                             self._get_plugin_signing_password())
                return plugin_set.get_id(), bp[0] if bp else None, bp[1] if bp else None
        raise Exception(f'plugin identifier not found in any loaded plugin set: {plugin_id}')

    def _deploy_one_plugin(self,
                           src_jar: Path,
                           plugin_id: PluginIdentifier,
                           layer_ids: list[PluginRegistryLayerIdentifier],
                           interactive: bool=False) -> list[DeployPluginResult]:
        """
        Deploys a single plugin to the provided plugin registry layers of all
        loaded plugin registries that declare the given plugin.

        :param src_jar: File path of the signed JAR.
        :type src_jar: Path
        :param plugin_id: The corresponding plugin identifier.
        :type plugin_id: PluginIdentifier
        :param layer_ids: A list of plugin layer identifiers.
        :type layer_ids: list[PluginRegistryLayerIdentifier]
        :param interactive: Whether interactive prompts are allowed (default
                            False).
        :type interactive: bool
        :return: A non-empty list of plugin deployment results; if for any, the
                 plugin registry returned None, the third and fourth items
                 (index 2 and 3) are None.
        :rtype: list[DeployPluginResult]
        :raises Exception: If the given plugin identifier is not declared in any
                           loaded plugin registry.
        """
        ret = list()
        for plugin_registry in self._plugin_registries:
            if plugin_registry.has_plugin(plugin_id):
                for layer_id in layer_ids:
                    if layer := plugin_registry.get_layer(layer_id):
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

    def _get_plugin_signing_alias(self) -> str:
        """
        Returns the plugin signing alias from the loaded plugin signing
        credentials.

        :return: The plugin signing alias.
        :rtype: str
        """
        return self._plugin_signing_credentials.get_plugin_signing_alias()

    def _get_plugin_signing_keystore(self) -> Path:
        """
        Returns the plugin signing keystore file path from the loaded plugin
        signing credentials.

        :return: The plugin signing keystore file path.
        :rtype: Path
        """
        return self._plugin_signing_credentials.get_plugin_signing_keystore()

    def _get_plugin_signing_password(self) -> Optional[Callable[[], str]]:
        """
        Returns the plugin signing password.

        :return: The plugin signing password callable.
        :rtype: Optional[Callable[[], str]]
        """
        return self._plugin_signing_password_callable

    @staticmethod
    def default_plugin_registry_catalog_choices() -> tuple[Path, ...]:
        """
        Returns the tuple of default plugin registry catalog file choices.

        See ``CONFIG_DIRS`` and ``PLUGIN_REGISTRY_CATALOG``.

        :return: A tuple of default plugin registry catalog file choices.
        :rtype: tuple[Path, ...]
        """
        return Turtles._default_files(Turtles.PLUGIN_REGISTRY_CATALOG)

    @staticmethod
    def default_plugin_set_catalog_choices() -> tuple[Path, ...]:
        """
        Returns the tuple of default plugin set catalog file choices.

        See ``CONFIG_DIRS`` and ``PLUGIN_SET_CATALOG``.

        :return: A tuple of default plugin set catalog file choices.
        :rtype: tuple[Path, ...]
        """
        return Turtles._default_files(Turtles.PLUGIN_SET_CATALOG)

    @staticmethod
    def default_plugin_signing_credentials_choices() -> tuple[Path, ...]:
        """
        Returns the tuple of default plugin signing credentials file choices.

        See ``CONFIG_DIRS`` and ``PLUGIN_SIGNING_CREDENTIALS``.

        :return: A tuple of default plugin signing credentials file choices.
        :rtype: tuple[Path, ...]
        """
        return Turtles._default_files(Turtles.PLUGIN_SIGNING_CREDENTIALS)

    @staticmethod
    def select_default_plugin_registry_catalog() -> Optional[Path]:
        """
        Of the default plugin registry catalog file choices, select the first
        one that exists.

        See ``default_plugin_registry_catalog_choices`` and ``_select_file``.

        :return: The first of the default plugin registry catalog file choices
                 that exists, or None if none do.
        :rtype: Optional[Path]
        """
        return Turtles._select_file(Turtles.default_plugin_registry_catalog_choices())

    @staticmethod
    def select_default_plugin_set_catalog() -> Optional[Path]:
        """
        Of the default plugin set catalog file choices, select the first one
        that exists.

        See ``default_plugin_registry_set_choices`` and ``_select_file``.

        :return: The first of the default plugin set catalog file choices that
                 exists, or None if none do.
        :rtype: Optional[Path]
        """
        return Turtles._select_file(Turtles.default_plugin_set_catalog_choices())

    @staticmethod
    def select_default_plugin_signing_credentials() -> Optional[Path]:
        """
        Of the default plugin signing credentials file choices, select the first
        one that exists.

        See ``default_plugin_registry_set_choices`` and ``_select_file``.

        :return: The first of the default plugin signing credentials file
                 choices that exists, or None if none do.
        :rtype: Optional[Path]
        """
        return Turtles._select_file(Turtles.default_plugin_signing_credentials_choices())

    @staticmethod
    def _default_files(file_str) -> tuple[Path, ...]:
        """
        Given a file base name, returns a tuple of this file in the various
        Turtles configuration directories (``CONFIG_DIRS``).

        :param file_str: A file base name.
        :type file_str: str
        :return: The file in the various Turtles configuration directories.
        :rtype: tuple[Path, ...]
        """
        return tuple(dir_path.joinpath(file_str) for dir_path in Turtles.CONFIG_DIRS)

    @staticmethod
    def _select_file(choices: Iterable[Path]) -> Optional[Path]:
        """
        Of the given files, returns the first one that exists.

        :param choices: An iterable of file paths.
        :type choices: Iterable[Path]
        :return: The first choice that exists, or None if none do.
        :rtype: Optional[Path]
        """
        for p in choices:
            if p.is_file():
                return p
        return None

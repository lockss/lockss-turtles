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
Library to represent plugin registries and plugin registry catalogs.
"""

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


#: A type alias for the plugin registry catalog kind.
PluginRegistryCatalogKind = Literal['PluginRegistryCatalog']


class PluginRegistryCatalog(BaseModelWithRoot):
    """
    A Pydantic model (``lockss.turtles.util.BaseModelWithRoot``) to represent a
    plugin registry catalog.
    """

    #: This object's kind.
    kind: PluginRegistryCatalogKind = Field(title='Kind',
                                            description="This object's kind")

    #: A non-empty list of plugin registry files.
    plugin_registry_files: list[str] = Field(alias='plugin-registry-files',
                                             min_length=1,
                                             title='Plugin Registry Files',
                                             description="A non-empty list of plugin registry files")

    def get_plugin_registry_files(self) -> list[Path]:
        """
        Returns the list of plugin registry files in this catalog, relative to
        the plugin registry catalog file if applicable.

        :return: A non-null list of plugin registry file paths.
        :rtype: list[Path]
        """
        return [self.get_root().joinpath(pstr) for pstr in self.plugin_registry_files]


#: A type alias for the two plugin registry layout types.
PluginRegistryLayoutType = Literal['directory', 'rcs']


#: A type alias for the three plugin registry layout file naming conventions.
PluginRegistryLayoutFileNamingConvention = Literal['abbreviated', 'identifier', 'underscore']


class BasePluginRegistryLayout(BaseModel, ABC):
    """
    An abstract Pydantic model (``lockss.turtles.util.BaseModelWithRoot``) to
    represent a plugin registry layout, with concrete implementations
    ``DirectoryPluginRegistryLayout`` and ``RcsPluginRegistryLayout``.
    """

    #: Pydantic definition of the ``type`` field.
    TYPE_FIELD: ClassVar[dict[str, str]] = dict(title='Plugin Registry Layout Type',
                                                description='A plugin registry layout type')

    #: Default file naming convention.
    FILE_NAMING_CONVENTION_DEFAULT: ClassVar[PluginRegistryLayoutFileNamingConvention] = 'identifier'

    #: Pydantic definition of the ``file_naming_convention`` field.
    FILE_NAMING_CONVENTION_FIELD: ClassVar[dict[str, str]] = dict(alias='file-naming-convention',
                                                                  title='Plugin Registry Layout File Naming Convention',
                                                                  description='A file naming convention for the plugin registry layout')

    #: Internal backreference to the enclosing plugin registry; see ``initialize``.
    _plugin_registry: Optional[PluginRegistry]

    def deploy_plugin(self,
                      plugin_id: PluginIdentifier,
                      layer: PluginRegistryLayer,
                      src_path: Path,
                      interactive: bool=False) -> Optional[tuple[Path, Plugin]]:
        """
        Deploys the given plugin to the target plugin registry layer according to
        this plugin registry layout's file naming convention.

        See ``_copy_jar``.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :param layer: A plugin registry layer.
        :type layer: PluginRegistryLayer
        :param src_path: The path of the plugin JAR.
        :type src_path: Path
        :param interactive: If False (the default), no interactive confirmation
                            will occur. If True, and the given plugin is being
                            deployed to the target layer for the very first
                            time, the user will be prompted interactively to
                            confirm.
        :type interactive: bool
        :return: A tuple of the path of the deployed JAR and a Plugin object
                 instantiated from the source JAR, or None if the user was
                 prompted for confirmation and responded negatively.
        :rtype: Optional[tuple[Path, Plugin]]
        """
        src_path = path(src_path)  # in case it's a string
        dst_path = self._get_dstpath(plugin_id, layer)
        if not self._proceed_copy(src_path, dst_path, layer, interactive=interactive):
            return None
        self._copy_jar(src_path, dst_path)
        return dst_path, Plugin.from_jar(src_path)

    # Believed to be abandoned:

    # def get_file_for(self,
    #                  plugin_id,
    #                  layer: PluginRegistryLayer) -> Optional[Path]:
    #     """
    #
    #     :param plugin_id:
    #     :type plugin_id:
    #     :param layer:
    #     :type layer:
    #     :return:
    #     :rtype:
    #     """
    #     jar_path = self._get_dstpath(plugin_id, layer)
    #     return jar_path if jar_path.is_file() else None

    def get_file_naming_convention(self) -> PluginRegistryLayoutFileNamingConvention:
        """
        Returns the concrete implementation's ``file_naming`convention`` field.

        :return: This plugin registry layout's file naming convention.
        :rtype: PluginRegistryLayoutFileNamingConvention
        """
        return getattr(self, 'file_naming_convention')

    def get_plugin_registry(self) -> PluginRegistry:
        """
        Returns the enclosing plugin registry.

        See ``initialize``.

        :return: The enclosing plugin registry.
        :rtype: PluginRegistry
        :raises ValueError: If ``initialize`` was not called on the object.
        """
        if self._plugin_registry is None:
            raise ValueError('Uninitialized plugin registry')
        return self._plugin_registry

    def get_type(self) -> PluginRegistryLayoutType:
        """
        Returns the concrete implementation's ``type`` field.

        :return: This plugin registry layout's type.
        :rtype: PluginRegistryLayoutType
        """
        return getattr(self, 'type')

    def initialize(self,
                   plugin_registry: PluginRegistry) -> BasePluginRegistryLayout:
        """
        Initializes the plugin registry backreference. Mandatory call after
        object creation.

        :param plugin_registry: The enclosing plugin registry.
        :type plugin_registry: PluginRegistry
        :return: This object (for chaining).
        :rtype: BasePluginRegistryLayout
        """
        self._plugin_registry = plugin_registry
        return self

    def model_post_init(self,
                        context: Any) -> None:
        """
        Pydantic post-initialization method, to create the ``_plugin_registry``
        backreference.

        See ``initialize``.

        :param context: The Pydantic context.
        :type context: Any
        """
        super().model_post_init(context)
        self._plugin_registry = None

    @abstractmethod
    def _copy_jar(self,
                  src_path: Path,
                  dst_path: Path) -> None:
        """
        Implementation-specific copy of the plugin JAR from a source path to its
        intended deployed path.

        :param src_path: The path of the plugin JAR to be deployed.
        :type src_path: Path
        :param dst_path: The intended path of the deployed JAR.
        :type dst_path: Path
        """
        pass

    def _get_dstfile(self,
                     plugin_id: PluginIdentifier) -> str:
        """
        Computes the destination file name (not path) based on this layout's
        file naming convention.

        Implemented here because common to both concrete implementations.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :return: A file name string consistent with the file naming convention.
                 For a plugin identifier ``org.myproject.plugin.MyPlugin``, the
                 result is ``MyPlugin.jar`` for ``abbreviated``,
                 ``org.myproject.plugin.MyPlugin.jar`` for ``identifier`` and
                 ``org_myproject_plugin_MyPlugin.jar`` for ``underscore``.
        :rtype: str
        """
        if (conv := self.get_file_naming_convention()) == 'abbreviated':
            return f'{plugin_id.split(".")[-1]}.jar'
        elif conv == 'identifier':
            return f'{plugin_id}.jar'
        elif conv == 'underscore':
            return f'{plugin_id.replace(".", "_")}.jar'
        else:
            raise InternalError()

    def _get_dstpath(self,
                     plugin_id: PluginIdentifier,
                     layer: PluginRegistryLayer) -> Path:
        """
        Computes the destination path for the given plugin being deployed to the
        target layer, using the layout's file naming convention.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :param layer: A target plugin registry layer.
        :type layer: PluginRegistryLayer
        :return: The would-be destination of the deployed JAR.
        :rtype: Path
        """
        return layer.get_path().joinpath(self._get_dstfile(plugin_id))

    def _proceed_copy(self,
                      src_path: Path,
                      dst_path: Path,
                      layer: PluginRegistryLayer,
                      interactive: bool=False) -> bool:
        """
        Determines whether the copy of the JAR should proceed.

        :param src_path: The path of the JAR being deployed.
        :type src_path: Path
        :param dst_path: The path of the intended deployed JAR.
        :type dst_path: Path
        :param layer: The target plugin registry layer.
        :type layer: PluginRegistryLayer
        :param interactive: Whether interactive prompts are allowed (False by
                            default)
        :type interactive: bool
        :return: True, unless the destination file does not exist yet, the
                 interactive flag is True, and the user does not respond
                 positively to the confirmation prompt.
        :rtype: bool
        """
        if not dst_path.exists():
            if interactive:
                i = input(f'{dst_path} does not exist in {self.get_plugin_registry().get_id()}:{layer.get_id()} ({layer.get_name()}); create it (y/n)? [n] ').lower() or 'n'
                if i != 'y':
                    return False
        return True


class DirectoryPluginRegistryLayout(BasePluginRegistryLayout):
    """
    A plugin registry layout that keeps plugin JARs in a single directory.
    """

    #: This plugin registry layout's type.
    type: Literal['directory'] = Field(**BasePluginRegistryLayout.TYPE_FIELD)

    #: This plugin registry layout's file naming convention.
    file_naming_convention: Optional[PluginRegistryLayoutFileNamingConvention] = Field(BasePluginRegistryLayout.FILE_NAMING_CONVENTION_DEFAULT,
                                                                                       **BasePluginRegistryLayout.FILE_NAMING_CONVENTION_FIELD)

    def _copy_jar(self,
                  src_path: Path,
                  dst_path: Path) -> None:
        """
        Copies the plugin JAR from a source path to its intended deployed path.

        Additionally, if SELinux is enabled, sets the type of the security
        context of the deployed path to ``httpd_sys_content_t``.

        :param src_path: The path of the plugin JAR to be deployed.
        :type src_path: Path
        :param dst_path: The intended path of the deployed JAR.
        :type dst_path: Path
        :raises subprocess.CalledProcessError: If an invoked subprocess fails.
        """
        dst_dir, dst_file = dst_path.parent, dst_path.name
        subprocess.run(['cp', str(src_path), str(dst_path)], check=True, cwd=dst_dir)
        if subprocess.run('command -v selinuxenabled > /dev/null && selinuxenabled && command -v chcon > /dev/null', shell=True).returncode == 0:
            cmd = ['chcon', '-t', 'httpd_sys_content_t', dst_file]
            subprocess.run(cmd, check=True, cwd=dst_dir)


class RcsPluginRegistryLayout(DirectoryPluginRegistryLayout):
    """
    A plugin registry layout that is like ``DirectoryPluginRegistryLayout`` but
    also uses `GNU RCS <https://www.gnu.org/software/rcs/>`_ to keep a record of
    successive plugin versions in an ``RCS`` subdirectory.
    """

    #: This plugin registry layout's type. Shadows that of ``DirectoryPluginRegistryLayout`` due to inheritance.
    type: Literal['rcs'] = Field(**BasePluginRegistryLayout.TYPE_FIELD)

    # Believed to be unnecessary:

    #file_naming_convention: Optional[PluginRegistryLayoutFileNamingConvention] = Field(BasePluginRegistryLayout.FILE_NAMING_CONVENTION_DEFAULT, **BasePluginRegistryLayout.FILE_NAMING_CONVENTION_FIELD)

    def _copy_jar(self,
                  src_path: Path,
                  dst_path: Path) -> None:
        """
        Copies the plugin JAR from a source path to its intended deployed path.

        Does ``co -l`` if applicable, does the same copy as the parent
        ``DirectoryPluginRegistryLayout._copy_jar``, then does ``ci -u``.

        :param src_path: The path of the plugin JAR to be deployed.
        :type src_path: Path
        :param dst_path: The intended path of the deployed JAR.
        :type dst_path: Path
        :raises subprocess.CalledProcessError: If an invoked subprocess fails.
        """
        dst_dir, dst_file = dst_path.parent, dst_path.name
        plugin = Plugin.from_jar(src_path)
        rcs_path = dst_dir.joinpath('RCS', f'{dst_file},v')
        # Maybe do co -l before the parent's copy
        if dst_path.exists() and rcs_path.is_file():
            cmd = ['co', '-l', dst_file]
            subprocess.run(cmd, check=True, cwd=dst_dir)
        # Do the parent's copy
        super()._copy_jar(src_path, dst_path)
        # Do ci -u after the parent's copy
        cmd = ['ci', '-u', f'-mVersion {plugin.get_version()}']
        if not rcs_path.is_file():
            cmd.append(f'-t-{plugin.get_name()}')
        cmd.append(dst_file)
        subprocess.run(cmd, check=True, cwd=dst_dir)


#: A type alias for plugin registry layouts, which is the union of
#: ``DirectoryPluginRegistryLayout`` and ``RcsPluginRegistryLayout`` using
#: ``type`` as the discriminator field.
PluginRegistryLayout = Annotated[Union[DirectoryPluginRegistryLayout, RcsPluginRegistryLayout], Field(discriminator='type')]


#: A type alias for plugin registry layer identifiers.
PluginRegistryLayerIdentifier = str


class PluginRegistryLayer(BaseModel):
    """
    A Pydantic model to represent a plugin registry layer.
    """

    #: This plugin registry layer's identifier.
    id: PluginRegistryLayerIdentifier = Field(title='Plugin Registry Layer Identifier',
                                              description='An identifier for the plugin registry layer')

    #: This plugin registry layer's name.
    name: str = Field(title='Plugin Registry Layer Name',
                      description='A name for the plugin registry layer')

    #: This plugin registry layer's path.
    path: str = Field(title='Plugin Registry Layer Path',
                      description='A root path for the plugin registry layer')

    #: Internal backreference to the enclosing plugin registry; see ``initialize``.
    _plugin_registry: Optional[PluginRegistry]

    def deploy_plugin(self,
                      plugin_id: PluginIdentifier,
                      src_path: Path,
                      interactive: bool=False) -> Optional[tuple[Path, Plugin]]:
        """
        Deploys the given plugin to this plugin registry layer according to
        this plugin registry layout's file naming convention.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :param src_path: The path of the plugin JAR.
        :type src_path: Path
        :param interactive: If False (the default), no interactive confirmation
                            will occur. If True, and the given plugin is being
                            deployed to this layer for the very first time, the
                            user will be prompted interactively to confirm.
        :type interactive: bool
        :return: A tuple of the path of the deployed JAR and a Plugin object
                 instantiated from the source JAR, or None if the user was
                 prompted for confirmation and responded negatively.
        :rtype: Optional[tuple[Path, Plugin]]
        """
        return self.get_plugin_registry().get_layout().deploy_plugin(plugin_id, self, src_path, interactive)

    def get_id(self) -> PluginRegistryLayerIdentifier:
        """
        Returns this plugin registry layer's identifier.

        :return: This plugin registry layer's identifier.
        :rtype: PluginRegistryLayerIdentifier
        """
        return self.id

    def get_jars(self) -> list[Path]:
        """
        Returns the list of this plugin registry layer's JAR file paths.

        :return: A sorted list of JAR file paths.
        :rtype: list[Path]
        """
        # FIXME Strictly speaking this should be in the layout
        return sorted(self.get_path().glob('*.jar'))

    def get_name(self) -> str:
        """
        Returns this plugin registry layer's name.

        :return: This plugin registry layer's name.
        :rtype: str
        """
        return self.name

    def get_path(self) -> Path:
        """
        Returns this plugin registry layer's path.

        :return: This plugin registry layer's path.
        :rtype: Path
        """
        return path(self.path)

    def get_plugin_registry(self) -> PluginRegistry:
        """
        Returns the enclosing plugin registry.

        See ``initialize``.

        :return: The enclosing plugin registry.
        :rtype: PluginRegistry
        :raises ValueError: If ``initialize`` was not called on the object.
        """
        if self._plugin_registry is None:
            raise ValueError('Uninitialized plugin registry')
        return self._plugin_registry

    def initialize(self,
                   plugin_registry: PluginRegistry) -> PluginRegistryLayer:
        """
        Initializes the plugin registry backreference. Mandatory call after
        object creation.

        :param plugin_registry: The enclosing plugin registry.
        :type plugin_registry: PluginRegistry
        :return: This object (for chaining).
        :rtype: BasePluginRegistryLayout
        """
        self._plugin_registry = plugin_registry
        return self

    def model_post_init(self,
                        context: Any) -> None:
        """
        Pydantic post-initialization method, to create the ``_plugin_registry``
        backreference.

        See ``initialize``.

        :param context: The Pydantic context.
        :type context: Any
        """
        super().model_post_init(context)
        self._plugin_registry = None


#: A type alias for the plugin registry kind.
PluginRegistryKind = Literal['PluginRegistry']


#: A type alias for plugin registry identifiers.
PluginRegistryIdentifier = str


class PluginRegistry(BaseModelWithRoot):
    """
    A Pydantic model (``lockss.turtles.util.BaseModelWithRoot``) to represent a
    plugin registry.
    """

    #: This object's kind.
    kind: PluginRegistryKind = Field(title='Kind',
                                     description="This object's kind")

    #: This plugin registry's identifier.
    id: PluginRegistryIdentifier = Field(title='Plugin Registry Identifier',
                                         description='An identifier for the plugin set')

    #: This plugin registry's name.
    name: str = Field(title='Plugin Registry Name',
                      description='A name for the plugin set')

    #: This plugin registry's layout.
    layout: PluginRegistryLayout = Field(title='Plugin Registry Layout',
                                         description='A layout for the plugin registry')

    #: This plugin registry's layers.
    layers: list[PluginRegistryLayer] = Field(min_length=1,
                                              title='Plugin Registry Layers',
                                              description="A non-empty list of plugin registry layers")

    #: The plugin identifiers in this registry.
    plugin_identifiers: list[PluginIdentifier] = Field(alias='plugin-identifiers',
                                                       min_length=1,
                                                       title='Plugin Identifiers',
                                                       description="A non-empty list of plugin identifiers")

    #: The suppressed plugin identifiers, formerly in this plugin registry.
    suppressed_plugin_identifiers: list[PluginIdentifier] = Field([],
                                                                  alias='suppressed-plugin-identifiers',
                                                                  title='Suppressed Plugin Identifiers',
                                                                  description="A list of suppressed plugin identifiers")

    def get_id(self) -> PluginRegistryIdentifier:
        """
        Returns this plugin registry's identifier.

        :return: This plugin registry's identifier.
        :rtype: PluginRegistryIdentifier
        """
        return self.id

    def get_layer(self,
                  layer_id: PluginRegistryLayerIdentifier) -> Optional[PluginRegistryLayer]:
        """
        Returns the plugin registry layer with the given identifier.

        :param layer_id: A plugin registry layer identifier.
        :type layer_id: PluginRegistryLayerIdentifier
        :return: The plugin registry layer from this registry with the given
                 identifier, or None if there is no such layer.
        :rtype: Optional[PluginRegistryLayer]
        """
        for layer in self.get_layers():
            if layer.get_id() == layer_id:
                return layer
        return None

    def get_layer_ids(self) -> list[PluginRegistryLayerIdentifier]:
        """
        Returns a list of all the plugin registry layer identifiers in this
        registry.

        :return: A list of plugin registry layer identifiers.
        :rtype: list[PluginRegistryLayerIdentifier]
        """
        return [layer.get_id() for layer in self.get_layers()]

    def get_layers(self) -> list[PluginRegistryLayer]:
        """
        Returns a list of all the plugin registry layers in this registry.

        :return: A list of plugin registry layers.
        :rtype: list[PluginRegistryLayer]
        """
        return self.layers

    def get_layout(self) -> BasePluginRegistryLayout:
        """
        Returns this plugin registry's layout.

        :return: A list of plugin registry layers.
        :rtype: list[PluginRegistryLayer]
        """
        return self.layout

    def get_name(self) -> str:
        """
        Returns this plugin registry's name.

        :return: This plugin registry's name.
        :rtype: str
        """
        return self.name

    def get_plugin_identifiers(self) -> list[PluginIdentifier]:
        """
        Returns the list of plugin identifiers in this registry.

        :return: The list of plugin identifiers in this registry.
        :rtype: list[PluginIdentifier]
        """
        return self.plugin_identifiers

    def get_suppressed_plugin_identifiers(self) -> list[PluginIdentifier]:
        """
        Returns the list of suppressed plugin identifiers in this registry.

        :return: The list of suppressed plugin identifiers in this registry.
        :rtype: list[PluginIdentifier]
        """
        return self.suppressed_plugin_identifiers

    def has_plugin(self,
                   plugin_id: PluginIdentifier) -> bool:
        """
        Determines if a given plugin identifier is in this registry.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :return: True if and only if the given plugin identifier is in this
                 registry.
        :rtype: bool
        """
        return plugin_id in self.get_plugin_identifiers()

    def model_post_init(self,
                        context: Any) -> None:
        """
        Pydantic post-initialization method to initialize the layout and all the
        layers with this registry as the enclosing registry.

        See ``BasePluginRegistrLayout.initialize`` and
        ``PluginRegistryLayout.initialize``.

        :param context: The Pydantic context.
        :type context: Any
        """
        super().model_post_init(context)
        self.get_layout().initialize(self)
        for layer in self.get_layers():
            layer.initialize(self)

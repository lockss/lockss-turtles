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
Module to represent plugin sets and plugin set catalogs.
"""

# Remove in Python 3.14; see https://stackoverflow.com/a/33533514
from __future__ import annotations

from abc import ABC, abstractmethod
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Annotated, Any, Callable, ClassVar, Literal, Optional, Union

from pydantic import BaseModel, Field

from .plugin import Plugin, PluginIdentifier
from .util import BaseModelWithRoot


#: A type alias for the plugin set catalog kind.
PluginSetCatalogKind = Literal['PluginSetCatalog']


class PluginSetCatalog(BaseModelWithRoot):
    """
    A Pydantic model (``lockss.turtles.util.BaseModelWithRoot``) to represent a
    plugin set catalog.
    """

    #: This object's kind.
    kind: PluginSetCatalogKind = Field(title='Kind',
                                       description="This object's kind")

    #: A non-empty list of plugin set files.
    plugin_set_files: list[str] = Field(alias='plugin-set-files',
                                        min_length=1,
                                        title='Plugin Set Files',
                                        description="A non-empty list of plugin set files")

    def get_plugin_set_files(self) -> list[Path]:
        """
        Return this plugin set catalog's list of plugin set definition file
        paths (relative to the root if not absolute).

        :return: A list of plugin set definition file paths.
        :rtype: list[Path]
        """
        return [self.get_root().joinpath(p) for p in self.plugin_set_files]


#: A type alias for the plugin set builder type.
PluginSetBuilderType = Literal['ant', 'maven']


class BasePluginSetBuilder(BaseModelWithRoot, ABC):
    """
    An abstract Pydantic model (``lockss.turtles.util.BaseModelWithRoot``) to
    represent a plugin set builder, with concrete implementations
    ``MavenPluginSetBuilder`` and ``AntPluginSetBuilder``.
    """

    #: Pydantic definition of the ``type`` field.
    TYPE_FIELD: ClassVar[dict[str, str]] = dict(title='Plugin Builder Type',
                                                description='A plugin builder type')

    #: Pydantic definition of the ``main`` field.
    MAIN_FIELD: ClassVar[dict[str, str]] = dict(title='Main Code Path',
                                                description="The path to the plugins' source code, relative to the root of the project")

    #: Pydantic definition of the ``test`` field.
    TEST_FIELD: ClassVar[dict[str, str]] = dict(title='Test Code Path',
                                                description="The path to the plugins' unit tests, relative to the root of the project")

    @abstractmethod
    def build_plugin(self,
                     plugin_id: PluginIdentifier,
                     keystore_path: Path,
                     keystore_alias: str,
                     keystore_password=None) -> tuple[Path, Plugin]:
        """
        Builds the given plugin, using the given plugin signing credentials.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :param keystore_path: The path to the plugin signing keystore.
        :type keystore_path: Path
        :param keystore_alias: The signing alias to use from the plugin signing
                               keystore.
        :type keystore_alias: str
        :param keystore_password: The signing password.
        :type keystore_password: Any
        :return: A tuple of the plugin JAR path and the corresponding ``Plugin``
                 object.
        :rtype: tuple[Path, Plugin]
        """
        pass # FIXME: typing of keystore_password

    def get_main(self) -> Path:
        """
        Returns this plugin set builder's main code path (relative to the root
        if not absolute).

        :return: This plugin set's main code path.
        :rtype: Path
        :raises ValueError: If this object is not properly initialized.
        """
        return self.get_root().joinpath(self._get_main())

    def get_test(self) -> Path:
        """
        Returns this plugin set builder's unit test path (relative to the root
        if not absolute).

        :return: This plugin set's unit test path.
        :rtype: Path
        :raises ValueError: If this object is not properly initialized.
        """
        return self.get_root().joinpath(self._get_test())

    def get_type(self) -> PluginSetBuilderType:
        """
        Returns this plugin set builder's type.

        :return: This plugin set builder's type.
        :rtype: PluginSetBuilderType
        """
        return getattr(self, 'type')

    def has_plugin(self,
                   plugin_id: PluginIdentifier) -> bool:
        """
        Determines if the given plugin identifier represents a plugin that is
        present in the plugin set.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :return: Whether the plugin is present in the plugin set.
        :rtype: bool
        """
        return self._plugin_path(plugin_id).is_file()

    def make_plugin(self,
                    plugin_id: PluginIdentifier) -> Plugin:
        """
        Makes a ``Plugin`` object from the given plugin identifier.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :return: The corresponding ``Plugin`` object.
        :rtype: Plugin
        """
        return Plugin.from_path(self._plugin_path(plugin_id))

    def _get_main(self) -> str:
        """
        Returns the concrete implementation's ``main`` field.

        :return: The ``main`` field.
        :rtype: str
        """
        return getattr(self, 'main')

    def _get_test(self) -> str:
        """
        Returns the concrete implementation's ``test`` field.

        :return: The ``test`` field.
        :rtype: str
        """
        return getattr(self, 'test')

    def _plugin_path(self,
                     plugin_id: PluginIdentifier) -> Path:
        """
        Returns the path of the plugin file for the given plugin identifier
        relative to the plugin set's main code path.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :return: The plugin file.
        :rtype: Path
        """
        return self.get_main().joinpath(Plugin.id_to_file(plugin_id))


class MavenPluginSetBuilder(BasePluginSetBuilder):
    """
    A plugin set builder that uses `Java <https://www.oracle.com/java/>`_
    Development Kit (JDK) 17 and `Apache Maven <https://maven.apache.org/>`_,
    with the parent POM
    `org.lockss:lockss-plugins-parent-pom <https://central.sonatype.com/artifact/org.lockss/lockss-plugins-parent-pom>`_.
    """

    #: The default value for ``main``.
    DEFAULT_MAIN: ClassVar[str] = 'src/main/java'

    #: The default value for ``test``.
    DEFAULT_TEST: ClassVar[str] = 'src/test/java'

    #: This Plugin set builder's type.
    type: Literal['maven'] = Field(**BasePluginSetBuilder.TYPE_FIELD)

    #: This plugin set builder's main code path.
    main: str = Field(DEFAULT_MAIN,
                      **BasePluginSetBuilder.MAIN_FIELD)

    #: This plugin set builder's unit test path.
    test: str = Field(DEFAULT_TEST,
                      **BasePluginSetBuilder.TEST_FIELD)

    #: An internal flag to remember if a build has occurred.
    _built: bool

    def build_plugin(self,
                     plugin_id: PluginIdentifier,
                     keystore_path: Path,
                     keystore_alias: str,
                     keystore_password: Optional[Callable[[], str]]=None) -> tuple[Path, Plugin]:
        """
        Builds the given plugin with the supplied plugin signing credentials.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :param keystore_path: The path to the plugin signing keystore.
        :type keystore_path: Path
        :param keystore_alias: The alias to use in the plugin signing keystore.
        :type keystore_alias: str
        :param keystore_password: The plugin signing password.
        :type keystore_password:
        :return: A tuple of the built and signed JAR file and a Plugin object
                 instantiated from it.
        :rtype: tuple[Path, Plugin]
        :raises subprocess.CalledProcessError: If a subprocess fails.
        :raises FileNotFoundError: If the expected built and signed plugin JAR
                                   path is unexpectedly not found despite the
                                   build.
        """
        self._big_build(keystore_path, keystore_alias, keystore_password=keystore_password)
        return self._little_build(plugin_id)

    def model_post_init(self,
                        context: Any) -> None:
        """
        Pydantic post-initialization method to initialize the ``_built`` flag.

        :param context: The Pydantic context.
        :type context: Any
        """
        super().model_post_init(context)
        self._built = False

    def _big_build(self,
                   keystore_path: Path,
                   keystore_alias: str,
                   keystore_password: Optional[Callable[[], str]]=None) -> None:
        """
        Runs ``mvn package`` on the project if the ``_built`` flag is False.

        :param keystore_path: The path to the plugin signing keystore.
        :type keystore_path: Path
        :param keystore_alias: The alias to use in the plugin signing keystore.
        :type keystore_alias: str
        :param keystore_password: The plugin signing password.
        :type keystore_password:
        :raises subprocess.CalledProcessError: If a subprocess fails.
        """
        if not self._built:
            # Do build
            cmd = ['mvn', 'package',
                   f'-Dkeystore.file={keystore_path!s}',
                   f'-Dkeystore.alias={keystore_alias}']
            if keystore_password:
                cmd.extend(f'-Dkeystore.password={keystore_password()}')
            try:
                subprocess.run(cmd, cwd=self.get_root(), check=True, stdout=sys.stdout, stderr=sys.stderr)
            except subprocess.CalledProcessError as cpe:
                raise self._sanitize(cpe)
            self._built = True

    def _little_build(self,
                      plugin_id: PluginIdentifier) -> tuple[Path, Plugin]:
        """
        In the Maven implementation, essentially a no-op (keeping for parallel
        structure with the legacy Ant plugin set builder).

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :return: A tuple of the built and signed JAR file and a Plugin object
                 instantiated from it.
        :rtype: tuple[Path, Plugin]
        :raises FileNotFoundError: If the expected built and signed plugin JAR
                                   path is unexpectedly not found despite the
                                   build.
        """
        jar_path = self.get_root().joinpath('target', 'pluginjars', f'{plugin_id}.jar')
        if not jar_path.is_file():
            raise FileNotFoundError(str(jar_path))
        return jar_path, Plugin.from_jar(jar_path)

    def _sanitize(self,
                  called_process_error: subprocess.CalledProcessError) -> subprocess.CalledProcessError:
        """
        Alters the ``-Dkeystore.password=`` portion of a called process error.

        :param called_process_error: A called process error.
        :return: The same called process error, with ``-Dkeystore.password=``
                 altered in ``cmd``.
        """
        cmd = called_process_error.cmd[:]
        for i in range(len(cmd)):
            if cmd[i].startswith('-Dkeystore.password='):
                cmd[i] = '-Dkeystore.password=<password>'
        called_process_error.cmd = ' '.join([shlex.quote(c) for c in cmd])
        return called_process_error


class AntPluginSetBuilder(BasePluginSetBuilder):
    """
    A plugin set builder that uses `Java <https://www.oracle.com/java/>`_
    Development Kit (JDK) 8 and `Apache Ant <https://ant.apache.org/>`_,
    with the legacy LOCKSS 1.x build system.
    """

    #: Default value for the ``main`` field.
    DEFAULT_MAIN: ClassVar[str] = 'plugins/src'

    #: Default value for the ``test`` field.
    DEFAULT_TEST: ClassVar[str] = 'plugins/test/src'

    #: This plugin set builder's type.
    type: Literal['ant'] = Field(**BasePluginSetBuilder.TYPE_FIELD)

    #: This plugin set builder's main code path.
    main: str = Field(DEFAULT_MAIN,
                      **BasePluginSetBuilder.MAIN_FIELD)

    #: This plugin set builder's unit test path.
    test: str = Field(DEFAULT_TEST,
                      **BasePluginSetBuilder.TEST_FIELD)

    #: An internal flag to remember if a build has occurred.
    _built: bool

    def build_plugin(self,
                     plugin_id: PluginIdentifier,
                     keystore_path: Path,
                     keystore_alias: str,
                     keystore_password: Optional[Callable[[], str]]=None) -> tuple[Path, Plugin]:
        """
        Builds the given plugin with the supplied plugin signing credentials.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :param keystore_path: The path to the plugin signing keystore.
        :type keystore_path: Path
        :param keystore_alias: The alias to use in the plugin signing keystore.
        :type keystore_alias: str
        :param keystore_password: The plugin signing password.
        :type keystore_password: Optional[Callable[[], str]]
        :return: A tuple of the built and signed JAR file and a Plugin object
                 instantiated from it.
        :rtype: tuple[Path, Plugin]
        :raises Exception: If ``JAVA_HOME`` is not set in the environment.
        :raises subprocess.CalledProcessError: If a subprocess fails.
        :raises FileNotFoundError: If the expected built and signed plugin JAR
                                   path is unexpectedly not found despite the
                                   build.
        """
        # Prerequisites
        if 'JAVA_HOME' not in os.environ:
            raise Exception('error: JAVA_HOME must be set in your environment')
        # Big build (maybe)
        self._big_build()
        # Little build
        return self._little_build(plugin_id, keystore_path, keystore_alias, keystore_password=keystore_password)

    def model_post_init(self,
                        context: Any) -> None:
        """
        Pydantic post-initialization method to initialize the ``_built`` flag.

        :param context: The Pydantic context.
        :type context: Any
        """
        super().model_post_init(context)
        self._built = False

    def _big_build(self) -> None:
        """
        Runs ``ant load-plugins`` if the ``_built`` flag is False.

        :raises subprocess.CalledProcessError: If a subprocess fails.
        """
        if not self._built:
            # Do build
            subprocess.run('ant load-plugins',
                           shell=True, cwd=self.get_root(), check=True, stdout=sys.stdout, stderr=sys.stderr)
            self._built = True

    def _little_build(self,
                      plugin_id: PluginIdentifier,
                      keystore_path: Path,
                      keystore_alias: str,
                      keystore_password: Optional[Callable[[], str]]=None) -> tuple[Path, Plugin]:
        """
        Performs the "little build" of the given plugin.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :param keystore_path: The path to the plugin signing keystore.
        :type keystore_path: Path
        :param keystore_alias: The alias to use in the plugin signing keystore.
        :type keystore_alias: str
        :param keystore_password: The plugin signing password.
        :type keystore_password: Optional[Callable[[], str]]
        :return: A tuple of the built and signed JAR file and a Plugin object
                 instantiated from it.
        :rtype: tuple[Path, Plugin]
        :raises subprocess.CalledProcessError: If a subprocess fails.
        :raises FileNotFoundError: If the expected built and signed plugin JAR
                                   path is unexpectedly not found despite the
                                   build.
        """
        orig_plugin = None
        cur_id = plugin_id
        # Get all directories for jarplugin -d
        dirs = []
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
        jar_path = self.get_root().joinpath('plugins/jars', f'{plugin_id}.jar')
        jar_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ['test/scripts/jarplugin',
               '-j', str(jar_path),
               '-p', str(jar_fstr)]
        for d in dirs:
            cmd.extend(['-d', d])
        subprocess.run(cmd, cwd=self.get_root(), check=True, stdout=sys.stdout, stderr=sys.stderr)
        # Invoke signplugin
        cmd = ['test/scripts/signplugin',
               '--jar', str(jar_path),
               '--alias', keystore_alias,
               '--keystore', str(keystore_path)]
        if keystore_password:
            cmd.extend(['--password', keystore_password()])
        try:
            subprocess.run(cmd, cwd=self.get_root(), check=True, stdout=sys.stdout, stderr=sys.stderr)
        except subprocess.CalledProcessError as cpe:
            raise self._sanitize(cpe)
        if not jar_path.is_file():
            raise FileNotFoundError(str(jar_path))
        return jar_path, orig_plugin

    # def _plugin_path(self, plugin_id: PluginIdentifier) -> Path:
    #     return self.get_main().joinpath(Plugin.id_to_file(plugin_id))

    def _sanitize(self,
                  called_process_error: subprocess.CalledProcessError) -> subprocess.CalledProcessError:
        """
        Alters the value of ``--password`` in a called process error.

        :param called_process_error: A called process error.
        :return: The same called process error, with the value of ``--password``
                 altered in ``cmd``.
        """
        cmd = called_process_error.cmd[:]
        for i in range(1, len(cmd)):
            if cmd[i - 1] == '--password':
                cmd[i] = '<password>'
        called_process_error.cmd = ' '.join([shlex.quote(c) for c in cmd])
        return called_process_error


#: A type alias for plugin set builders, which is the union of
#: ``MavenPluginSetBuilder`` and ``AntPluginSetBuilder`` using ``type`` as the
#: discriminator field.
PluginSetBuilder = Annotated[Union[MavenPluginSetBuilder, AntPluginSetBuilder], Field(discriminator='type')]


#: A type alias for the plugin set kind.
PluginSetKind = Literal['PluginSet']


#: A type alias for plugin set identifiers.
PluginSetIdentifier = str


class PluginSet(BaseModel):
    """
    A Pydantic model for a plugin set.
    """

    #: This object's kind.
    kind: PluginSetKind = Field(title='Kind',
                                description="This object's kind")

    #: This plugin set's identifier.
    id: PluginSetIdentifier = Field(title='Plugin Set Identifier',
                                    description='An identifier for the plugin set')

    #: This plugin set's name.
    name: str = Field(title='Plugin Set Name',
                      description='A name for the plugin set')

    #: This plugin set's builder.
    builder: PluginSetBuilder = Field(title='Plugin Set Builder',
                                      description='A builder for the plugin set')

    def build_plugin(self,
                     plugin_id: PluginIdentifier,
                     keystore_path: Path,
                     keystore_alias: str,
                     keystore_password: Optional[Callable[[], str]]=None) -> tuple[Path, Plugin]:
        """
        Builds the given plugin with the supplied plugin signing credentials.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :param keystore_path: The path to the plugin signing keystore.
        :type keystore_path: Path
        :param keystore_alias: The alias to use in the plugin signing keystore.
        :type keystore_alias: str
        :param keystore_password: The plugin signing password.
        :type keystore_password: Optional[Callable[[], str]]
        :return: A tuple of the built and signed JAR file and a Plugin object
                 instantiated from it.
        """
        return self.builder.build_plugin(plugin_id, keystore_path, keystore_alias, keystore_password)

    def get_builder(self) -> PluginSetBuilder:
        """
        Returns this plugin set's builder.

        :return: This plugin set's builder.
        :rtype: PluginSetBuilder
        """
        return self.builder

    def get_id(self) -> PluginSetIdentifier:
        """
        Returns this plugin set's identifier.

        :return: This plugin set's identifier.
        :rtype: PluginSetIdentifier
        """
        return self.id

    def get_name(self) -> str:
        """
        Returns this plugin set's name.

        :return: This plugin set's name.
        :rtype: str
        """
        return self.name

    def has_plugin(self,
                   plugin_id: PluginIdentifier) -> bool:
        """
        Determines if the given plugin identifier represents a plugin that is
        present in the plugin set.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :return: Whether the plugin is present in the plugin set.
        :rtype: bool
        """
        return self.get_builder().has_plugin(plugin_id)

    def initialize(self,
                   root: Path) -> PluginSet:
        """
        Mandatory initialization of the builder.

        :param root: This plugin set's root path.
        :type root: Path
        :return: This plugin set, for chaining.
        :rtype: PluginSet
        """
        self.get_builder().initialize(root)
        return self

    def make_plugin(self,
                    plugin_id: PluginIdentifier) -> Plugin:
        """
        Makes a ``Plugin`` object from the given plugin identifier.

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :return: The corresponding ``Plugin`` object.
        :rtype: Plugin
        """
        return self.get_builder().make_plugin(plugin_id)

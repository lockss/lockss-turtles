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
Module to represent a LOCKSS plugin.
"""

# Remove in Python 3.14; see https://stackoverflow.com/a/33533514
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, AnyStr, IO, Optional
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import java_manifest
from lockss.pybasic.fileutil import path

from .util import PathOrStr


#: A type alias for plugin identifiers.
PluginIdentifier = str


class Plugin(object):
    """
    An object to represent a LOCKSS plugin.
    """

    def __init__(self, plugin_file: IO[AnyStr], plugin_path: PathOrStr) -> None:
        """
        Constructor.

        Other exceptions than ``RuntimeError`` may be raised if the plugin
        definition file cannot be parsed by ``xml.etree.ElementTree``.

        :param plugin_file: An open file-like object that can read the plugin
                            definition file.
        :type plugin_file: IO[AnyStr]
        :param plugin_path: A string (or Path) representing the hierarchical
                            path of the plugin definition file (as a real file,
                            or as a file entry in a JAR file).
        :type plugin_path: PathOrStr
        :raises RuntimeError: If the plugin definition file parses as XML but
                              the top-level element is not <map>.
        """
        super().__init__()
        self._path = plugin_path
        self._parsed = ET.parse(plugin_file).getroot()
        tag = self._parsed.tag
        if tag != 'map':
            raise RuntimeError(f'{plugin_path!s}: invalid root element: {tag}')

    def get_aux_packages(self) -> list[str]:
        """
        Returns the (possibly empty) list of auxiliary code packages declared by
        the plugin (``plugin_aux_packages``).

        :return: A non-null list of strings representing auxiliary code
                 packages.
        :rtype: list[str]
        """
        key = 'plugin_aux_packages'
        lst = [x[1] for x in self._parsed.findall('entry') if x[0].tag == 'string' and x[0].text == key]
        if lst is None or len(lst) < 1:
            return []
        if len(lst) > 1:
            raise ValueError(f'plugin declares {len(lst)} entries for {key}')
        return [x.text for x in lst[0].findall('string')]

    def get_identifier(self) -> Optional[PluginIdentifier]:
        """
        Get this plugin's identifier (``plugin_identifier``).

        :return: A plugin identifier, or None if missing.
        :rtype: Optional[PluginIdentifier]
        :raises ValueError: If the plugin definition contains more than one.
        """
        return self._only_one('plugin_identifier')

    def get_name(self) -> Optional[str]:
        """
        Get this plugin's name (``plugin_name``).

        :return: A plugin name, or None if missing.
        :rtype: Optional[str]
        :raises ValueError: If the plugin definition contains more than one.
        """
        return self._only_one('plugin_name')

    def get_parent_identifier(self) -> Optional[PluginIdentifier]:
        """
        Get this plugin's parent identifier (``plugin_parent``).

        :return: A parent plugin identifier, or None if this plugin has no
                 parent.
        :rtype: Optional[PluginIdentifier]
        :raises ValueError: If the plugin definition contains more than one.
        """
        return self._only_one('plugin_parent')

    def get_parent_version(self) -> Optional[int]:
        """
        Get this plugin's parent version (``plugin_parent_version``).

        :return: A parent plugin version, or None if this plugin has no
                 parent.
        :rtype: Optional[int]
        :raises ValueError: If the plugin definition contains more than one.
        """
        return self._only_one('plugin_parent_version', int)

    def get_version(self) -> Optional[int]:
        """
        Get this plugin's version (``plugin_version``).

        :return: A plugin version, or None if missing.
        :rtype: Optional[int]
        :raises ValueError: If the plugin definition contains more than one.
        """
        return self._only_one('plugin_version', int)

    def _only_one(self, key: str, result: Callable[[str], Any]=str) -> Optional[Any]:
        """
        Retrieves the value of a given key in the plugin definition, optionally
        coerced into a representation (by default simply a string).

        :param key: A plugin key.
        :param key: str
        :param result: A functor that takes a string and returns the desired
                       representation; by default this is the string constructor
                       ``str``, meaning by default the string values are
                       returned unchanged.
        :param result: Callable[[str], Any]
        :return: The value for the given key, coerced through the given functor,
                 or None if the plugin definition does not contain any entry
                 with the given key.
        :rtype: Optional[Any]
        :raises ValueError: If the plugin definition contains more than one
                            entry with the given key.
        """
        lst = [x[1].text for x in self._parsed.findall('entry') if x[0].tag == 'string' and x[0].text == key]
        if lst is None or len(lst) < 1:
            return None
        if len(lst) > 1:
            raise ValueError(f'plugin declares {len(lst)} entries for {key}')
        return result(lst[0])

    @staticmethod
    def from_jar(jar_path_or_str: PathOrStr) -> Plugin:
        """
        Instantiates a Plugin object from the given plugin JAR file.

        :param jar_path_or_str: The path to a plugin JAR.
        :type jar_path_or_str: PathOrStr
        :return: A Plugin object.
        :rtype: Plugin
        """
        jar_path = path(jar_path_or_str)
        plugin_id = Plugin.id_from_jar(jar_path)
        plugin_fstr = str(Plugin.id_to_file(plugin_id))
        with ZipFile(jar_path, 'r') as zip_file:
            with zip_file.open(plugin_fstr, 'r') as plugin_file:
                return Plugin(plugin_file, plugin_fstr)

    @staticmethod
    def from_path(path_or_str: PathOrStr) -> Plugin:
        """
        Instantiates a Plugin object from the given plugin file.

        :param path_or_str: The path to a plugin file.
        :type path_or_str: PathOrStr
        :return: A Plugin object.
        :rtype: Plugin
        """
        fpath = path(path_or_str)
        with fpath.open('r') as input_file:
            return Plugin(input_file, fpath)

    @staticmethod
    def file_to_id(plugin_fstr: str) -> PluginIdentifier:
        """
        Converts a plugin file path (ending in ``.xml``) to the implied plugin
        identifier (e.g. ``org/myproject/plugin/MyPlugin.xml`` implies
        ``org.myproject.plugin.MyPlugin``).

        See also ``id_to_file``.

        :param plugin_fstr: A string file path.
        :type plugin_fstr: str
        :return: A plugin identifier.
        :rtype: PluginIdentifier
        """
        return plugin_fstr.replace('/', '.')[:-4]  # 4 is len('.xml')

    @staticmethod
    def id_from_jar(jar_path_or_str: PathOrStr) -> PluginIdentifier:
        """
        Extracts the plugin identifier from a plugin JAR's manifest file.

        :param jar_path_or_str: The path to a plugin JAR.
        :type jar_path_or_str: PathOrStr
        :return: The plugin identifier extracted from the given plugin JAR's
                 manifest file.
        :rtype: PluginIdentifier
        :raises Exception: If the JAR's manifest file has no entry with
                           ``Lockss-Plugin`` equal to ``true`` and ``Name``
                           equal to the packaged plugin's identifier.
        """
        jar_path = path(jar_path_or_str)
        manifest = java_manifest.from_jar(jar_path)
        for entry in manifest:
            if entry.get('Lockss-Plugin') == 'true':
                name = entry.get('Name')
                if name is None:
                    raise Exception(f'{jar_path!s}: Lockss-Plugin entry in META-INF/MANIFEST.MF has no Name value')
                return Plugin.file_to_id(name)
        else:
            raise Exception(f'{jar_path!s}: no Lockss-Plugin entry in META-INF/MANIFEST.MF')

    @staticmethod
    def id_to_dir(plugin_id: PluginIdentifier) -> Path:
        """
        Returns the path of the directory containing the given plugin identifier
        (for example ``org/myproject/plugin`` for
        ``org.myproject.plugin.MyPlugin``).

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :return: The directory path containing the given plugin identifier.
        :rtype: Path
        """
        return Plugin.id_to_file(plugin_id).parent

    @staticmethod
    def id_to_file(plugin_id: PluginIdentifier) -> Path:
        """
        Returns the path of the definition file corresponding to the given
        plugin identifier (for example ``org/myproject/plugin/MyPlugin.xml`` for
        ``org.myproject.plugin.MyPlugin``).

        :param plugin_id: A plugin identifier.
        :type plugin_id: PluginIdentifier
        :return: The path of the definition file corresponding to the given
                 plugin identifier.
        :rtype: Path
        """
        return Path(f'{plugin_id.replace(".", "/")}.xml')

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

from pathlib import Path
import xml.etree.ElementTree
import zipfile

import java_manifest

from lockss.turtles.util import _path


class Plugin(object):

    @staticmethod
    def from_jar(jar_path):
        jar_path = _path(jar_path)  # in case it's a string
        plugin_id = Plugin.id_from_jar(jar_path)
        plugin_fstr = str(Plugin.id_to_file(plugin_id))
        with zipfile.ZipFile(jar_path, 'r') as zip_file:
            with zip_file.open(plugin_fstr, 'r') as plugin_file:
                return Plugin(plugin_file, plugin_fstr)

    @staticmethod
    def from_path(path):
        path = _path(path)  # in case it's a string
        with open(path, 'r') as input_file:
            return Plugin(input_file, path)

    @staticmethod
    def file_to_id(plugin_fstr):
        return plugin_fstr.replace('/', '.')[:-4]  # 4 is len('.xml')

    @staticmethod
    def id_from_jar(jar_path):
        jar_path = _path(jar_path)  # in case it's a string
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
    def id_to_dir(plugin_id):
        return Plugin.id_to_file(plugin_id).parent

    @staticmethod
    def id_to_file(plugin_id):
        return Path(f'{plugin_id.replace(".", "/")}.xml')

    def __init__(self, plugin_file, plugin_path):
        super().__init__()
        self._path = plugin_path
        self._parsed = xml.etree.ElementTree.parse(plugin_file).getroot()
        tag = self._parsed.tag
        if tag != 'map':
            raise RuntimeError(f'{plugin_path!s}: invalid root element: {tag}')

    def get_identifier(self):
        return self._only_one('plugin_identifier')

    def get_name(self):
        return self._only_one('plugin_name')

    def get_parent_identifier(self):
        return self._only_one('plugin_parent')

    def get_parent_version(self):
        return self._only_one('plugin_parent_version', int)

    def get_version(self):
        return self._only_one('plugin_version', int)

    def _only_one(self, key, result=str):
        lst = [x[1].text for x in self._parsed.findall('entry') if x[0].tag == 'string' and x[0].text == key]
        if lst is None or len(lst) < 1:
            return None
        if len(lst) > 1:
            raise ValueError(f'plugin declares {len(lst)} entries for {key}')
        return result(lst[0])

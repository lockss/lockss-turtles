#!/usr/bin/env python3

__copyright__ = '''\
Copyright (c) 2000-2022, Board of Trustees of Leland Stanford Jr. University
'''

__license__ = '''\
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation
and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
may be used to endorse or promote products derived from this software without
specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
'''

__version__ = '0.1.0-dev'

import argparse
import getpass
import os
from pathlib import Path
import subprocess
import sys
import xdg
import xml.etree.ElementTree as ET
import yaml

class Plugin(object):

    @staticmethod
    def id_to_file(plugid):
        return Path('{}.xml'.format(plugid.replace('.', '/')))

    @staticmethod
    def id_to_dir(plugid):
        return Plugin.id_to_file(plugid).parent

    def __init__(self, path):
        super().__init__()
        self._path = path
        self._parsed = ET.parse(path).getroot()
        tag = self._parsed.tag
        if tag != 'map':
            raise RuntimeError('invalid root element: {}'.format(tag))

    def identifier(self):
        return self._only_one('plugin_identifier')

    def parent_identifier(self):
        return self._only_one('plugin_parent')

    def parent_version(self):
        return self._only_one('plugin_parent_version', int)

    def version(self):
        return self._only_one('plugin_version', int)

    def _only_one(self, key, result=str):
        lst = [x[1].text for x in self._parsed.findall('entry') if x[0].tag == 'string' and x[0].text == key]
        if lst is None or len(lst) < 1:
            return None
        if len(lst) > 1:
            raise ValueError('plugin declares {} entries for {}'.format(len(lst), key))
        return result(lst[0])

class PluginSet(object):

    TYPE_ANT = 'ant'
    TYPE_MVN = 'mvn'

    @staticmethod
    def from_path(path):
        path = Path(path) # in case it's a string
        with path.open('r') as f:
            return [PluginSet.from_yaml(parsed, path) for parsed in yaml.safe_load_all(f)]

    @staticmethod
    def from_yaml(parsed, path):
        if parsed.get('kind') != 'PluginSet':
            raise RuntimeError('{} is not of kind "PluginSet"'.format(path))
        if 'builder' not in parsed:
            raise RuntimeError('{} does not define "builder"'.format(path))
        typ = parsed.get('builder').get('type')
        if typ == PluginSet.TYPE_ANT:
            return AntPluginSet(parsed, path)
        elif typ == PluginSet.TYPE_MVN:
            raise NotImplementedError('the plugin set builder type "mvn" is not implemented yet')
        else:
            raise RuntimeError('unknown plugin set builder type: {}'.format(typ))

    def __init__(self, parsed):
        super().__init__()
        self._parsed = parsed
    
    def build_plugin(self, plugid, keystore, alias, password=None):
        raise NotImplementedError('build_plugin')
        
    def has_plugin(self, plugid):
        raise NotImplementedError('has_plugin')
        
    def make_plugin(self, plugid):
        raise NotImplementedError('make_plugin')

    def name(self):
        return self._parsed['name']
    
    def type(self):
        return self._parsed['type']
    
#
# class _AntPluginSet
#
class AntPluginSet(PluginSet):
        
    def __init__(self, parsed, path):
        super().__init__(parsed)
        self._root = path.parent
        self._cache = dict()
        
    def build_plugin(self, plugid, keystore, alias, password=None):
        # Get all directories for jarplugin -d
        curid = plugid
        dirs = list()
        while curid is not None:
            curdir = Plugin.id_to_dir(curid)
            if curdir not in dirs:
                dirs.append(curdir)
            curid = self.make_plugin(curid).parent_identifier()
        dirs = [str(i).replace('.', '/') for i in dirs]
        # Invoke jarplugin
        plugfile = Plugin.id_to_file(plugid)
        plugjar = self.root_path().joinpath('plugins/jars', '{}.jar'.format(plugfile.stem))
        plugjar.parent.mkdir(parents=True, exist_ok=True)
        cmd = ['test/scripts/jarplugin',
               '-j', str(plugjar),
                '-p', str(plugfile)]
        for dir in dirs:
            cmd.extend(['-d', dir])
        subprocess.run(cmd, cwd=self.root_path(), check=True, stdout=sys.stdout, stderr=sys.stderr)
        # Invoke signplugin
        cmd = ['test/scripts/signplugin',
               '--jar', str(plugjar),
               '--alias', alias,
               '--keystore', keystore]
        if password is not None:
            cmd.extend(['--password', password])
        subprocess.run(cmd, cwd=self.root_path(), check=True, stdout=sys.stdout, stderr=sys.stderr)
        if not plugjar.exists():
            raise FileNotFoundError(str(plugjar))
        return plugjar

    def has_plugin(self, plugid):
        return self._plugin_path(plugid).exists()
        
    def main(self):
        return self._parsed.get('main', 'plugins/src')
        
    def main_path(self):
        return self.root_path().joinpath(self.main())
        
    def make_plugin(self, plugid):
        ret = self._cache.get(plugid)
        if ret is None:
            ret = Plugin(self._plugin_path(plugid))
            self._cache[plugid] = ret
        return ret
        
    def root(self):
        return self._root
    
    def root_path(self):
        return Path(self.root()).expanduser().resolve()
        
    def test(self):
        return self._parsed.get('test', 'plugins/test/src')
        
    def test_path(self):
        return self.root_path().joinpath(self.test())
        
    def _plugin_path(self, plugid):
        return Path(self.main_path()).joinpath(Plugin.id_to_file(plugid))

class Tortuga(object):
    
    XDG_DIR='tortuga'
    CONFIG_DIR=xdg.xdg_config_home().joinpath(XDG_DIR)
    SETTINGS=CONFIG_DIR.joinpath('settings.yaml')

    def __init__(self):
        super().__init__()

    def do_build_one_plugin(self, plugid):
        for plugin_set in self.plugin_sets:
           if plugin_set.has_plugin(plugid):
               return plugin_set.build_plugin(plugid,
                                              self.settings['plugin-signing-keystore'],
                                              self.settings['plugin-signing-alias'],
                                              self._password)
        else:
            sys.exit('error: {} not found in any plugin set'.format(plugid))

    def do_build_plugin(self):
        # Prerequisites
        for x in ['plugin-signing-keystore', 'plugin-signing-alias']:
            if x not in self.settings:
                sys.exit('error: {} must be set in your settings'.format(x))
        self.load_plugin_sets()
        if not self.no_deploy:
            self.load_plugin_registries()
        if 'JAVA_HOME' not in os.environ:
            sys.exit('error: JAVA_HOME must be set in your environment')
        # Build plugins
        return [self.do_build_one_plugin(plugid) for plugid in self.plugin_identifiers]

    def initialize(self):
        parser = self.make_parser()
        args = parser.parse_args()
        #
        # One-and-done block
        #
        if args.copyright:
            print(__copyright__)
            parser.exit()
        # --help/-h is automatic
        if args.license:
            print(__license__)
            parser.exit()
        if args.usage:
            parser.print_usage()
            parser.exit()
        # --version is automatic
        #
        # --build-plugin block
        #
        if args.build_plugin:
            # --build-plugin -> build_plugin
            self.build_plugin = args.build_plugin
            # --no-deploy -> no_deploy
            self.no_deploy = args.no_deploy
            # --plugin-identifier -> plugin_identifiers
            self.plugin_identifiers = args.plugin_identifier or list()
            if len(self.plugin_identifiers) == 0:
                parser.error('list of plugins to build is empty')
            # --password -> _password
            self._password = args.password or getpass.getpass('Plugin signing keystore password: ')
        #
        # Configuration block
        #
        # --settings -> settings_path
        self.settings_path = args.settings
        #
        # Internal: settings, plugin_sets
        #
        self.settings = None
        self.plugin_sets = None
        self.plugin_registries = None

    def load_plugin_registries(self):
        if self.plugin_registries is None:
            pass ##FIXME

    def load_plugin_sets(self):
        if self.plugin_sets is None:
            if 'plugin-sets' not in self.settings:
                sys.exit('error: plugin-sets must be set in your settings')
            self.plugin_sets = list()
            for path in self.settings['plugin-sets']:
                self.plugin_sets.extend(PluginSet.from_path(path))

    def load_settings(self):
        with self.settings_path.open('r') as s:
            self.settings = yaml.safe_load(s)
            if self.settings.get('kind') != 'Settings':
                sys.exit('error: {} is not of kind "Settings"'.format(self.settings_path))

    def make_parser(self):
        # Make parser
        usage = '''
    %(prog)s --build-plugin --plugin-identifier=PLUG [--settings=FILE]
    %(prog)s (--copyright|--help|--license|--usage|--version)'''
        parser = argparse.ArgumentParser(usage=usage, add_help=False)
        # Mutually exclusive commands
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--build-plugin', action='store_true', help='build and deploy plugins')
        group.add_argument('--copyright', action='store_true', help='show copyright and exit')
        group.add_argument('--help', '-h', action='help', help='show this help message and exit')
        group.add_argument('--license', action='store_true', help='show license and exit')
        group.add_argument('--usage', action='store_true', help='show usage information and exit')
        group.add_argument('--version', action='version', version=__version__)
        # --build-plugin group
        group = parser.add_argument_group('Build and deploy plugins (--build-plugin)')
        group.add_argument('--no-deploy', action='store_true', help='only build plugins, do not deploy')
        group.add_argument('--password', metavar='PASS', help='use %(metavar)s as the plugin signing keystore password (default: interactive prompt)')
        group.add_argument('--plugin-identifier', metavar='PLUG', action='append', help='add %(metavar)s to the list of plugin identifiers to build')
        # Config group
        group = parser.add_argument_group('Configuration')
        group.add_argument('--settings', metavar='FILE', type=Path, default=Tortuga.SETTINGS, help='load settings from %(metavar)s (default: %(default)s)')
        # Return parser
        return parser

    def run(self):
        self.initialize()
        self.load_settings()
        if self.build_plugin:
            ret = self.do_build_plugin()
            print(ret) # FIXME
        else:
            raise RuntimeError('no command to dispatch')

#
# Main entry point
#

if __name__ == '__main__': Tortuga().run()


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

class _Plugin(object):

    @staticmethod
    def id_to_file(plugid):
        return Path('{}.xml'.format(plugid.replace('.', '/')))

    @staticmethod
    def id_to_dir(plugid):
        return _Plugin.id_to_file(plugid).parent

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

class _PluginSet(object):

    TYPE_ANT = 'ant'
    TYPE_MVN = 'mvn'

    @staticmethod
    def from_path(path):
        path = Path(path) # in case it's a string
        with path.open('r') as f:
            return [_PluginSet.from_yaml(parsed, path) for parsed in yaml.safe_load_all(f)]

    @staticmethod
    def from_yaml(parsed, path):
        if parsed.get('kind') != 'PluginSet':
            raise RuntimeError('{} is not of kind "PluginSet"'.format(path))
        if 'builder' not in parsed:
            raise RuntimeError('{} does not define "builder"'.format(path))
        typ = parsed.get('builder').get('type')
        if typ == _PluginSet.TYPE_ANT:
            return _AntPluginSet(parsed, path)
        elif typ == _PluginSet.TYPE_MVN:
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
class _AntPluginSet(_PluginSet):
        
    def __init__(self, parsed, path):
        super().__init__(parsed)
        self._root = path.parent
        self._cache = dict()
        
    def build_plugin(self, plugid, keystore, alias, password=None):
        # Get all directories for jarplugin -d
        curid = plugid
        dirs = list()
        while curid is not None:
            curdir = _Plugin.id_to_dir(curid)
            if curdir not in dirs:
                dirs.append(curdir)
            curid = self.make_plugin(curid).parent_identifier()
        dirs = [str(i).replace('.', '/') for i in dirs]
        # Invoke jarplugin
        plugfile = _Plugin.id_to_file(plugid)
        plugjar = self.root_path().joinpath('plugins/jars', '{}.jar'.format(plugfile.stem))
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
            ret = _Plugin(self._plugin_path(plugid))
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
        return Path(self.main_path()).joinpath(_Plugin.id_to_file(plugid))
    
class _TortugaOptions(object):
    
    XDG_DIR='tortuga'
    CONFIG_DIR=xdg.xdg_config_home().joinpath(XDG_DIR)
    SETTINGS=CONFIG_DIR.joinpath('settings.yaml')
    
    @staticmethod
    def make_parser():
        # Make parser
        usage = '''
    %(prog)s --build-plugin --plugin-identifier=PLUG [--settings=FILE]
    %(prog)s (--copyright|--help|--license|--usage|--version)'''
        parser = argparse.ArgumentParser(usage=usage, add_help=False)
        # Mutually exclusive commands
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--build-plugin', action='store_true', help='build plugins')
        group.add_argument('--copyright', action='store_true', help='show copyright and exit')
        group.add_argument('--help', '-h', action='help', help='show this help message and exit')
        group.add_argument('--license', action='store_true', help='show license and exit')
        group.add_argument('--usage', action='store_true', help='show usage information and exit')
        group.add_argument('--version', action='version', version=__version__)
        # --build-plugin group
        group = parser.add_argument_group('Build a plugin (--build-plugin)')
        group.add_argument('--no-publish', action='store_true', help='only build plugins, do not publish')
        group.add_argument('--password', metavar='PASS', help='use %(metavar)s as the plugin signing keystore password (default: interactive prompt)')
        group.add_argument('--plugin-identifier', metavar='PLUG', action='append', help='add %(metavar)s to the list of plugin identifiers to build')
        # Config group
        group = parser.add_argument_group('Configuration')
        group.add_argument('--settings', metavar='FILE', type=Path, default=_TortugaOptions.SETTINGS, help='load settings from %(metavar)s (default: %(default)s)')
        # Return parser
        return parser
    
    def __init__(self, parser, args):
        super().__init__()
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
            # --no-publish -> no_publish
            self.no_publish = args.no_publish
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
        # Internal: settings, plugin_sets
        self.settings = None
        self.plugin_sets = None

def _build_one_plugin(options, plugid):
    for plugin_set in options.plugin_sets:
       if plugin_set.has_plugin(plugid):
           return plugin_set.build_plugin(plugid,
                                          options.settings['plugin-signing-keystore'],
                                          options.settings['plugin-signing-alias'],
                                          options._password)
    else:
        sys.exit('error: {} not found in any plugin set'.format(plugid))

def _build_plugin(options):
    # Prerequisites
    for x in ['plugin-signing-keystore', 'plugin-signing-alias']:
        if x not in options.settings:
            sys.exit('error: {} must be set in your settings'.format(x))
    _load_plugin_sets(options)
    if not options.no_publish:
        _load_plugin_registries(options)
    if 'JAVA_HOME' not in os.environ:
        sys.exit('error: JAVA_HOME must be set in your environment')
    # Build plugins
    return [_build_one_plugin(options, plugid) for plugid in options.plugin_identifiers]

def _load_plugin_registries(options):
    if options.plugin_registries is None:
        pass ##FIXME

def _load_plugin_sets(options):
    if options.plugin_sets is None:
        if 'plugin-sets' not in options.settings:
            sys.exit('error: plugin-sets must be set in your settings')
        options.plugin_sets = list()
        for path in options.settings['plugin-sets']:
            options.plugin_sets.extend(_PluginSet.from_path(path))

def _load_settings(options):
    if options.settings is None:
        with options.settings_path.open('r') as s:
            options.settings = yaml.safe_load(s)
            if options.settings.get('kind') != 'Settings':
                sys.exit('error: {} is not of kind "Settings"'.format(options.settings_path))

#
# Main driver
#

def _dispatch(options):
    _load_settings(options)
    if options.build_plugin:
        ret = _build_plugin(options)
        print(ret) # FIXME
    else:
        raise RuntimeError('no command to dispatch')

def _main():
    '''Main method.'''
    # Parse command line
    parser = _TortugaOptions.make_parser()
    args = parser.parse_args()
    options = _TortugaOptions(parser, args)
    _dispatch(options)

if __name__ == '__main__': _main()


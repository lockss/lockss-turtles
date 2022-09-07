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
from pathlib import Path, PurePath
import shutil
import subprocess
import sys
import xdg
import xml.etree.ElementTree as ET
import yaml

def _path(purepath_or_string):
    if issubclass(type(purepath_or_string), PurePath):
        return purepath_or_string
    else:
        return Path(purepath_or_string).expanduser().resolve() 

class Plugin(object):

    _cache = dict()

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
            raise RuntimeError('{}: invalid root element: {}'.format(path, tag))
        Plugin._cache.setdefault(self.identifier(), self)

    def name(self):
        return self._only_one('plugin_name')

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

class PluginRegistry(object):
    
    KIND = 'PluginRegistry'
    
    @staticmethod
    def from_path(path):
        path = _path(path)
        with path.open('r') as f:
            return [PluginRegistry.from_yaml(parsed, path) for parsed in yaml.safe_load_all(f)]

    @staticmethod
    def from_yaml(parsed, path):
        kind = parsed.get('kind')
        if kind is None:
            raise RuntimeError('{}: undefined kind'.format(path)) 
        elif kind != PluginRegistry.KIND:
            raise RuntimeError('{}: not of kind {}: {}'.format(path, PluginRegistry.KIND, kind))
        layout = parsed.get('layout')
        if layout is None:
            raise RuntimeError('{}: undefined layout'.format(path))
        elif layout == RcsPluginRegistry.LAYOUT:
            return RcsPluginRegistry(parsed)
        else:
            raise RuntimeError('{}: unknown layout: {}'.format(path, layout))

    def __init__(self, parsed):
        super().__init__()
        self._parsed = parsed

    def deploy_plugin(self, plugid, srcpath, testing=False, production=False, interactive=False):
        raise NotImplementedError('deploy_plugin')
        
    def has_plugin(self, plugid):
        return plugid in self.plugin_identifiers()
        
    def layout(self):
        return self._parsed['layout']
    
    def name(self):
        return self._parsed['name']
    
    def plugin_identifiers(self):
        return self._parsed['plugin-identifiers']
    
    def prod_path(self):
        return _path(self._parsed['prod'])
    
    def test_path(self):
        return _path(self._parsed.get('test'))
    
class RcsPluginRegistry(PluginRegistry):
    
    LAYOUT = 'rcs'

    def __init__(self, parsed):
        super().__init__(parsed)

    def deploy_plugin(self, plugid, srcpath, testing=False, production=False, interactive=False):
        if not (testing or production):
            raise RuntimeError('must deploy to at least one of testing or production')
        if testing:
            self.do_deploy_plugin(plugid, srcpath, self.test_path(), interactive)
        if production:
            self.do_deploy_plugin(plugid, srcpath, self.prod_path(), interactive)

    def do_deploy_plugin(self, plugid, srcpath, regpath, interactive=False):
        plugin = Plugin._cache[plugid]
        filestr = srcpath.name
        dstpath = Path(regpath, filestr)
        do_chcon = (subprocess.run('command -v selinuxenabled && selinuxenabled && command -v chcon', shell=True).returncode == 0)
        is_new = not dstpath.exists()
        if is_new:
            if interactive:
                i = input('{} does not exist in {}; create it (y/n)? [n] '.format(dstpath, self.name())).lower() or 'n'
                if i != 'y':
                    return
        else:
            cmd = ['co', '-l', filestr]
            subprocess.run(cmd, check=True, cwd=str(regpath))
        shutil.copy(str(srcpath), str(dstpath))
        if do_chcon:
            cmd = ['chcon', '-t', 'httpd_sys_content_t', filestr]
            subprocess.run(cmd, check=True, cwd=str(regpath))
        cmd = ['ci', '-u', '-mVersion {}'.format(plugin.version())]
        if is_new:
            cmd.append('-t-{}'.format(plugin.name())) 
        cmd.append(filestr)
        subprocess.run(cmd, check=True, cwd=str(regpath))
        
class PluginSet(object):

    KIND = 'PluginSet'

    @staticmethod
    def from_path(path):
        path = _path(path)
        with path.open('r') as f:
            return [PluginSet.from_yaml(parsed, path) for parsed in yaml.safe_load_all(f)]

    @staticmethod
    def from_yaml(parsed, path):
        kind = parsed.get('kind')
        if kind is None:
            raise RuntimeError('{}: undefined kind'.format(path)) 
        elif kind != PluginSet.KIND:
            raise RuntimeError('{}: not of kind {}: {}'.format(path, PluginSet.KIND, kind))
        builder = parsed.get('builder')
        if builder is None:
            raise RuntimeError('{}: undefined builder'.format(path))
        typ = builder.get('type')
        if typ is None:
            raise RuntimeError('{}: undefined builder type'.format(path))
        elif typ == AntPluginSet.TYPE:
            return AntPluginSet(parsed, path)
        elif typ == 'mvn':
            raise NotImplementedError('{}: the builder type mvn is not implemented yet')
        else:
            raise RuntimeError('{}: unknown builder type: {}'.format(path, typ))

    def __init__(self, parsed):
        super().__init__()
        self._parsed = parsed
    
    def build_plugin(self, plugid, keystore, alias, password=None):
        raise NotImplementedError('build_plugin')
        
    def builder_type(self):
        return self._parsed['builder']['type']
    
    def has_plugin(self, plugid):
        raise NotImplementedError('has_plugin')
        
    def make_plugin(self, plugid):
        raise NotImplementedError('make_plugin')

    def name(self):
        return self._parsed['name']
    
#
# class _AntPluginSet
#
class AntPluginSet(PluginSet):

    TYPE = 'ant'
        
    def __init__(self, parsed, path):
        super().__init__(parsed)
        self._root = path.parent
        
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
               '--keystore', str(keystore)]
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
        return Plugin._cache.get(plugid) or Plugin(self._plugin_path(plugid))
        
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

class Turtles(object):
    
    XDG_NAME='turtles'
    XDG_CONFIG_DIR=xdg.xdg_config_home().joinpath(XDG_NAME)
    GLOBAL_CONFIG_DIR=Path('/etc', XDG_NAME)
    CONFIG_DIRS=[XDG_CONFIG_DIR, GLOBAL_CONFIG_DIR]

    PLUGIN_REGISTRIES='plugin-registries.yaml'
    PLUGIN_SETS='plugin-sets.yaml'
    SETTINGS='settings.yaml'

    def __init__(self):
        super().__init__()

    def config_files(self, filename):
        return [Path(base, filename) for base in Turtles.CONFIG_DIRS]

    def do_build_plugin(self, plugid):
        for plugin_set in self.plugin_sets:
           if plugin_set.has_plugin(plugid):
               return plugin_set.build_plugin(plugid,
                                              _path(self.settings['plugin-signing-keystore']),
                                              self.settings['plugin-signing-alias'],
                                              self._password)
        else:
            sys.exit('error: {} not found in any plugin set'.format(plugid))

    def do_deploy_plugin(self, plugid, jarpath):
        # Prerequisites
        
        atleast1 = False
        for plugin_registry in self.plugin_registries:
            if plugin_registry.has_plugin(plugid):
                plugin_registry.deploy_plugin(plugid,
                                              jarpath,
                                              testing=self.testing,
                                              production=self.production,
                                              interactive=self.interactive)
                atleast1 = True
        if not atleast1:
            sys.exit('error: {} is not declared in any plugin registry')

    def do_release_plugin(self):
        # Prerequisites
        for setting in ['plugin-signing-keystore', 'plugin-signing-alias']:
            if setting not in self.settings:
                sys.exit('error: {} must be set in your settings'.format(setting))
        self.load_plugin_sets()
        if not self.no_deploy:
            self.load_plugin_registries()
        if 'JAVA_HOME' not in os.environ:
            sys.exit('error: JAVA_HOME must be set in your environment')
        # Build plugins
        plugid_jarpath_tuples = [(plugid, self.do_build_plugin(plugid)) for plugid in self.plugin_identifiers]
        if not self.no_deploy:
            for plugid, jarpath in plugid_jarpath_tuples:
                self.do_deploy_plugin(plugid, jarpath)

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
        # --release-plugin block
        #
        if args.release_plugin:
            # --release-plugin -> release_plugin
            self.release_plugin = args.release_plugin
            # --no-deploy -> no_deploy
            self.no_deploy = args.no_deploy
            # --plugin-identifier -> plugin_identifiers
            self.plugin_identifiers = args.plugin_identifier or list()
            if len(self.plugin_identifiers) == 0:
                parser.error('list of plugins to build is empty')
            # --testing -> testing
            self.testing = args.testing
            # --production -> production
            self.production = args.production
            # --password -> _password
            self._password = args.password or getpass.getpass('Plugin signing keystore password: ')

        #
        # Configuration block
        #
        # --interactive/--non-interactive -> interactive
        self.interactive = args.interactive
        # --plugin-registries -> plugin_registries_path
        self.plugin_registries_path = args.plugin_registries or self.select_config_file(Turtles.PLUGIN_REGISTRIES)
        # --plugin-sets -> plugin_sets_path
        self.plugin_sets_path = args.plugin_sets or self.select_config_file(Turtles.PLUGIN_SETS)
        # --settings -> settings_path
        self.settings_path = args.settings or self.select_config_file(Turtles.SETTINGS)
        
        #
        # Internal: settings, plugin_sets
        #
        self.settings = None
        self.plugin_sets = None
        self.plugin_registries = None

    def list_config_files(self, filename):
        return ' or '.join(str(x) for x in self.config_files(filename))

    def load_plugin_registries(self):
        if self.plugin_registries is None:
            parsed = None
            with self.plugin_registries_path.open('r') as f:
                parsed = yaml.safe_load(f)
            kind = parsed.get('kind')
            if kind is None:
                sys.exit('{}: undefined kind'.format(self.plugin_registries_path))
            elif kind != 'Settings':
                sys.exit('{}: not of kind Settings: {}'.format(self.plugin_registries_path, kind))
            paths = parsed.get('plugin-registries')
            if paths is None:
                sys.exit('{}: undefined plugin-registries'.format(self.plugin_registries_path))
            self.plugin_registries = list()
            for path in paths:
                self.plugin_registries.extend(PluginRegistry.from_path(path))

    def load_plugin_sets(self):
        if self.plugin_sets is None:
            parsed = None
            with self.plugin_sets_path.open('r') as f:
                parsed = yaml.safe_load(f)
            kind = parsed.get('kind')
            if kind is None:
                sys.exit('{}: undefined kind'.format(self.plugin_sets_path))
            elif kind != 'Settings':
                sys.exit('{}: not of kind Settings: {}'.format(self.plugin_sets_path, kind))
            paths = parsed.get('plugin-sets')
            if paths is None:
                sys.exit('{}: undefined plugin-sets'.format(self.plugin_sets_path))
            self.plugin_sets = list()
            for path in paths:
                self.plugin_sets.extend(PluginSet.from_path(path))

    def load_settings(self):
        if self.settings is None:
            with self.settings_path.open('r') as f:
                self.settings = yaml.safe_load(f)
            kind = self.settings.get('kind')
            if kind is None:
                sys.exit('{}: undefined kind'.format(self.settings_path))
            elif kind != 'Settings':
                sys.exit('{}: not of kind Settings: {}'.format(self.settings_path, kind))

    def make_parser(self):
        # Make parser
        usage = '''
    %(prog)s --release-plugin [--interactive|--non-interactive] [--password=PASS] [--production] [--settings=FILE] [--testing] --plugin-identifier=PLUG
    %(prog)s (--copyright|--help|--license|--usage|--version)'''
        parser = argparse.ArgumentParser(usage=usage, add_help=False)
        # Mutually exclusive commands
        mutexgroup = parser.add_mutually_exclusive_group(required=True)
        mutexgroup.add_argument('--release-plugin', '-r', action='store_true', help='build and deploy plugins')
        mutexgroup.add_argument('--copyright', '-C', action='store_true', help='show copyright and exit')
        mutexgroup.add_argument('--help', '-h', action='help', help='show this help message and exit')
        mutexgroup.add_argument('--license', '-L', action='store_true', help='show license and exit')
        mutexgroup.add_argument('--usage', '-U', action='store_true', help='show usage information and exit')
        mutexgroup.add_argument('--version', '-V', action='version', version=__version__)
        # --release-plugin group
        group = parser.add_argument_group('Build and deploy plugins (--release-plugin)')
        group.add_argument('--no-deploy', action='store_true', help='only build plugins, do not deploy')
        group.add_argument('--password', metavar='PASS', help='use %(metavar)s as the plugin signing keystore password (default: interactive prompt)')
        group.add_argument('--plugin-identifier', metavar='PLUG', action='append', help='add %(metavar)s to the list of plugin identifiers to build')
        group.add_argument('--production', '-p', action='store_true', help="deploy to the registry's production directory")
        group.add_argument('--testing', '-t', action='store_true', help="deploy to the registry's testing directory")
        # Config group
        group = parser.add_argument_group('Configuration')
        mutexgroup = group.add_mutually_exclusive_group()
        mutexgroup.add_argument('--interactive', '-i', action='store_true', help='enable interactive prompts (default: --non-interactive)')
        mutexgroup.add_argument('--non-interactive', '-n', dest='interactive', action='store_const', const=False, help='disallow interactive prompts (default)')
        group.add_argument('--plugin-registries', metavar='FILE', type=Path, help='load plugin registries from %(metavar)s (default: {})'.format(self.list_config_files(Turtles.PLUGIN_REGISTRIES)))
        group.add_argument('--plugin-sets', metavar='FILE', type=Path, help='load plugin sets from %(metavar)s (default: {})'.format(self.list_config_files(Turtles.PLUGIN_SETS)))
        group.add_argument('--settings', metavar='FILE', type=Path, help='load settings from %(metavar)s (default: {})'.format(self.list_config_files(Turtles.SETTINGS)))
        # Return parser
        return parser

    def run(self):
        self.initialize()
        self.load_settings()
        if self.release_plugin:
            self.do_release_plugin()
        else:
            raise RuntimeError('no command to dispatch')

    def select_config_file(self, filename):
        for x in self.config_files(filename):
            if x.exists():
                return x
        else:
            return None

#
# Main entry point
#

if __name__ == '__main__': Turtles().run()


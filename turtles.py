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
import java_manifest
import os
from pathlib import Path, PurePath
import shutil
import subprocess
import sys
import xdg
import xml.etree.ElementTree as ET
import yaml
import zipfile

def _path(purepath_or_string):
    if issubclass(type(purepath_or_string), PurePath):
        return purepath_or_string
    else:
        return Path(purepath_or_string).expanduser().resolve() 

class Plugin(object):

    @staticmethod
    def from_jar(jarpath):
        jarpath = _path(jarpath) # in case it's a string
        plugid = Plugin.id_from_jar(jarpath)
        plugfile = str(Plugin.id_to_file(plugid))
        with zipfile.ZipFile(jarpath, 'r') as zf:
            with zf.open(plugfile, 'r') as mf:
                return Plugin(mf, zipfile.Path(zf, plugfile))

    @staticmethod
    def from_path(filepath):
        filepath = _path(filepath) # in case it's a string
        with open(filepath, 'r') as f:
            return Plugin(f, filepath)

    @staticmethod
    def file_to_id(filepath):
        return filepath.replace('/', '.')[:-4] # for .xml

    @staticmethod
    def id_from_jar(jarpath):
        jarpath = _path(jarpath) # in case it's a string
        manifest = java_manifest.from_jar(jarpath)
        for entry in manifest:
            if entry.get('Lockss-Plugin') == 'true':
                return Plugin.file_to_id(entry['Name'])
        else:
            raise RuntimeException(f'error: {jarpath!s}: no valid Lockss-Plugin entry in META-INF/MANIFEST.MF')

    @staticmethod
    def id_to_dir(plugid):
        return Plugin.id_to_file(plugid).parent

    @staticmethod
    def id_to_file(plugid):
        return Path(f'{plugid.replace(".", "/")}.xml')

    def __init__(self, f, path):
        super().__init__()
        self._path = path
        self._parsed = ET.parse(f).getroot()
        tag = self._parsed.tag
        if tag != 'map':
            raise RuntimeError(f'{path!s}: invalid root element: {tag}')

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
            raise ValueError(f'plugin declares {len(lst)} entries for {key}')
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
            raise RuntimeError(f'{path}: kind is not defined') 
        elif kind != PluginRegistry.KIND:
            raise RuntimeError(f'{path}: not of kind {PluginRegistry.KIND}: {kind}')
        layout = parsed.get('layout')
        if layout is None:
            raise RuntimeError(f'{path}: layout is not defined')
        elif layout == RcsPluginRegistry.LAYOUT:
            return RcsPluginRegistry(parsed)
        else:
            raise RuntimeError(f'{path}: unknown layout: {layout}')

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

    def deploy_plugin(self, plugid, jarpath, testing=False, production=False, interactive=False):
        if not (testing or production):
            raise RuntimeError('must deploy to at least one of testing or production')
        ret = list()
        if testing:
            ret.append(self.do_deploy_plugin(plugid, jarpath, self.test_path(), interactive))
        if production:
            ret.append(self.do_deploy_plugin(plugid, jarpath, self.prod_path(), interactive))
        return ret

    def do_deploy_plugin(self, plugid, jarpath, regpath, interactive=False):
        plugin = Plugin.from_jar(jarpath)
        filestr = jarpath.name
        dstpath = Path(regpath, filestr)
        do_chcon = (subprocess.run('command -v selinuxenabled && selinuxenabled && command -v chcon', shell=True).returncode == 0)
        if not dstpath.exists():
            if interactive:
                i = input(f'{dstpath} does not exist in {self.name()}; create it (y/n)? [n] ').lower() or 'n'
                if i != 'y':
                    return
        else:
            cmd = ['co', '-l', filestr]
            subprocess.run(cmd, check=True, cwd=regpath)
        shutil.copy(str(jarpath), str(dstpath))
        if do_chcon:
            cmd = ['chcon', '-t', 'httpd_sys_content_t', filestr]
            subprocess.run(cmd, check=True, cwd=regpath)
        cmd = ['ci', '-u', f'-mVersion {plugin.version()}']
        if not regpath.joinpath('RCS', f'{filestr},v').is_file():
            cmd.append(f'-t-{plugin.name()}') 
        cmd.append(filestr)
        subprocess.run(cmd, check=True, cwd=regpath)
        return dstpath
        
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
            raise RuntimeError(f'{path}: kind is not defined') 
        elif kind != PluginSet.KIND:
            raise RuntimeError(f'{path}: not of kind {PluginSet.KIND}: {kind}')
        builder = parsed.get('builder')
        if builder is None:
            raise RuntimeError(f'{path}: builder is not defined')
        typ = builder.get('type')
        if typ is None:
            raise RuntimeError(f'{path}: builder type is not defined')
        elif typ == AntPluginSet.TYPE:
            return AntPluginSet(parsed, path)
        elif typ == 'mvn':
            raise NotImplementedError(f'{path}: the builder type mvn is not implemented yet')
        else:
            raise RuntimeError(f'{path}: unknown builder type: {typ}')

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
        # Prerequisites
        if 'JAVA_HOME' not in os.environ:
            raise RuntimeError('error: JAVA_HOME must be set in your environment')
        # Get all directories for jarplugin -d
        dirs = list()
        curid = plugid
        while curid is not None:
            curdir = Plugin.id_to_dir(curid)
            if curdir not in dirs:
                dirs.append(curdir)
            curid = self.make_plugin(curid).parent_identifier()
        dirs = [str(i).replace('.', '/') for i in dirs]
        # Invoke jarplugin
        plugfile = Plugin.id_to_file(plugid)
        plugjar = self.root_path().joinpath('plugins/jars', f'{plugfile.stem}.jar')
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
        if not plugjar.is_file():
            raise FileNotFoundError(str(plugjar))
        return plugjar

    def has_plugin(self, plugid):
        return self._plugin_path(plugid).is_file()
        
    def main(self):
        return self._parsed.get('main', 'plugins/src')
        
    def main_path(self):
        return self.root_path().joinpath(self.main())
        
    def make_plugin(self, plugid):
        return Plugin.from_path(self._plugin_path(plugid))
        
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
        self.settings = None
        self.plugin_sets = None
        self.plugin_registries = None

    def config_files(self, filename):
        return [Path(base, filename) for base in Turtles.CONFIG_DIRS]

    def do_build_one_plugin(self, plugid):
        for plugin_set in self.plugin_sets:
           if plugin_set.has_plugin(plugid):
               return plugin_set.build_plugin(plugid,
                                              self.get_plugin_signing_keystore(),
                                              self.get_plugin_signing_alias(),
                                              self.get_plugin_signing_password())
        else:
            sys.exit(f'error: {plugid} not found in any plugin set')

    def do_build_plugin(self):
        self.load_settings()
        self.load_plugin_sets()
        ret = [self.do_build_one_plugin(plugid) for plugid in self.plugin_identifiers]
        if self.build_plugin:
            for path in ret:
                print(path)
        return ret

    def do_deploy_one_plugin(self, jarpath):
        try:
            plugid = Plugin.id_from_jar(jarpath)
        except RuntimeException as e:
            sys.exit(f'error: {jarpath}: no valid Lockss-Plugin entry in META-INF/MANIFEST.MF')
        paths = list()
        for plugin_registry in self.plugin_registries:
            if plugin_registry.has_plugin(plugid):
                paths.extend(plugin_registry.deploy_plugin(plugid,
                                                           jarpath,
                                                           testing=self.testing,
                                                           production=self.production,
                                                           interactive=False))
        if len(paths) == 0:
            sys.exit(f'error: {jarpath}: {plugid} is not declared in any plugin registry')
        return paths

    def do_deploy_plugin(self):
        self.load_plugin_registries()
        ret = list()
        for jarpath in self.plugin_jars:
            ret.extend(self.do_deploy_one_plugin(jarpath))
        if self.deploy_plugin:
            for path in ret:
                print(path)
        return ret

    def do_release_plugin(self):
        self.plugin_jars = self.do_build_plugin()
        ret = self.do_deploy_plugin()
        if self.release_plugin:
            for path in ret:
                print(path)
        return ret

    def get_plugin_signing_alias(self):
        self.load_settings()
        ret = self.settings.get('plugin-signing-alias')
        if ret is None:
            sys.exit('error: plugin-signing-alias is not defined in your settings')
        return ret

    def get_plugin_signing_keystore(self):
        self.load_settings()
        ret = self.settings.get('plugin-signing-keystore')
        if ret is None:
            sys.exit('error: plugin-signing-keystore is not defined in your settings')
        return _path(ret)

    def get_plugin_signing_password(self):
        if self._password is None:
            if self.interactive:
                self._password = getpass.getpass('Plugin signing password: ')
            else:
                sys.exit('error: plugin signing password is not set')
        return self._password

    def initialize(self):
        parser = self.make_parser()
        args = parser.parse_args()

        #
        # One-and-done block
        #
        if args.copyright:
            print(__copyright__)
            parser.exit()
        # --help is automatic
        if args.license:
            print(__license__)
            parser.exit()
        if args.usage:
            parser.print_usage()
            parser.exit()
        # --version is automatic
        
        #
        # --build-plugin, --deploy-plugin, --release-plugin
        #
        self.build_plugin = args.build_plugin
        self.deploy_plugin = args.deploy_plugin
        self.release_plugin = args.release_plugin

        #
        # Plugin build options
        #
        if self.build_plugin or self.release_plugin:
            self.plugin_identifiers = args.plugin_identifier
            if len(self.plugin_identifiers) == 0:
                parser.error('list of plugin identifiers to build is empty')
            self._password = args.password 

        #
        # Plugin deployment options
        #
        if self.deploy_plugin or self.release_plugin:
            self.testing = args.testing
            self.production = args.production
            if self.deploy_plugin:
                self.plugin_jars = args.plugin_jar
                if len(self.plugin_jars) == 0:
                    parser.error('list of plugin JARs to build is empty')
            elif self.release_plugin:
                self.plugin_jars = None
            else:
                raise RuntimeError('internal error')

        #
        # Configuration options
        #
        self.interactive = args.interactive
        self.plugin_registries_path = args.plugin_registries or self.select_config_file(Turtles.PLUGIN_REGISTRIES)
        self.plugin_sets_path = args.plugin_sets or self.select_config_file(Turtles.PLUGIN_SETS)
        self.settings_path = args.settings or self.select_config_file(Turtles.SETTINGS)

    def list_config_files(self, filename):
        return ' or '.join(str(x) for x in self.config_files(filename))

    def load_plugin_registries(self):
        if self.plugin_registries is None:
            parsed = None
            with self.plugin_registries_path.open('r') as f:
                parsed = yaml.safe_load(f)
            kind = parsed.get('kind')
            if kind is None:
                sys.exit(f'{self.plugin_registries_path}: kind is not defined')
            elif kind != 'Settings':
                sys.exit(f'{self.plugin_registries_path}: not of kind Settings: {kind}')
            paths = parsed.get('plugin-registries')
            if paths is None:
                sys.exit(f'{self.plugin_registries_path}: undefined plugin-registries')
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
                sys.exit(f'{self.plugin_sets_path}: kind is not defined')
            elif kind != 'Settings':
                sys.exit(f'{self.plugin_sets_path}: not of kind Settings: {kind}')
            paths = parsed.get('plugin-sets')
            if paths is None:
                sys.exit(f'{self.plugin_sets_path}: plugin-sets is not defined')
            self.plugin_sets = list()
            for path in paths:
                self.plugin_sets.extend(PluginSet.from_path(path))

    def load_settings(self):
        if self.settings is None:
            if not self.settings_path.is_file():
                self.settings = dict()
                return
            with self.settings_path.open('r') as f:
                self.settings = yaml.safe_load(f)
            kind = self.settings.get('kind')
            if kind is None:
                sys.exit(f'{self.settings_path}: kind is not defined')
            elif kind != 'Settings':
                sys.exit(f'{self.settings_path}: not of kind Settings: {kind}')

    def make_parser(self):
        # Make parser
        usage = '''
    %(prog)s --build-plugin [OPTIONS] --plugin-identifier=PLUG
    %(prog)s --deploy-plugin [OPTIONS] [--production] [--testing] --plugin-jar=JAR
    %(prog)s --release-plugin [OPTIONS] [--production] [--testing] --plugin-identifier=PLUG
    %(prog)s (--copyright|--help|--license|--usage|--version)'''
        parser = argparse.ArgumentParser(prog='turtles', usage=usage, add_help=False)
        # Mutually exclusive commands
        m1a = parser.add_mutually_exclusive_group(required=True)
        m1a.add_argument('--build-plugin', '-b', action='store_true', help='build plugins')
        m1a.add_argument('--copyright', '-C', action='store_true', help='show copyright and exit')
        m1a.add_argument('--deploy-plugin', '-d', action='store_true', help='deploy plugins')
        m1a.add_argument('--help', '-h', action='help', help='show this help message and exit')
        m1a.add_argument('--license', '-L', action='store_true', help='show license and exit')
        m1a.add_argument('--release-plugin', '-r', action='store_true', help='release (build and deploy) plugins')
        m1a.add_argument('--usage', '-U', action='store_true', help='show usage information and exit')
        m1a.add_argument('--version', '-V', action='version', version=__version__)
        # Plugin build options
        g2 = parser.add_argument_group('Plugin build options (--build-plugin, --release-plugin)')
        g2.add_argument('--password', metavar='PASS', help='use %(metavar)s as the plugin signing keystore password (default: interactive prompt)')
        g2.add_argument('--plugin-identifier', metavar='PLUG', action='append', help='add %(metavar)s to the list of plugin identifiers to build')
        # Plugin deployment options (--deploy-plugin)
        g3 = parser.add_argument_group('Plugin deployment options (--deploy-plugin, --release-plugin)')
        g3.add_argument('--plugin-jar', metavar='JAR', type=Path, action='append', help='(--deploy-plugin only) add %(metavar)s to the list of plugin JARs to deploy')
        g3.add_argument('--production', '-p', action='store_true', help="deploy to the registry's production directory")
        g3.add_argument('--testing', '-t', action='store_true', help="deploy to the registry's testing directory")
        # Config group
        g4 = parser.add_argument_group('Configuration options')
        m4a = g4.add_mutually_exclusive_group()
        m4a.add_argument('--interactive', '-i', action='store_true', help='enable interactive prompts (default: --non-interactive)')
        m4a.add_argument('--non-interactive', '-n', dest='interactive', action='store_const', const=False, help='disallow interactive prompts (default)')
        g4.add_argument('--plugin-registries', metavar='FILE', type=Path, help=f'load plugin registries from %(metavar)s (default: {self.list_config_files(Turtles.PLUGIN_REGISTRIES)})')
        g4.add_argument('--plugin-sets', metavar='FILE', type=Path, help=f'load plugin sets from %(metavar)s (default: {self.list_config_files(Turtles.PLUGIN_SETS)})')
        g4.add_argument('--settings', metavar='FILE', type=Path, help=f'load settings from %(metavar)s (default: {self.list_config_files(Turtles.SETTINGS)})')
        # Return parser
        return parser

    def run(self):
        self.initialize()
        self.load_settings()
        if self.build_plugin:
            self.do_build_plugin()
        elif self.deploy_plugin:
            self.do_deploy_plugin()
        elif self.release_plugin:
            self.do_release_plugin()
        else:
            raise RuntimeError('no command to dispatch')

    def select_config_file(self, filename):
        for x in self.config_files(filename):
            if x.is_file():
                return x
        else:
            return None

#
# Main entry point
#

if __name__ == '__main__':
    if sys.version_info < (3, 6):
        sys.exit('Requires Python 3.6 or greater; currently {}'.format(sys.version))
    Turtles().run()


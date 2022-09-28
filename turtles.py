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

PROG = 'turtles'

def _file_lines(path):
    f = None
    try:
        f = open(_path(path), 'r') if path != '-' else sys.stdin 
        return [line for line in [line.partition('#')[0].strip() for line in f] if len(line) > 0]
    finally:
        if f is not None and path != '-':
            f.close() 

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
                return Plugin(mf, plugfile)

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
            raise Exception(f'error: {jarpath!s}: no valid Lockss-Plugin entry in META-INF/MANIFEST.MF')

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
        
    def id(self):
        return self._parsed['id']
    
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
            ret.append(self.do_deploy_plugin(plugid, jarpath, self.test_path(), interactive=interactive))
        if production:
            ret.append(self.do_deploy_plugin(plugid, jarpath, self.prod_path(), interactive=interactive))
        return ret

    def do_deploy_plugin(self, plugid, jarpath, regpath, interactive=False):
        plugin = Plugin.from_jar(jarpath)
        filestr = jarpath.name
        dstpath = Path(regpath, filestr)
        do_chcon = (subprocess.run('command -v selinuxenabled > /dev/null && selinuxenabled && command -v chcon > /dev/null', shell=True).returncode == 0)
        if not dstpath.exists():
            if interactive:
                i = input(f'{dstpath} does not exist in {self.name()} ({self.id()}); create it (y/n)? [n] ').lower() or 'n'
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
        
    def id(self):
        return self._parsed['id']
    
    def make_plugin(self, plugid):
        raise NotImplementedError('make_plugin')

    def name(self):
        return self._parsed['name']
    
#
# class AntPluginSet
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
    
    def __init__(self):
        super().__init__()
        self._password = None
        self._plugin_sets = list()
        self._plugin_registries = list()
        self._settings = dict()

    def build_plugin(self, plugids):
        return {plugid: self._build_one_plugin(plugid) for plugid in plugids}

    def deploy_plugin(self, plugjars, testing=False, production=False):
        return {jarpath: self._deploy_one_plugin(jarpath, testing=testing, production=production) for jarpath in plugjars}

    def release_plugin(self, plugids, testing=False, production=False):
        ret1 = self.build_plugin(plugids)
        plugjars = list(ret1.values())
        ret2 = self.deploy_plugin(plugjars, testing=testing, production=production)
        return {plugid: ret2[ret1[plugid]] for plugid in ret1.keys()}

    def load_plugin_registries(self, path):
        path = _path(path)
        parsed = None
        with path.open('r') as f:
            parsed = yaml.safe_load(f)
        kind = parsed.get('kind')
        if kind is None:
            raise Exception(f'{path!s}: kind is not defined')
        elif kind != 'Settings':
            raise Exception(f'{path!s}: not of kind Settings: {kind}')
        paths = parsed.get('plugin-registries')
        if paths is None:
            raise Exception(f'{path!s}: undefined plugin-registries')
        self._plugin_registries = list()
        for p in paths:
            self._plugin_registries.extend(PluginRegistry.from_path(p))

    def load_plugin_sets(self, path):
        path = _path(path)
        parsed = None
        with path.open('r') as f:
            parsed = yaml.safe_load(f)
        kind = parsed.get('kind')
        if kind is None:
            raise Exception(f'{path!s}: kind is not defined')
        elif kind != 'Settings':
            raise Exception(f'{path!s}: not of kind Settings: {kind}')
        paths = parsed.get('plugin-sets')
        if paths is None:
            raise Exception(f'{path!s}: plugin-sets is not defined')
        self.plugin_sets = list()
        for p in paths:
            self._plugin_sets.extend(PluginSet.from_path(p))

    def load_settings(self, path):
        path = _path(path)
        with path.open('r') as f:
            parsed = yaml.safe_load(f)
        kind = parsed.get('kind')
        if kind is None:
            raise Exception(f'{path!s}: kind is not defined')
        elif kind != 'Settings':
            raise Exception(f'{path!s}: not of kind Settings: {kind}')
        self._settings = parsed

    def set_password(self, obj):
        self._password = obj() if callable(obj) else obj

    def _build_one_plugin(self, plugid):
        for plugin_set in self._plugin_sets:
            if plugin_set.has_plugin(plugid):
                return plugin_set.build_plugin(plugid,
                                               self._get_plugin_signing_keystore(),
                                               self._get_plugin_signing_alias(),
                                               self._get_plugin_signing_password())
        else:
            raise Exception(f'{plugid}: not found in any plugin set')

    def _deploy_one_plugin(self, jarpath, testing=False, production=False):
        try:
            plugid = Plugin.id_from_jar(jarpath)
        except Exception as e:
            raise Exception(f'{jarpath}: no valid Lockss-Plugin entry in META-INF/MANIFEST.MF') from e
        paths = list()
        for plugin_registry in self._plugin_registries:
            if plugin_registry.has_plugin(plugid):
                paths.extend(plugin_registry.deploy_plugin(plugid,
                                                           jarpath,
                                                           testing=testing,
                                                           production=production,
                                                           interactive=False))
        if len(paths) == 0:
            raise Exception(f'{jarpath}: {plugid} not declared in any plugin registry')
        return paths

    def _get_plugin_signing_alias(self):
        ret = self._settings.get('plugin-signing-alias')
        if ret is None:
            raise Exception('plugin-signing-alias is not defined in the settings')
        return ret

    def _get_plugin_signing_keystore(self):
        ret = self._settings.get('plugin-signing-keystore')
        if ret is None:
            raise Exception('plugin-signing-keystore is not defined in the settings')
        return _path(ret)

    def _get_plugin_signing_password(self):
        return self._password

class TurtlesCli(Turtles):
    
    XDG_CONFIG_DIR=xdg.xdg_config_home().joinpath(PROG)
    GLOBAL_CONFIG_DIR=Path('/etc', PROG)
    CONFIG_DIRS=[XDG_CONFIG_DIR, GLOBAL_CONFIG_DIR]

    PLUGIN_REGISTRIES='plugin-registries.yaml'
    PLUGIN_SETS='plugin-sets.yaml'
    SETTINGS='settings.yaml'

    @staticmethod
    def _config_files(filename):
        return [Path(base, filename) for base in TurtlesCli.CONFIG_DIRS]

    @staticmethod
    def _list_config_files(filename):
        return ' or '.join(str(x) for x in TurtlesCli._config_files(filename))

    @staticmethod
    def _select_config_file(filename):
        for x in TurtlesCli._config_files(filename):
            if x.is_file():
                return x
        return None

    def __init__(self):
        super().__init__()
        self._args = None
        self._parser = None
        self._plugin_identifiers = None
        self._plugin_jars = None
        self._subparsers = None

    def run(self):
        self._make_parser()
        self._args = self._parser.parse_args()
        self._args.fun()

    def _build_plugin(self):
        self.load_settings(self._args.settings or TurtlesCli._select_config_file(TurtlesCli.SETTINGS))
        self.load_plugin_sets(self._args.plugin_sets or TurtlesCli._select_config_file(TurtlesCli.PLUGIN_SETS))
        self._obtain_password()
        ret = self.build_plugin(self._get_plugin_identifiers())

    def _copyright(self):
        print(__copyright__)

    def _deploy_plugin(self):
        self.load_plugin_registries(self._args.plugin_registries or TurtlesCli._select_config_file(TurtlesCli.PLUGIN_REGISTRIES))
        ret = self.deploy_plugin(self._get_plugin_jars())

    def _get_plugin_identifiers(self):
        if self._plugin_identifiers is None:
            self._plugin_identifiers = list()
            self._plugin_identifiers.extend(self._args.remainder)
            self._plugin_identifiers.extend(self._args.plugin_identifier)
            for path in self._args.plugin_identifiers:
                self._plugin_identifiers.extend(_file_lines(path))
            if len(self._plugin_identifiers) == 0:
                self._parser.error('list of plugin identifiers to build is empty')
        return self._plugin_identifiers
    
    def _get_plugin_jars(self):
        if self._plugin_jars is None:
            self._plugin_jars = list()
            self._plugin_jars.extend(self._args.remainder)
            self._plugin_jars.extend(self._args.plugin_jar)
            for path in self._args.plugin_jars:
                self._plugin_jars.extend(_file_lines(path))
            if len(self._plugin_identifiers) == 0:
                self._parser.error('list of plugin JARs to deploy is empty')
        return self._plugin_jars
    
    def _license(self):
        print(__license__)

    def _make_parser(self):
        self._parser = argparse.ArgumentParser(prog=PROG)
        self._subparsers = self._parser.add_subparsers(title='commands',
                                                       #dest='subcommand',
                                                       metavar='COMMAND',
                                                       description="Add --help to see the command's own help message",
                                                       help='DESCRIPTION')
        self._make_options_main()
        self._make_parser_build_plugin()
        self._make_parser_deploy_plugin()
        self._make_parser_release_plugin()
        self._make_parser_one_and_done()

    def _make_parser_build_plugin(self):
        parser = self._subparsers.add_parser('build-plugin', aliases=['bp'],
                                             description='Build plugins',
                                             help='build plugins')
        #parser.set_defaults(fun=self._build_plugin)
        self._make_options_password(parser)
        self._make_options_plugin_identifiers(parser)
        self._make_options_plugin_sets(parser)
        self._make_options_settings(parser)

    def _make_parser_deploy_plugin(self):
        parser = self._subparsers.add_parser('deploy-plugin', aliases=['dp'],
                                             description='Deploy plugins',
                                             help='deploy plugins')
        parser.set_defaults(fun=self._deploy_plugin)
        self._make_options_plugin_jars(parser)
        self._make_options_plugin_registries(parser)
        self._make_options_testing_production(parser)

    def _make_parser_one_and_done(self):
        for s in ['copyright', 'license', 'usage', 'version']:
            parser = self._subparsers.add_parser(s,
                                                 description=f'Show {s} and exit',
                                                 help=f'show {s} and exit')

            parser.set_defaults(fun=getattr(self, f'_{s}'))

    def _make_parser_release_plugin(self):
        parser = self._subparsers.add_parser('release-plugin', aliases=['rp'],
                                             description='Release (build and deploy) plugins',
                                             help='release (build and deploy) plugins')
        parser.set_defaults(fun=self._release_plugin)
        self._make_options_password(parser)
        self._make_options_plugin_identifiers(parser)
        self._make_options_plugin_registries(parser)
        self._make_options_plugin_sets(parser)
        self._make_options_testing_production(parser)
        self._make_options_settings(parser)

    def _make_options_password(self, parser):
        parser.add_argument('--password',
                            metavar='PASS',
                            help='set the plugin signing password')

    def _make_options_main(self):
        meg = self._parser.add_mutually_exclusive_group()
        meg.add_argument('--interactive', '-i',
                         action='store_true',
                         default=True,
                         help='allow interactive prompts (default)')
        meg.add_argument('--non-interactive', '-n',
                         dest='interactive',
                         action='store_false',
                         help='disallow interactive prompts (default: --interactive)')

    def _make_options_plugin_identifiers(self, parser):
        parser.add_argument('--plugin-identifier',
                            metavar='PLUGID',
                            action='append',
                            default=list(),
                            help='add %(metavar)s to the list of plugin identifiers to build')
        parser.add_argument('--plugin-identifiers',
                            metavar='FILE',
                            action='append',
                            default=list(),
                            help='add the plugin identifiers in %(metavar)s to the list of plugin identifiers to build')
        parser.add_argument('remainder',
                            metavar='PLUGID',
                            nargs='*',
                            help='plugin identifier to build')

    def _make_options_plugin_jars(self, parser):
        parser.add_argument('--plugin-jar',
                            metavar='PLUGJAR',
                            type=Path,
                            action='append',
                            default=list(),
                            help='add %(metavar)s to the list of plugin JARs to deploy')
        parser.add_argument('--plugin-jars',
                            metavar='FILE',
                            action='append',
                            default=list(),
                            help='add the plugin JARs in %(metavar)s to the list of plugin JARs to deploy')
        parser.add_argument('remainder',
                            metavar='PLUGJAR',
                            nargs='*',
                            help='plugin JAR to deploy')

    def _make_options_plugin_registries(self, parser):
        parser.add_argument('--plugin-registries',
                            metavar='FILE',
                            type=Path,
                            help=f'load plugin registries from %(metavar)s (default: {TurtlesCli._list_config_files(TurtlesCli.PLUGIN_REGISTRIES)})')
    
    def _make_options_plugin_sets(self, parser):
        parser.add_argument('--plugin-sets',
                            metavar='FILE',
                            type=Path,
                            help=f'load plugin sets from %(metavar)s (default: {TurtlesCli._list_config_files(TurtlesCli.PLUGIN_SETS)})')
    
    def _make_options_settings(self, parser):
        parser.add_argument('--settings',
                            metavar='FILE',
                            type=Path,
                            help=f'load settings from %(metavar)s (default: {TurtlesCli._list_config_files(TurtlesCli.SETTINGS)})')
    
    def _make_options_testing_production(self, parser):
        parser.add_argument('--production', '-p',
                            action='store_true',
                            help="deploy to the registry's production directory")
        parser.add_argument('--testing', '-t',
                            action='store_true',
                            help="deploy to the registry's testing directory")

    def _obtain_password(self):
        if self._args.password is not None:
            _p = self._args.password
        elif self._args.interactive:
            _p = getpass.getpass('Plugin signing password: ')
        else:
            self._parser.error('no plugin signing password specified while in non-interactive mode')
        self.set_password(lambda: _p)

    def _release_plugin(self):
        self.load_settings(self._args.settings or TurtlesCli._select_config_file(TurtlesCli.SETTINGS))
        self.load_plugin_sets(self._args.plugin_sets or TurtlesCli._select_config_file(TurtlesCli.PLUGIN_SETS))
        self.load_plugin_registries(self._args.plugin_registries or TurtlesCli._select_config_file(TurtlesCli.PLUGIN_REGISTRIES))
        if not (self._args.testing or self._args.production):
            self._parser.error('must deploy to at least one of testing or production')
        self._obtain_password()
        ret = self.release_plugin(self._get_plugin_identifiers(), testing=self._args.testing, production=self._args.production)

    def _usage(self):
        self._parser.print_usage()

    def _version(self):
        print(__version__)

#
# Main entry point
#

if __name__ == '__main__':
    if sys.version_info < (3, 6):
        sys.exit('Requires Python 3.6 or greater; currently {}'.format(sys.version))
    TurtlesCli().run()


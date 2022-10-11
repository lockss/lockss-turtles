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

__version__ = '0.2.0-dev'

import argparse
import getpass
import java_manifest
import os
from pathlib import Path, PurePath
import shutil
import subprocess
import sys
import tabulate
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
        typ = layout.get('type')
        if typ is None:
            raise RuntimeError(f'{path}: layout type is not defined')
        elif typ == DirectoryPluginRegistry.LAYOUT:
            return DirectoryPluginRegistry(parsed)
        elif typ == RcsPluginRegistry.LAYOUT:
            return RcsPluginRegistry(parsed)
        else:
            raise RuntimeError(f'{path}: unknown layout type: {typ}')

    def __init__(self, parsed):
        super().__init__()
        self._parsed = parsed

    def get_layer(self, layerid):
        for layer in self._parsed['layers']:
            if layer['id'] == layerid:
                return self._make_layer(layer)
        return None

    def get_layers(self):
        return [layer['id'] for layer in self._parsed['layers']]

    def has_plugin(self, plugid):
        return plugid in self.plugin_identifiers()
        
    def id(self):
        return self._parsed['id']
    
    def layout_type(self):
        return self._parsed['layout']['type']

    def layout_options(self):
        return self._parsed['layout'].get('options', dict())

    def name(self):
        return self._parsed['name']
    
    def plugin_identifiers(self):
        return self._parsed['plugin-identifiers']
    
    def _make_layer(self, parsed):
        raise NotImplementedError('_make_layer')

class PluginRegistryLayer(object):

    PRODUCTION = 'production'
    TESTING = 'testing'

    def __init__(self, plugin_registry, parsed):
        super().__init__()
        self._parsed = parsed
        self._plugin_registry = plugin_registry

    def deploy_plugin(self, plugid, jarpath, interactive=False):
        raise NotImplementedError('deploy_plugin')

    def get_file_for(self, plugid):
        raise NotImplementedError('get_file_for')

    def get_jars(self):
        raise NotImplementedError('get_jars')

    def id(self):
        return self._parsed['id']

    def name(self):
        return self._parsed['name']

    def path(self):
        return _path(self._parsed['path'])

    def plugin_registry(self):
        return self._plugin_registry

class DirectoryPluginRegistry(PluginRegistry):

    class DirectoryPluginRegistryLayer(PluginRegistryLayer):

        def __init__(self, plugin_registry, parsed):
            super().__init__(plugin_registry, parsed)

        def deploy_plugin(self, plugid, srcpath, interactive=False):
            srcpath = _path(srcpath)  # in case it's a string
            dstpath = self._get_dstpath(plugid)
            if not self._proceed_copy(srcpath, dstpath, interactive=interactive):
                return None
            self._copy_jar(srcpath, dstpath, interactive=interactive)
            return dstpath

        def get_file_for(self, plugid):
            jarpath = self._get_dstpath(plugid)
            return jarpath if jarpath.is_file() else None

        def get_jars(self):
            return sorted(self.path().glob('*.jar'))

        def _copy_jar(self, srcpath, dstpath, interactive=False):
            filename = dstpath.name
            shutil.copy(str(srcpath), str(dstpath))
            if subprocess.run('command -v selinuxenabled > /dev/null && selinuxenabled && command -v chcon > /dev/null',
                              shell=True).returncode == 0:
                cmd = ['chcon', '-t', 'httpd_sys_content_t', filename]
                subprocess.run(cmd, check=True, cwd=self.path())

        def _get_dstpath(self, plugid):
            return Path(self.path(), self._get_dstfile(plugid))

        def _get_dstfile(self, plugid):
            return f'{plugid}.jar'

        def _proceed_copy(self, srcpath, dstpath, interactive=False):
            if not dstpath.exists():
                if interactive:
                    i = input(f'{dstpath} does not exist in {self.plugin_registry().id()}:{self.id()} ({self.name()}); create it (y/n)? [n] ').lower() or 'n'
                    if i != 'y':
                        return False
            return True

    LAYOUT = 'directory'

    def __init__(self, parsed):
        super().__init__(parsed)

    def _make_layer(self, parsed):
        return DirectoryPluginRegistry.DirectoryPluginRegistryLayer(self, parsed)

class RcsPluginRegistry(DirectoryPluginRegistry):

    class RcsPluginRegistryLayer(DirectoryPluginRegistry.DirectoryPluginRegistryLayer):

        def __init__(self, plugin_registry, parsed):
            super().__init__(plugin_registry, parsed)

        def _copy_jar(self, srcpath, dstpath, interactive=False):
            filename = dstpath.name
            plugin = Plugin.from_jar(srcpath)
            # Maybe do co -l before the parent's copy
            if dstpath.exists():
                cmd = ['co', '-l', filename]
                subprocess.run(cmd, check=True, cwd=self.path())
            # Do the parent's copy
            super()._copy_jar(srcpath, dstpath)
            # Do ci -u after the aprent's copy
            cmd = ['ci', '-u', f'-mVersion {plugin.version()}']
            if not self.path().joinpath('RCS', f'{filename},v').is_file():
                cmd.append(f'-t-{plugin.name()}')
            cmd.append(filename)
            subprocess.run(cmd, check=True, cwd=self.path())

        def _get_dstfile(self, plugid):
            conv = self.plugin_registry().layout_options().get('file-naming-convention')
            if conv == RcsPluginRegistry.ABBREVIATED:
                return f'{plugid.split(".")[-1]}.jar'
            elif conv == RcsPluginRegistry.FULL or conv is None:
                return super()._get_dstfile(plugid)
            else:
                raise RuntimeError(f'{self.plugin_registry().id()}: unknown file naming convention in layout options: {conv}')

    LAYOUT = 'rcs'

    FULL = 'full'
    ABBREVIATED = 'abbreviated'

    def __init__(self, parsed):
        super().__init__(parsed)

    def _make_layer(self, parsed):
        return RcsPluginRegistry.RcsPluginRegistryLayer(self, parsed)

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

    def builder_options(self):
        return self._parsed['builder'].get('options', dict())

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
        # Invoke jarplugin
        plugfile = Plugin.id_to_file(plugid)
        plugjar = self.root_path().joinpath('plugins/jars', f'{plugid}.jar')
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


#
# class AntPluginSet
#
class MavenPluginSet(PluginSet):

    TYPE = 'maven'

    def __init__(self, parsed, path):
        super().__init__(parsed)
        self._root = path.parent

    def build_plugin(self, plugid, keystore, alias, password=None):

        ###FIXME

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
        # Invoke jarplugin
        plugfile = Plugin.id_to_file(plugid)
        plugjar = self.root_path().joinpath('plugins/jars', f'{plugid}.jar')
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
        return self._parsed.get('main', 'src/main/java')

    def main_path(self):
        return self.root_path().joinpath(self.main())

    def make_plugin(self, plugid):
        return Plugin.from_path(self._plugin_path(plugid))

    def root(self):
        return self._root

    def root_path(self):
        return Path(self.root()).expanduser().resolve()

    def test(self):
        return self._parsed.get('test', 'src/test/java')

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

    def deploy_plugin(self, plugjars, layers, interactive=False):
        plugids = [Plugin.id_from_jar(jarpath) for jarpath in plugjars]
        return {(jarpath, plugid): self._deploy_one_plugin(jarpath,
                                                           plugid,
                                                           layers,
                                                           interactive=interactive) for jarpath, plugid in zip(plugjars, plugids)}

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

    def release_plugin(self, plugids, layers, interactive=False):
        ret1 = self.build_plugin(plugids)
        plugjars = [plugjar for plugsetid, plugjar in ret1.values()]
        ret2 = self.deploy_plugin(plugjars,
                                  layers,
                                  interactive=interactive)
        return {plugid: val for (plugjar, plugid), val in ret2.items()}

    def set_password(self, obj):
        self._password = obj() if callable(obj) else obj

    def _build_one_plugin(self, plugid):
        """
        Returns a (plugsetid, plujarpath) tuple
        """
        for plugin_set in self._plugin_sets:
            if plugin_set.has_plugin(plugid):
                return (plugin_set.id(),
                        plugin_set.build_plugin(plugid,
                                                self._get_plugin_signing_keystore(),
                                                self._get_plugin_signing_alias(),
                                                self._get_plugin_signing_password()))
        raise Exception(f'{plugid}: not found in any plugin set')

    def _deploy_one_plugin(self, jarpath, plugid, layers, interactive=False):
        """
        Returns a (plugregid, layer, deplpath) tuple
        """
        ret = list()
        for plugin_registry in self._plugin_registries:
            if plugin_registry.has_plugin(plugid):
                for layer in layers:
                    reglayer = plugin_registry.get_layer(layer)
                    if reglayer is not None:
                        ret.append((plugin_registry.id(),
                                    reglayer.id(),
                                    reglayer.deploy_plugin(plugid,
                                                           jarpath,
                                                           interactive=interactive)))
        if len(ret) == 0:
            raise Exception(f'{jarpath}: {plugid} not declared in any plugin registry')
        return ret

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
        self._identifiers = None
        self._jars = None
        self._layers = None
        self._parser = None
        self._subparsers = None

    def run(self):
        self._make_parser()
        self._args = self._parser.parse_args()
        if self._args.debug_cli:
            print(self._args)
        self._args.fun()

    def _analyze_registry(self):
        # Prerequisites
        self.load_settings(self._args.settings or TurtlesCli._select_config_file(TurtlesCli.SETTINGS))
        self.load_plugin_registries(self._args.plugin_registries or TurtlesCli._select_config_file(TurtlesCli.PLUGIN_REGISTRIES))
        self.load_plugin_sets(self._args.plugin_sets or TurtlesCli._select_config_file(TurtlesCli.PLUGIN_SETS))

        #####
        title = 'Plugins declared in a plugin registry but not found in any plugin set'
        a = list()
        ah = ['Plugin registry', 'Plugin identifier']
        for plugin_registry in self._plugin_registries:
            for plugid in plugin_registry.plugin_identifiers():
                for plugin_set in self._plugin_sets:
                    if plugin_set.has_plugin(plugid):
                        break
                else: # No plugin set matched
                    a.append([plugin_registry.id(), plugid])
        if len(a) > 0:
            self._tabulate(title, a, ah)

        #####
        title = 'Plugins declared in a plugin registry but with missing JARs'
        a = list()
        ah = ['Plugin registry', 'Plugin registry layer', 'Plugin identifier']
        for plugin_registry in self._plugin_registries:
            for plugid in plugin_registry.plugin_identifiers():
                for layer in plugin_registry.get_layers():
                    if plugin_registry.get_layer(layer).get_file_for(plugid) is None:
                        a.append([plugin_registry.id(), layer, plugid])
        if len(a) > 0:
            self._tabulate(title, a, ah)

        #####
        title = 'Plugin JARs not declared in any plugin registry'
        a = list()
        ah = ['Plugin registry', 'Plugin registry layer', 'Plugin JAR', 'Plugin identifier']
        # Map from layer path to the layers that have that path
        pathlayers = dict()
        for plugin_registry in self._plugin_registries:
            for layerid in plugin_registry.get_layers():
                layer = plugin_registry.get_layer(layerid)
                path = layer.path()
                pathlayers.setdefault(path, list()).append(layer)
        # Do report, taking care of not processing a path twice if overlapping
        visited = set()
        for plugin_registry in self._plugin_registries:
            for layerid in plugin_registry.get_layers():
                layer = plugin_registry.get_layer(layerid)
                if layer.path() not in visited:
                    visited.add(layer.path())
                    for jarpath in layer.get_jars():
                        if jarpath.stat().st_size > 0:
                            plugid = Plugin.id_from_jar(jarpath)
                            if not any([lay.plugin_registry().has_plugin(plugid) for lay in pathlayers[layer.path()]]):
                                a.append([plugin_registry.id(), layerid, jarpath, plugid])
        if len(a) > 0:
            self._tabulate(title, a, ah)

    def _build_plugin(self):
        # Prerequisites
        self.load_settings(self._args.settings or TurtlesCli._select_config_file(TurtlesCli.SETTINGS))
        self.load_plugin_sets(self._args.plugin_sets or TurtlesCli._select_config_file(TurtlesCli.PLUGIN_SETS))
        self._obtain_password()
        # Action
        ret = self.build_plugin(self._get_identifiers())
        # Output
        print(tabulate.tabulate([[key, *val] for key, val in ret.items()],
                                headers=['Plugin identifier', 'Plugin set', 'Plugin JAR'],
                                tablefmt=self._args.output_format))

    def _copyright(self):
        print(__copyright__)

    def _deploy_plugin(self):
        # Prerequisites
        self.load_plugin_registries(self._args.plugin_registries or TurtlesCli._select_config_file(TurtlesCli.PLUGIN_REGISTRIES))
        # Action
        ret = self.deploy_plugin(self._get_jars(),
                                 self._get_layers(),
                                 interactive=self._args.interactive)
        # Output
        print(tabulate.tabulate([[*key, *row] for key, val in ret.items() for row in val],
                                headers=['Plugin JAR', 'Plugin identifier', 'Plugin registry', 'Plugin registry layer', 'Deployed JAR'],
                                tablefmt=self._args.output_format))

    def _get_identifiers(self):
        if self._identifiers is None:
            self._identifiers = list()
            self._identifiers.extend(self._args.remainder)
            self._identifiers.extend(self._args.identifier)
            for path in self._args.identifiers:
                self._identifiers.extend(_file_lines(path))
            if len(self._identifiers) == 0:
                self._parser.error('list of plugin identifiers to build is empty')
        return self._identifiers

    def _get_jars(self):
        if self._jars is None:
            self._jars = list()
            self._jars.extend(self._args.remainder)
            self._jars.extend(self._args.jar)
            for path in self._args.jars:
                self._jars.extend(_file_lines(path))
            if len(self._jars) == 0:
                self._parser.error('list of plugin JARs to deploy is empty')
        return self._jars

    def _get_layers(self):
        if self._layers is None:
            self._layers = list()
            self._layers.extend(self._args.layer)
            for path in self._args.layers:
                self._layers.extend(_file_lines(path))
            if len(self._layers) == 0:
                self._parser.error('list of plugin registry layers to process is empty')
        return self._layers

    def _license(self):
        print(__license__)

    def _make_option_debug_cli(self, container):
        container.add_argument('--debug-cli',
                               action='store_true',
                               help='print the result of parsing command line arguments')

    def _make_option_non_interactive(self, container):
        container.add_argument('--non-interactive', '-n',
                               dest='interactive',
                               action='store_false', # note: default True
                               help='disallow interactive prompts (default: allow)')

    def _make_option_output_format(self, container):
        container.add_argument('--output-format',
                               metavar='FMT',
                               choices=tabulate.tabulate_formats,
                               default='simple',
                               help='set tabular output format to %(metavar)s (default: %(default)s; choices: %(choices)s)')

    def _make_option_password(self, container):
        container.add_argument('--password',
                               metavar='PASS',
                               help='set the plugin signing password')

    def _make_option_plugin_registries(self, container):
        container.add_argument('--plugin-registries',
                               metavar='FILE',
                               type=Path,
                               help=f'load plugin registries from %(metavar)s (default: {TurtlesCli._list_config_files(TurtlesCli.PLUGIN_REGISTRIES)})')

    def _make_option_plugin_sets(self, container):
        container.add_argument('--plugin-sets',
                               metavar='FILE',
                               type=Path,
                               help=f'load plugin sets from %(metavar)s (default: {TurtlesCli._list_config_files(TurtlesCli.PLUGIN_SETS)})')

    def _make_option_production(self, container):
        container.add_argument('--production', '-p',
                               dest='layer',
                               action='append_const',
                               const=PluginRegistryLayer.PRODUCTION,
                               help="synonym for --layer=%(const)s (i.e. add '%(const)s' to the list of plugin registry layers to process)")

    def _make_option_settings(self, container):
        container.add_argument('--settings',
                               metavar='FILE',
                               type=Path,
                               help=f'load settings from %(metavar)s (default: {TurtlesCli._list_config_files(TurtlesCli.SETTINGS)})')

    def _make_option_testing(self, container):
        container.add_argument('--testing', '-t',
                               dest='layer',
                               action='append_const',
                               const=PluginRegistryLayer.TESTING,
                               help="synonym for --layer=%(const)s (i.e. add '%(const)s' to the list of plugin registry layers to process)")

    def _make_options_identifiers(self, container):
        container.add_argument('--identifier', '-i',
                               metavar='PLUGID',
                               action='append',
                               default=list(),
                               help='add %(metavar)s to the list of plugin identifiers to build')
        container.add_argument('--identifiers', '-I',
                               metavar='FILE',
                               action='append',
                               default=list(),
                               help='add the plugin identifiers in %(metavar)s to the list of plugin identifiers to build')
        container.add_argument('remainder',
                               metavar='PLUGID',
                               nargs='*',
                               help='plugin identifier to build')

    def _make_options_jars(self, container):
        container.add_argument('--jar', '-j',
                               metavar='PLUGJAR',
                               type=Path,
                               action='append',
                               default=list(),
                               help='add %(metavar)s to the list of plugin JARs to deploy')
        container.add_argument('--jars', '-J',
                               metavar='FILE',
                               action='append',
                               default=list(),
                               help='add the plugin JARs in %(metavar)s to the list of plugin JARs to deploy')
        container.add_argument('remainder',
                               metavar='PLUGJAR',
                               nargs='*',
                               help='plugin JAR to deploy')

    def _make_options_layers(self, container):
        container.add_argument('--layer', '-l',
                               metavar='LAYER',
                               action='append',
                               default=list(),
                               help='add %(metavar)s to the list of plugin registry layers to process')
        container.add_argument('--layers', '-L',
                               metavar='FILE',
                               action='append',
                               default=list(),
                               help='add the layers in %(metavar)s to the list of plugin registry layers to process')

    def _make_parser(self):
        self._parser = argparse.ArgumentParser(prog=PROG)
        self._subparsers = self._parser.add_subparsers(title='commands',
                                                       description="Add --help to see the command's own help message",
                                                       # In subparsers, metavar is also used as the heading of the column of subcommands
                                                       metavar='COMMAND',
                                                       # In subparsers, help is used as the heading of the column of subcommand descriptions
                                                       help='DESCRIPTION')
        self._make_option_debug_cli(self._parser)
        self._make_option_non_interactive(self._parser)
        self._make_option_output_format(self._parser)
        self._make_parser_analyze_registry(self._subparsers)
        self._make_parser_build_plugin(self._subparsers)
        self._make_parser_copyright(self._subparsers)
        self._make_parser_deploy_plugin(self._subparsers)
        self._make_parser_license(self._subparsers)
        self._make_parser_release_plugin(self._subparsers)
        self._make_parser_usage(self._subparsers)
        self._make_parser_version(self._subparsers)

    def _make_parser_analyze_registry(self, container):
        parser = container.add_parser('analyze-registry', aliases=['ar'],
                                      description='Analyze plugin registries',
                                      help='analyze plugin registries')
        parser.set_defaults(fun=self._analyze_registry)
        self._make_option_plugin_registries(parser)
        self._make_option_plugin_sets(parser)
        self._make_option_settings(parser)

    def _make_parser_build_plugin(self, container):
        parser = container.add_parser('build-plugin', aliases=['bp'],
                                      description='Build (package and sign) plugins',
                                      help='build (package and sign) plugins')
        parser.set_defaults(fun=self._build_plugin)
        self._make_options_identifiers(parser)
        self._make_option_password(parser)
        self._make_option_plugin_sets(parser)
        self._make_option_settings(parser)

    def _make_parser_copyright(self, container):
        parser = container.add_parser('copyright',
                                      description='Show copyright and exit',
                                      help='show copyright and exit')
        parser.set_defaults(fun=self._copyright)

    def _make_parser_deploy_plugin(self, container):
        parser = container.add_parser('deploy-plugin', aliases=['dp'],
                                      description='Deploy plugins',
                                      help='deploy plugins')
        parser.set_defaults(fun=self._deploy_plugin)
        self._make_options_jars(parser)
        self._make_options_layers(parser)
        self._make_option_plugin_registries(parser)
        self._make_option_production(parser)
        self._make_option_testing(parser)

    def _make_parser_license(self, container):
        parser = container.add_parser('license',
                                      description='Show license and exit',
                                      help='show license and exit')
        parser.set_defaults(fun=self._license)

    def _make_parser_release_plugin(self, container):
        parser = container.add_parser('release-plugin', aliases=['rp'],
                                      description='Release (build and deploy) plugins',
                                      help='release (build and deploy) plugins')
        parser.set_defaults(fun=self._release_plugin)
        self._make_options_identifiers(parser)
        self._make_options_layers(parser)
        self._make_option_password(parser)
        self._make_option_plugin_registries(parser)
        self._make_option_plugin_sets(parser)
        self._make_option_production(parser)
        self._make_option_settings(parser)
        self._make_option_testing(parser)

    def _make_parser_usage(self, container):
        parser = container.add_parser('usage',
                                      description='Show usage and exit',
                                      help='show detailed usage and exit')
        parser.set_defaults(fun=self._usage)

    def _make_parser_version(self, container):
        parser = container.add_parser('version',
                                      description='Show version and exit',
                                      help='show version and exit')
        parser.set_defaults(fun=self._version)

    def _obtain_password(self):
        if self._args.password is not None:
            _p = self._args.password
        elif self._args.interactive:
            _p = getpass.getpass('Plugin signing password: ')
        else:
            self._parser.error('no plugin signing password specified while in non-interactive mode')
        self.set_password(lambda: _p)

    def _release_plugin(self):
        # Prerequisites
        self.load_settings(self._args.settings or TurtlesCli._select_config_file(TurtlesCli.SETTINGS))
        self.load_plugin_sets(self._args.plugin_sets or TurtlesCli._select_config_file(TurtlesCli.PLUGIN_SETS))
        self.load_plugin_registries(self._args.plugin_registries or TurtlesCli._select_config_file(TurtlesCli.PLUGIN_REGISTRIES))
        self._obtain_password()
        # Action
        ret = self.release_plugin(self._get_identifiers(),
                                  self._get_layers(),
                                  interactive=self._args.interactive)
        # Output
        print(tabulate.tabulate([[key, *row] for key, val in ret.items() for row in val],
                                headers=['Plugin identifier', 'Plugin registry', 'Plugin registry layer', 'Deployed JAR'],
                                tablefmt=self._args.output_format))

    def _tabulate(self, title, data, headers):
        print(self._title(title))
        print(tabulate.tabulate(data, headers=headers, tablefmt=self._args.output_format))
        print()

    def _title(self, s):
        return f'{"=" * len(s)}\n{s}\n{"=" * len(s)}\n'

    def _usage(self):
        self._parser.print_usage()
        print()
        uniq = set()
        for cmd, par in self._subparsers.choices.items():
            if par not in uniq:
                uniq.add(par)
                for s in par.format_usage().split('\n'):
                    usage = 'usage: '
                    print(f'{" " * len(usage)}{s[len(usage):]}' if s.startswith(usage) else s)

    def _version(self):
        print(__version__)

#
# Main entry point
#

if __name__ == '__main__':
    if sys.version_info < (3, 6):
        sys.exit('Requires Python 3.6 or greater; currently {}'.format(sys.version))
    TurtlesCli().run()

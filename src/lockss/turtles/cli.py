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

import argparse
import getpass
from pathlib import Path
import sys

import rich_argparse
import tabulate

import lockss.turtles
from lockss.turtles.app import TurtlesApp
from lockss.turtles.plugin_registry import PluginRegistryLayer
from lockss.turtles.util import _path


def _file_lines(path):
    f = None
    try:
        f = open(_path(path), 'r') if path != '-' else sys.stdin
        return [line for line in [line.partition('#')[0].strip() for line in f] if len(line) > 0]
    finally:
        if f is not None and path != '-':
            f.close()


class TurtlesCli(object):

    PROG = 'turtles'

    def __init__(self):
        super().__init__()
        self._app = TurtlesApp()
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

    # def _analyze_registry(self):
    #     # Prerequisites
    #     self.load_settings(self._args.settings or TurtlesCli._select_config_file(TurtlesCli.SETTINGS))
    #     self.load_plugin_registries(self._args.plugin_registries or TurtlesCli._select_config_file(TurtlesCli.PLUGIN_REGISTRIES))
    #     self.load_plugin_sets(self._args.plugin_sets or TurtlesCli._select_config_file(TurtlesCli.PLUGIN_SETS))
    #
    #     #####
    #     title = 'Plugins declared in a plugin registry but not found in any plugin set'
    #     result = list()
    #     headers = ['Plugin registry', 'Plugin identifier']
    #     for plugin_registry in self._plugin_registries:
    #         for plugin_id in plugin_registry.plugin_identifiers():
    #             for plugin_set in self._plugin_sets:
    #                 if plugin_set.has_plugin(plugin_id):
    #                     break
    #             else: # No plugin set matched
    #                 result.append([plugin_registry.id(), plugin_id])
    #     if len(result) > 0:
    #         self._tabulate(title, result, headers)
    #
    #     #####
    #     title = 'Plugins declared in a plugin registry but with missing JARs'
    #     result = list()
    #     headers = ['Plugin registry', 'Plugin registry layer', 'Plugin identifier']
    #     for plugin_registry in self._plugin_registries:
    #         for plugin_id in plugin_registry.plugin_identifiers():
    #             for layer_id in plugin_registry.get_layer_ids():
    #                 if plugin_registry.get_layer(layer_id).get_file_for(plugin_id) is None:
    #                     result.append([plugin_registry.id(), layer_id, plugin_id])
    #     if len(result) > 0:
    #         self._tabulate(title, result, headers)
    #
    #     #####
    #     title = 'Plugin JARs not declared in any plugin registry'
    #     result = list()
    #     headers = ['Plugin registry', 'Plugin registry layer', 'Plugin JAR', 'Plugin identifier']
    #     # Map from layer path to the layers that have that path
    #     pathlayers = dict()
    #     for plugin_registry in self._plugin_registries:
    #         for layer_id in plugin_registry.get_layer_ids():
    #             layer_id = plugin_registry.get_layer(layer_id)
    #             path = layer_id.path()
    #             pathlayers.setdefault(path, list()).append(layer_id)
    #     # Do report, taking care of not processing a path twice if overlapping
    #     visited = set()
    #     for plugin_registry in self._plugin_registries:
    #         for layer_id in plugin_registry.get_layer_ids():
    #             layer_id = plugin_registry.get_layer(layer_id)
    #             if layer_id.path() not in visited:
    #                 visited.add(layer_id.path())
    #                 for jar_path in layer_id.get_jars():
    #                     if jar_path.stat().st_size > 0:
    #                         plugin_id = Plugin.id_from_jar(jar_path)
    #                         if not any([lay.plugin_registry().has_plugin(plugin_id) for lay in pathlayers[layer_id.path()]]):
    #                             result.append([plugin_registry.id(), layer_id, jar_path, plugin_id])
    #     if len(result) > 0:
    #         self._tabulate(title, result, headers)

    def _build_plugin(self):
        # Prerequisites
        self._app.load_plugin_sets(self._args.plugin_set_catalog)
        self._app.load_plugin_signing_credentials(self._args.plugin_signing_credentials)
        self._obtain_password()
        # Action
        # ... plugin_id -> (set_id, jar_path, plugin)
        ret = self._app.build_plugin(self._get_identifiers())
        # Output
        print(tabulate.tabulate([[plugin_id, plugin.get_version(), set_id, jar_path] for plugin_id, (set_id, jar_path, plugin) in ret.items()],
                                headers=['Plugin identifier', 'Plugin version', 'Plugin set', 'Plugin JAR'],
                                tablefmt=self._args.output_format))

    def _copyright(self):
        print(lockss.turtles.__copyright__)

    def _deploy_plugin(self):
        # Prerequisites
        self._app.load_plugin_registries(self._args.plugin_registry_catalog)
        # Action
        # ... (src_path, plugin_id) -> list of (registry_id, layer_id, dst_path, plugin)
        ret = self._app.deploy_plugin(self._get_jars(),
                                      self._get_layers(),
                                      interactive=self._args.interactive)
        # Output
        print(tabulate.tabulate([[src_path, plugin_id, plugin.get_version(), registry_id, layer_id, dst_path] for (src_path, plugin_id), val in ret.items() for registry_id, layer_id, dst_path, plugin in val],
                                headers=['Plugin JAR', 'Plugin identifier', 'Plugin version', 'Plugin registry', 'Plugin registry layer', 'Deployed JAR'],
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
        print(lockss.turtles.__license__)

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

    def _make_option_plugin_registry_catalog(self, container):
        container.add_argument('--plugin-registry-catalog', '-r',
                               metavar='FILE',
                               type=Path,
                               help=f'load plugin registry catalog from %(metavar)s (default: {" or ".join(map(str, self._app.default_plugin_registry_catalogs()))})')

    def _make_option_plugin_set_catalog(self, container):
        container.add_argument('--plugin-set-catalog', '-s',
                               metavar='FILE',
                               type=Path,
                               help=f'load plugin set catalog from %(metavar)s (default: {" or ".join(map(str, self._app.default_plugin_set_catalogs()))})')

    def _make_option_plugin_signing_credentials(self, container):
        container.add_argument('--plugin-signing-credentials', '-c',
                               metavar='FILE',
                               type=Path,
                               help=f'load plugin signing credentials from %(metavar)s (default: {" or ".join(map(str, self._app.default_plugin_signing_credentials()))})')

    def _make_option_production(self, container):
        container.add_argument('--production', '-p',
                               dest='layer',
                               action='append_const',
                               const=PluginRegistryLayer.PRODUCTION,
                               help="synonym for --layer=%(const)s (i.e. add '%(const)s' to the list of plugin registry layers to process)")

    def _make_option_testing(self, container):
        container.add_argument('--testing', '-t',
                               dest='layer',
                               action='append_const',
                               const=PluginRegistryLayer.TESTING,
                               help="synonym for --layer=%(const)s (i.e. add '%(const)s' to the list of plugin registry layers to process)")

    def _make_options_identifiers(self, container):
        group = container.add_argument_group(title='plugin identifier arguments and options')
        group.add_argument('--identifier', '-i',
                           metavar='PLUGID',
                           action='append',
                           default=list(),
                           help='add %(metavar)s to the list of plugin identifiers to build')
        group.add_argument('--identifiers', '-I',
                           metavar='FILE',
                           action='append',
                           default=list(),
                           help='add the plugin identifiers in %(metavar)s to the list of plugin identifiers to build')
        group.add_argument('remainder',
                            metavar='PLUGID',
                            nargs='*',
                            help='plugin identifier to build')

    def _make_options_jars(self, container):
        group = container.add_argument_group(title='plugin JAR arguments and options')
        group.add_argument('--jar', '-j',
                           metavar='PLUGJAR',
                           type=Path,
                           action='append',
                           default=list(),
                           help='add %(metavar)s to the list of plugin JARs to deploy')
        group.add_argument('--jars', '-J',
                           metavar='FILE',
                           action='append',
                           default=list(),
                           help='add the plugin JARs in %(metavar)s to the list of plugin JARs to deploy')
        group.add_argument('remainder',
                           metavar='PLUGJAR',
                           nargs='*',
                           help='plugin JAR to deploy')

    def _make_options_layers(self, container):
        group = container.add_argument_group(title='plugin registry layer options')
        group.add_argument('--layer', '-l',
                           metavar='LAYER',
                           action='append',
                           default=list(),
                           help='add %(metavar)s to the list of plugin registry layers to process')
        group.add_argument('--layers', '-L',
                           metavar='FILE',
                           action='append',
                           default=list(),
                           help='add the layers in %(metavar)s to the list of plugin registry layers to process')

    def _make_parser(self):
        for cls in [rich_argparse.RichHelpFormatter]:
            cls.styles.update({
                'argparse.args': f'bold {cls.styles["argparse.args"]}',
                'argparse.groups': f'bold {cls.styles["argparse.groups"]}',
                'argparse.metavar': f'bold {cls.styles["argparse.metavar"]}',
                'argparse.prog': f'bold {cls.styles["argparse.prog"]}',
            })
        self._parser = argparse.ArgumentParser(prog=TurtlesCli.PROG,
                                               formatter_class=rich_argparse.RichHelpFormatter)
        self._subparsers = self._parser.add_subparsers(title='commands',
                                                       description="Add --help to see the command's own help message.",
                                                       # With subparsers, metavar is also used as the heading of the column of subcommands
                                                       metavar='COMMAND',
                                                       # With subparsers, help is used as the heading of the column of subcommand descriptions
                                                       help='DESCRIPTION')
        self._make_option_debug_cli(self._parser)
        self._make_option_non_interactive(self._parser)
        #self._make_parser_analyze_registry(self._subparsers)
        self._make_parser_build_plugin(self._subparsers)
        self._make_parser_copyright(self._subparsers)
        self._make_parser_deploy_plugin(self._subparsers)
        self._make_parser_license(self._subparsers)
        self._make_parser_release_plugin(self._subparsers)
        self._make_parser_usage(self._subparsers)
        self._make_parser_version(self._subparsers)

    # def _make_parser_analyze_registry(self, container):
    #     parser = container.add_parser('analyze-registry', aliases=['ar'],
    #                                   description='Analyze plugin registries',
    #                                   help='analyze plugin registries')
    #     parser.set_defaults(fun=self._analyze_registry)
    #     self._make_option_plugin_registry_catalog(parser)
    #     self._make_option_plugin_set_catalog(parser)
    #     self._make_option_plugin_signing(parser)

    def _make_parser_build_plugin(self, container):
        parser = container.add_parser('build-plugin', aliases=['bp'],
                                      description='Build (package and sign) plugins.',
                                      help='build (package and sign) plugins',
                                      formatter_class=self._parser.formatter_class)
        parser.set_defaults(fun=self._build_plugin)
        self._make_option_output_format(parser)
        self._make_option_password(parser)
        self._make_option_plugin_set_catalog(parser)
        self._make_option_plugin_signing_credentials(parser)
        self._make_options_identifiers(parser)

    def _make_parser_copyright(self, container):
        parser = container.add_parser('copyright',
                                      description='Show copyright and exit.',
                                      help='show copyright and exit',
                                      formatter_class=self._parser.formatter_class)
        parser.set_defaults(fun=self._copyright)

    def _make_parser_deploy_plugin(self, container):
        parser = container.add_parser('deploy-plugin', aliases=['dp'],
                                      description='Deploy plugins.',
                                      help='deploy plugins',
                                      formatter_class=self._parser.formatter_class)
        parser.set_defaults(fun=self._deploy_plugin)
        self._make_option_output_format(parser)
        self._make_option_plugin_registry_catalog(parser)
        self._make_option_production(parser)
        self._make_option_testing(parser)
        self._make_options_jars(parser)
        self._make_options_layers(parser)

    def _make_parser_license(self, container):
        parser = container.add_parser('license',
                                      description='Show license and exit.',
                                      help='show license and exit',
                                      formatter_class=self._parser.formatter_class)
        parser.set_defaults(fun=self._license)

    def _make_parser_release_plugin(self, container):
        parser = container.add_parser('release-plugin', aliases=['rp'],
                                      description='Release (build and deploy) plugins.',
                                      help='release (build and deploy) plugins',
                                      formatter_class=self._parser.formatter_class)
        parser.set_defaults(fun=self._release_plugin)
        self._make_option_output_format(parser)
        self._make_option_password(parser)
        self._make_option_plugin_registry_catalog(parser)
        self._make_option_plugin_set_catalog(parser)
        self._make_option_plugin_signing_credentials(parser)
        self._make_option_production(parser)
        self._make_option_testing(parser)
        self._make_options_identifiers(parser)
        self._make_options_layers(parser)

    def _make_parser_usage(self, container):
        parser = container.add_parser('usage',
                                      description='Show detailed usage and exit.',
                                      help='show detailed usage and exit',
                                      formatter_class=self._parser.formatter_class)
        parser.set_defaults(fun=self._usage)

    def _make_parser_version(self, container):
        parser = container.add_parser('version',
                                      description='Show version and exit.',
                                      help='show version and exit',
                                      formatter_class=self._parser.formatter_class)
        parser.set_defaults(fun=self._version)

    def _obtain_password(self):
        if self._args.password is not None:
            _p = self._args.password
        elif self._args.interactive:
            _p = getpass.getpass('Plugin signing password: ')
        else:
            self._parser.error('no plugin signing password specified while in non-interactive mode')
        self._app.set_password(lambda: _p)

    def _release_plugin(self):
        # Prerequisites
        self._app.load_plugin_sets(self._args.plugin_set_catalog)
        self._app.load_plugin_registries(self._args.plugin_registry_catalog)
        self._app.load_plugin_signing_credentials(self._args.plugin_signing_credentials)
        self._obtain_password()
        # Action
        # ... plugin_id -> list of (registry_id, layer_id, dst_path, plugin)
        ret = self._app.release_plugin(self._get_identifiers(),
                                       self._get_layers(),
                                       interactive=self._args.interactive)
        # Output
        print(tabulate.tabulate([[plugin_id, plugin.get_version(), registry_id, layer_id, dst_path] for plugin_id, val in ret.items() for registry_id, layer_id, dst_path, plugin in val],
                                headers=['Plugin identifier', 'Plugin version', 'Plugin registry', 'Plugin registry layer', 'Deployed JAR'],
                                tablefmt=self._args.output_format))

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
        print(lockss.turtles.__version__)

def main():
    TurtlesCli().run()

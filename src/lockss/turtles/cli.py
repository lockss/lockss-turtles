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
Command line tool for managing LOCKSS plugin sets and LOCKSS plugin registries.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
# Remove in Python 3.11; see https://docs.python.org/3.11/library/exceptions.html#exception-groups
from exceptiongroup import ExceptionGroup # see also 'traceback'
from importlib.metadata import entry_points
from inspect import ismethod
from itertools import chain
from pathlib import Path
from traceback import format_exception # modified by 'exceptiongroup' to handle ExceptionGroup
from typing import Optional

from click_extra import ChoiceSource, EnumChoice, ExtraContext, Section, TableFormat, color_option, echo, group, option, option_group, pass_context, pass_obj, print_table, prompt, show_params_option, table_format_option
from click_plugins import with_plugins
from lockss.pybasic.cliutil import click_path, make_extra_context_settings
from lockss.pybasic.errorutil import InternalError
from lockss.pybasic.fileutil import file_lines

from . import __copyright__, __license__, __version__
from .app import BuildPluginResult, DeployPluginResult, Turtles
from .plugin import PluginIdentifier
from .plugin_registry import PluginRegistryLayerIdentifier
from .util import file_or


@dataclass(kw_only=True)
class _Opts:
    plugin_identifier: tuple[PluginIdentifier, ...] = ()
    plugin_identifiers: tuple[Path, ...] = ()
    plugin_jar: tuple[Path, ...] = ()
    plugin_jars: tuple[Path, ...] = ()
    plugin_registry: tuple[Path, ...] = ()
    plugin_registry_catalog: tuple[Path, ...] = ()
    plugin_registry_layer: tuple[PluginRegistryLayerIdentifier, ...] = ()
    plugin_registry_layers: tuple[Path, ...] = ()
    plugin_set: tuple[Path, ...] = ()
    plugin_set_catalog: tuple[Path, ...] = ()
    plugin_signing_credentials: Optional[Path] = None
    plugin_signing_password: Optional[str] = field(default=None, repr=False)
    production: Optional[bool] = None
    testing: Optional[bool] = None
    headings: Optional[bool] = None
    interactive: Optional[bool] = None
    table_format: Optional[TableFormat] = None


class _TurtlesCli(object):

    def __init__(self, ctx: ExtraContext):
        super().__init__()
        self._ctx: ExtraContext = ctx
        self._app: Turtles = Turtles()
        self._errs: list[Exception] = []
        self._opts: Optional[_Opts] = None

    def build_plugin(self) -> None:
        """
        Implementation of the ``build-plugin`` command.
        """
        self._initialize_plugin_building_operation()
        self._fail_if_errs()
        ret: dict[str, BuildPluginResult] = self._app.build_plugin(self._get_plugin_identifiers())
        print_table([[plugin_id, plugin.get_version(), set_id, jar_path] for plugin_id, (set_id, jar_path, plugin) in ret.items()],
                    headers=['Plugin identifier', 'Plugin version', 'Plugin set', 'Plugin JAR'] if (opts := self._opts).headings else None,
                    table_format=opts.table_format)

    def deploy_plugin(self) -> None:
        """
        Implementation of the ``deploy_plugin`` command.
        """
        self._initialize_plugin_deployment_operation()
        self._fail_if_errs()
        ret: dict[tuple[Path, PluginIdentifier], list[DeployPluginResult]] = self._app.deploy_plugin(self._get_plugin_jars(),
                                                                                                     self._get_plugin_registry_layers(),
                                                                                                     interactive=(opts := self._opts).interactive)
        print_table([[src_path, plugin_id, plugin.get_version(), registry_id, layer_id, dst_path] for (src_path, plugin_id), val in ret.items() for registry_id, layer_id, dst_path, plugin in val],
                    headers=['Plugin JAR', 'Plugin identifier', 'Plugin version', 'Plugin registry', 'Plugin registry layer', 'Deployed JAR'] if opts.headings else None,
                    table_format=opts.table_format)

    def dispatch(self, method: Callable[[], None], **cli_kwargs) -> None:
        if not ismethod(method):
            raise InternalError() from ValueError(method)
        self._opts = _Opts(**cli_kwargs)
        method()

    def release_plugin(self) -> None:
        """
        Implementation of the ``release-plugin`` command.
        """
        self._initialize_plugin_building_operation()
        self._initialize_plugin_deployment_operation()
        self._fail_if_errs()
        ret: dict[PluginIdentifier, list[DeployPluginResult]] = self._app.release_plugin(self._get_plugin_identifiers(),
                                                                                         self._get_plugin_registry_layers(),
                                                                                         interactive=(opts := self._opts).interactive) # FIXME
        print_table([[plugin_id, plugin.get_version(), registry_id, layer_id, dst_path] for plugin_id, val in ret.items() for registry_id, layer_id, dst_path, plugin in val],
                    headers=['Plugin identifier', 'Plugin version', 'Plugin registry', 'Plugin registry layer', 'Deployed JAR'] if opts.headings else None,
                    table_format=opts.table_format)

    def _fail_if_errs(self) -> None:
        if errs := self._errs:
            self._ctx.fail(''.join(format_exception(ExceptionGroup(f'{"Errors" if errs else "Error"} loading configuration files', errs))))

    def _get_plugin_identifiers(self) -> list[PluginIdentifier]:
        """
        Returns the cumulative list of plugin identifiers, from
        ``plugin_identifier`` and the identifiers in ``plugin_identifiers``
         files.

        :return: The cumulative list of plugin identifiers, from
                ``plugin_identifier`` and the identifiers in
                ``plugin_identifiers`` files.
        :rtype: list[PluginIdentifier]
        """
        ret = [*((opts := self._opts).plugin_identifier or []),
               *chain.from_iterable(file_lines(file_path) for file_path in opts.plugin_identifiers or [])]
        if ret:
            return ret
        self._ctx.fail('Empty list of plugin identifiers')

    def _get_plugin_jars(self) -> list[Path]:
        """
        Returns the cumulative list of plugin JARs, from ``plugin_jar`` and the
        plugin JARs in ``plugin_jars``
         files.

        :return: The cumulative list of plugin JARs, from ``plugin_jar`` and the
                 plugin JARs in ``plugin_jars`` files.
        :rtype: list[Path]
        """
        ret = [*((opts := self._opts).plugin_jar or []),
               *chain.from_iterable(file_lines(file_path) for file_path in opts.plugin_jars or [])]
        if ret:
            return ret
        self._ctx.fail('Empty list of plugin JARs')

    def _get_plugin_registries(self) -> list[Path]:
        """
        Returns the cumulative plugin registry files.

        :return: The cumulative plugin registry files (possibly an empty list).
        :rtype: list[Path]
        """
        return self._opts.plugin_registry or []

    def _get_plugin_registry_catalogs(self) -> list[Path]:
        """
        Returns the cumulative plugin registry catalog files.

        :return: The cumulative plugin registry catalog files if any plugin set
                 files or plugin registry catalog files are specified (possibly
                 an empty list), or the first default plugin registry catalog
                 file if no plugin registry files nor plugin registry catalog
                 files are specified.
        :rtype: list[Path]
        """
        if (opts := self._opts).plugin_registry or opts.plugin_registry_catalog:
            return opts.plugin_registry_catalog or []
        if single := Turtles.select_default_plugin_registry_catalog():
            return [single]
        self._ctx.fail(f'No default plugin registry catalog definition file found: {file_or(Turtles.default_plugin_registry_catalog_choices())}')

    def _get_plugin_registry_layers(self) -> list[PluginRegistryLayerIdentifier]:
        """
        Returns the cumulative list of plugin registry layer identifiers, from
        ``plugin_registry_layer`` and the identifiers in
        ``plugin_registry_layers`` files.

        :return: The cumulative list of plugin registry layer identifiers, from
                ``plugin_registry_layer`` and the identifiers in
                ``plugin_registry_layers`` files.
        :rtype: list[PluginRegistryLayerIdentifier]
        """
        ret = [*((opts := self._opts).plugin_registry_layer or []),
               *chain.from_iterable(file_lines(file_path) for file_path in opts.plugin_registry_layers or [])]
        for layer in reversed(['testing', 'production']):
            if getattr(opts, layer, False) and layer not in ret:
                ret.insert(0, layer)
        if ret:
            return ret
        self._ctx.fail('Empty list of plugin registry layers')

    def _get_plugin_sets(self) -> list[Path]:
        """
        Returns the cumulative plugin set files.

        :return: The cumulative plugin set files (possibly an empty list).
        :rtype: list[Path]
        """
        return self._opts.plugin_set or []

    def _get_plugin_set_catalogs(self) -> list[Path]:
        """
        Returns the cumulative plugin set catalog files.

        :return: The cumulative plugin set catalog files if any plugin set files
                 or plugin set catalog files are specified (possibly an empty
                 list), or the first default plugin set catalog file if no
                 plugin set files nor plugin set catalog files are specified.
        :rtype: list[Path]
        """
        if (opts := self._opts).plugin_set or opts.plugin_set_catalog:
            return opts.plugin_set_catalog or []
        if single := Turtles.select_default_plugin_set_catalog():
            return [single]
        self._ctx.fail(f'No default plugin set catalog definition file found: {file_or(Turtles.default_plugin_set_catalog_choices())}')

    def _get_plugin_signing_credentials(self) -> Path:
        """
        Returns the plugin signing credentials file.

        :return: The plugin signing credentials file, or the first default
                 plugin signing credentials file if not specified.
        :rtype: Path
        """
        if psc := self._opts.plugin_signing_credentials:
            return psc
        if ret := Turtles.select_default_plugin_signing_credentials():
            return ret
        self._ctx.fail(f'No default plugin signing credentials file found: {file_or(Turtles.default_plugin_signing_credentials_choices())}')

    def _initialize_plugin_building_operation(self) -> None:
        app, errs = self._app, self._errs
        for psc in self._get_plugin_set_catalogs():
            try:
                app.load_plugin_set_catalogs(psc)
            except ValueError as ve:
                errs.append(ve)
            except ExceptionGroup as eg:
                errs.extend(eg.exceptions)
        for ps in self._get_plugin_sets():
            try:
                app.load_plugin_sets(ps)
            except ValueError as ve:
                errs.append(ve)
            except ExceptionGroup as eg:
                errs.extend(eg.exceptions)
        try:
            app.load_plugin_signing_credentials(self._get_plugin_signing_credentials())
        except ValueError as ve:
            errs.append(ve)
        except ExceptionGroup as eg:
            errs.extend(eg.exceptions)
        self._obtain_plugin_signing_password()

    def _initialize_plugin_deployment_operation(self) -> None:
        app = self._app
        errs = []
        for prc in self._get_plugin_registry_catalogs():
            try:
                app.load_plugin_registry_catalogs(prc)
            except ValueError as ve:
                errs.append(ve)
            except ExceptionGroup as eg:
                errs.extend(eg.exceptions)
        for pr in self._get_plugin_registries():
            try:
                app.load_plugin_registries(pr)
            except ValueError as ve:
                errs.append(ve)
            except ExceptionGroup as eg:
                errs.extend(eg.exceptions)

    def _obtain_plugin_signing_password(self) -> None:
        if (opts := self._opts).plugin_signing_password is None:
            if not opts.interactive:
                self._ctx.fail(f'Cannot prompt for plugin signing plugin in non-interactive mode')
            self._app.set_plugin_signing_password(prompt('Plugin signing password', hide_input=True))
            opts.plugin_signing_password = ''


_interactive_option = option('--interactive/--non-interactive', is_flag=True, default=True, help='Set whether to allow interactive prompts for the plugin signing password or for first-time deployment confirmations.')


_output_option_group = option_group(
    'Output options',
    option('--headings/--no-headings', is_flag=True, default=True, help='Set whether to include column headings in tabular output.'),
    option('--table-format', '-T', type=EnumChoice(TableFormat, choice_source=ChoiceSource.VALUE), default=TableFormat.SIMPLE, show_default=True, help=f'Set the rendering of tables to the given style.')
)


_plugin_building_option_group = option_group(
    'Plugin building options',
    option('--plugin-set', '-s', metavar='FILE', type=click_path('ferz'), multiple=True, help='Add the plugin set definitions from FILE to the loaded plugin sets.'),
    option('--plugin-set-catalog', '-S', metavar='FILE', type=click_path('ferz'), multiple=True, show_default=f'if no plugin sets or plugin set catalogs are specified: {file_or(Turtles.default_plugin_set_catalog_choices())}', help=f'Add the plugin set catalog definitions from FILE to the loaded plugin set catalogs.'),
    option('--plugin-signing-credentials', '-c', metavar='FILE', type=click_path('ferz'), show_default=f'{file_or(Turtles.default_plugin_signing_credentials_choices())}', help=f'Load the plugin signing credentials from FILE.'),
    option('--plugin-signing-password', '-P', metavar='PASS', show_default='interactive prompt', help='Set the plugin signing password to PASS.')
)


_plugin_deployment_option_group = option_group(
    'Plugin deployment options',
    option('--plugin-registry', '-r', metavar='FILE', type=click_path('ferz'), multiple=True, help='Add the plugin registry definitions from FILE to the loaded plugin registries.'),
    option('--plugin-registry-catalog', '-R', metavar='FILE', type=click_path('ferz'), multiple=True, show_default=f'if no plugin registries or plugin registry catalogs are specified: {file_or(Turtles.default_plugin_registry_catalog_choices())}', help=f'Add the plugin registry catalog definitions from FILE to the loaded plugin registry catalogs.')
)


_plugin_identifier_option_group = option_group(
    'Plugin identifier options',
    option('--plugin-identifier', '-i', metavar='IDENT', multiple=True, help='Add IDENT to the list of plugin identifiers to process.'),
    option('--plugin-identifiers', '-I', metavar='FILE', type=click_path('ferz'), multiple=True, help='Add the plugin identifiers from FILE to the list of plugin identifiers to process.')
)


_plugin_jar_option_group = option_group(
    'Plugin JAR options',
    option('--plugin-jar', '-j', metavar='FILE', type=click_path('ferz'), multiple=True, help='Add FILE to the list of plugin JARs to process.'),
    option('--plugin-jars', '-J', metavar='FILE', type=click_path('ferz'), multiple=True, help='Add the plugin JARs from FILE to the list of plugin JARs to process.')
)


_plugin_registry_layer_option_group = option_group(
    'Plugin registry layer options',
    option('--plugin-registry-layer', '-l', metavar='IDENT', multiple=True, help='Add IDENT to the list of plugin registry layers to process.'),
    option('--plugin-registry-layers', '-L', metavar='FILE', type=click_path('ferz'), multiple=True, help='Add the plugin registry layers from FILE to the list of plugin registry layers to process.'),
    option('--production', '-p', is_flag=True, help='Add "production" to the list of plugin registry layers to process.'),
    option('--testing', '-t', is_flag=True, help='Add "testing" to the list of plugin registry layers to process.')
)


@with_plugins(entry_points(module='click_command_tree')) # adds a 'tree' command
@group('turtles', params=None, context_settings=make_extra_context_settings())
@color_option
@show_params_option
@pass_context
def _turtles(ctx: ExtraContext, **kwargs) -> None:
    ctx.obj = _TurtlesCli(ctx)


_COMMANDS = Section('Principal commands')


@_turtles.command('build-plugin', aliases=['bp'], section=_COMMANDS, help='Build (package and sign) plugins.')
@_plugin_identifier_option_group
@_plugin_building_option_group
@_output_option_group
@_interactive_option
@pass_obj
def _build_plugin(cli: _TurtlesCli, **kwargs) -> None:
    cli.dispatch(cli.build_plugin, **kwargs)


@_turtles.command('copyright', help='Show the copyright and exit.')
def _copyright() -> None:
    echo(__copyright__)


@_turtles.command('deploy-plugin', aliases=['dp'], section=_COMMANDS, help='Deploy plugins.')
@_plugin_jar_option_group
@_plugin_registry_layer_option_group
@_plugin_deployment_option_group
@_output_option_group
@_interactive_option
@pass_obj
def _deploy_plugin(cli: _TurtlesCli, **kwargs) -> None:
    cli.dispatch(cli.deploy_plugin, **kwargs)


@_turtles.command('license', help='Show the software license and exit.')
def _license() -> None:
    echo(__license__)


@_turtles.command('release-plugin', aliases=['rp'], section=_COMMANDS, help='Release (build and deploy) plugins.')
@_plugin_identifier_option_group
@_plugin_registry_layer_option_group
@_plugin_building_option_group
@_plugin_deployment_option_group
@_output_option_group
@_interactive_option
@pass_obj
def _release_plugin(cli: _TurtlesCli, **kwargs) -> None:
    cli.dispatch(cli.release_plugin, **kwargs)


# 'tree' command implied by click_command_tree plugin


@_turtles.command('version', help='Show the version number and exit.')
def _version() -> None:
    echo(__version__)


def main() -> None:
    """
    Main entry point of the module.
    """
    _turtles()


# Main entry point of the module.
if __name__ == '__main__':
    main()

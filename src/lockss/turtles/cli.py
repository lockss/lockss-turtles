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
Tool for managing LOCKSS plugin sets and LOCKSS plugin registries
"""

from getpass import getpass
from pathlib import Path

from lockss.pybasic.cliutil import BaseCli, StringCommand, COPYRIGHT_DESCRIPTION, LICENSE_DESCRIPTION, VERSION_DESCRIPTION
from lockss.pybasic.fileutil import file_lines, path
from lockss.pybasic.outpututil import OutputFormatOptions
from pydantic.v1 import BaseModel, Field, FilePath
from pydantic.v1.class_validators import validator
import tabulate
from typing import Optional

from lockss.turtles.plugin_registry import PluginRegistryLayer
from . import __copyright__, __license__, __version__
from .app import TurtlesApp
from .plugin_registry import PluginRegistryLayerIdentifier
from .util import file_or


class PluginBuildingOptions(BaseModel):
    plugin_set: Optional[list[FilePath]] = Field(aliases=['-s'], description=f'(plugin set) add one or more plugin sets to the loaded plugin sets')
    plugin_set_catalog: Optional[list[FilePath]] = Field(aliases=['-S'], description=f'(plugin set) add one or more plugin set catalogs to the loaded plugin set catalogs; if no plugin set catalogs or plugin sets are specified, load {file_or(TurtlesApp.default_plugin_set_catalog_choices())}')
    plugin_signing_credentials: Optional[FilePath] = Field(aliases=['-c'], description=f'(plugin signing credentials) load the plugin signing credentials from the given file, or if none, from {file_or(TurtlesApp.default_plugin_signing_credentials_choices())}')
    plugin_signing_password: Optional[str] = Field(description='(plugin signing credentials) set the plugin signing password, or if none, prompt interactively')

    def get_plugin_sets(self) -> list[Path]:
        return [path(p) for p in self.plugin_set or []]

    def get_plugin_set_catalogs(self) -> list[Path]:
        if self.plugin_set or self.plugin_set_catalog:
            return [path(p) for p in self.plugin_set_catalog or []]
        if single := TurtlesApp.select_default_plugin_set_catalog():
            return [single]
        raise FileNotFoundError(file_or(TurtlesApp.default_plugin_set_catalog_choices()))


class PluginDeploymentOptions(BaseModel):
    plugin_registry: Optional[list[FilePath]] = Field(aliases=['-r'], description=f'(plugin registry) add one or more plugin registries to the loaded plugin registries')
    plugin_registry_catalog: Optional[list[FilePath]] = Field(aliases=['-R'], description=f'(plugin registry) add one or more plugin registry catalogs to the loaded plugin registry catalogs; if no plugin registry catalogs or plugin registries are specified, load {file_or(TurtlesApp.default_plugin_registry_catalog_choices())}')
    plugin_registry_layer: Optional[list[str]] = Field(aliases=['-l'], description='(plugin registry layers) add one or more plugin registry layers to the set of plugin registry layers to process')
    plugin_registry_layers: Optional[list[FilePath]] = Field(aliases=['-L'], description='(plugin registry layers) add the plugin registry layers listed in one or more files to the set of plugin registry layers to process')
    testing: Optional[bool] = Field(False, aliases=['-t'], description='(plugin registry layers) synonym for --plugin-registry-layer testing (i.e. add "testing" to the list of plugin registry layers to process)')
    production: Optional[bool] = Field(False, aliases=['-p'], description='(plugin registry layers) synonym for --plugin-registry-layer production (i.e. add "production" to the list of plugin registry layers to process)')

    @validator('plugin_registry_layers', each_item=True, pre=True)
    def _expand_each_plugin_registry_layers_path(cls, v: Path) -> Path:
        return path(v)

    def get_plugin_registries(self) -> list[Path]:
        return [path(p) for p in self.plugin_registry or []]

    def get_plugin_registry_catalogs(self) -> list[Path]:
        if self.plugin_registry or self.plugin_registry_catalog:
            return [path(p) for p in self.plugin_registry_catalog or []]
        if single := TurtlesApp.select_default_plugin_registry_catalog():
            return [single]
        raise FileNotFoundError(file_or(TurtlesApp.default_plugin_set_catalog_choices()))

    def get_plugin_registry_layers(self) -> list[PluginRegistryLayerIdentifier]:
        ret = [*(self.plugin_registry_layer or []), *[file_lines(file_path) for file_path in self.plugin_registry_layers or []]]
        for layer in reversed(['testing', 'production']):
            if getattr(self, layer, False):
                ret.insert(0, layer)
        if ret:
            return ret
        raise ValueError('Empty list of plugin registry layers')


class PluginIdentifierOptions(BaseModel):
    """
    The --identifier/-i and --identifiers/-I options.
    """
    plugin_identifier: Optional[list[str]] = Field(aliases=['-i'], description='(plugin identifiers) add one or more plugin identifiers to the set of plugin identifiers to process')
    plugin_identifiers: Optional[list[FilePath]] = Field(aliases=['-I'], description='(plugin identifiers) add the plugin identifiers listed in one or more files to the set of plugin identifiers to process')

    @validator('plugin_identifiers', each_item=True, pre=True)
    def _expand_each_plugin_identifiers_path(cls, v: Path) -> Path:
        return path(v)

    def get_plugin_identifiers(self) -> list[str]:
        ret = [*(self.plugin_identifier or []), *[file_lines(file_path) for file_path in self.plugin_identifiers or []]]
        if ret:
            return ret
        raise ValueError('Empty list of plugin identifiers')


class PluginJarOptions(BaseModel):
    """
    The --plugin-jar/-j and --plugin-jars/-J options.
    """
    plugin_jar: Optional[list[FilePath]] = Field(aliases=['-j'], description='(plugin JARs) add one or more plugin JARs to the set of plugin JARs to process')
    plugin_jars: Optional[list[FilePath]] = Field(aliases=['-J'], description='(plugin JARs) add the plugin JARs listed in one or more files to the set of plugin JARs to process')

    @validator('plugin_jar', 'plugin_jars', each_item=True, pre=True)
    def _expand_each_plugin_jars_path(cls, v: Path) -> Path:
        return path(v)

    def get_plugin_jars(self):
        ret = [*(self.plugin_jar or []), *[file_lines(file_path) for file_path in self.plugin_jars or []]]
        if len(ret):
            return ret
        raise ValueError('Empty list of plugin JARs')


class NonInteractiveOptions(BaseModel):
    non_interactive: Optional[bool] = Field(False, description='(plugin signing credentials) disallow interactive prompts')


class BuildPluginCommand(OutputFormatOptions, NonInteractiveOptions, PluginBuildingOptions, PluginIdentifierOptions):
    pass


class DeployPluginCommand(OutputFormatOptions, NonInteractiveOptions, PluginDeploymentOptions, PluginJarOptions):
    pass


class ReleasePluginCommand(OutputFormatOptions, NonInteractiveOptions, PluginDeploymentOptions, PluginBuildingOptions, PluginIdentifierOptions):
    pass


class TurtlesCommand(BaseModel):
    bp: Optional[BuildPluginCommand] = Field(description='synonym for: build-plugin')
    build_plugin: Optional[BuildPluginCommand] = Field(description='build (package and sign) plugins')
    copyright: Optional[StringCommand.type(__copyright__)] = Field(description=COPYRIGHT_DESCRIPTION)
    deploy_plugin: Optional[DeployPluginCommand] = Field(description='deploy plugins')
    dp: Optional[DeployPluginCommand] = Field(description='synonym for: deploy-plugin')
    license: Optional[StringCommand.type(__license__)] = Field(description=LICENSE_DESCRIPTION)
    release_plugin: Optional[ReleasePluginCommand] = Field(description='release (build and deploy) plugins')
    rp: Optional[ReleasePluginCommand] = Field(description='synonym for: release-plugin')
    version: Optional[StringCommand.type(__version__)] = Field(description=VERSION_DESCRIPTION)


class TurtlesCli(BaseCli[TurtlesCommand]):

    def __init__(self):
        super().__init__(model=TurtlesCommand,
                         prog='turtles',
                         description='Tool for managing LOCKSS plugin sets and LOCKSS plugin registries')
        self._app: TurtlesApp = TurtlesApp()

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

    def _bp(self, build_plugin_command: BuildPluginCommand) -> None:
        return self._build_plugin(build_plugin_command)

    def _build_plugin(self, build_plugin_command: BuildPluginCommand) -> None:
        for psc in build_plugin_command.get_plugin_set_catalogs():
            self._app.load_plugin_set_catalogs(psc)
        for ps in build_plugin_command.get_plugin_sets():
            self._app.load_plugin_sets(ps)
        # Prerequisites
        self._app.load_plugin_sets(build_plugin_command.plugin_set_catalog)
        self._app.load_plugin_signing_credentials(build_plugin_command.plugin_signing_credentials)
        self._obtain_password(build_plugin_command)
        # Action
        # ... plugin_id -> (set_id, jar_path, plugin)
        ret = self._app.build_plugin(build_plugin_command.get_plugin_identifiers())
        # Output
        print(tabulate.tabulate([[plugin_id, plugin.get_version(), set_id, jar_path] for plugin_id, (set_id, jar_path, plugin) in ret.items()],
                                headers=['Plugin identifier', 'Plugin version', 'Plugin set', 'Plugin JAR'],
                                tablefmt=build_plugin_command.output_format))

    def _copyright(self, string_command: StringCommand) -> None:
        self._do_string_command(string_command)

    def _deploy_plugin(self, deploy_plugin_command: DeployPluginCommand) -> None:
        # Prerequisites
        self._app.load_plugin_registries(deploy_plugin_command.plugin_registry_catalog)
        # Action
        # ... (src_path, plugin_id) -> list of (registry_id, layer_id, dst_path, plugin)
        ret = self._app.deploy_plugin(deploy_plugin_command.get_plugin_jars(),
                                      deploy_plugin_command.get_plugin_registry_layers(),
                                      interactive=not deploy_plugin_command.non_interactive)
        # Output
        print(tabulate.tabulate([[src_path, plugin_id, plugin.get_version(), registry_id, layer_id, dst_path] for (src_path, plugin_id), val in ret.items() for registry_id, layer_id, dst_path, plugin in val],
                                headers=['Plugin JAR', 'Plugin identifier', 'Plugin version', 'Plugin registry', 'Plugin registry layer', 'Deployed JAR'],
                                tablefmt=deploy_plugin_command.output_format))

    def _do_string_command(self, string_command: StringCommand) -> None:
        string_command()

    def _dp(self, deploy_plugin_command: DeployPluginCommand) -> None:
        return self._deploy_plugin(deploy_plugin_command)

    def _license(self, string_command: StringCommand) -> None:
        self._do_string_command(string_command)

    def _obtain_password(self, non_interactive_options: NonInteractiveOptions) -> None:
        if non_interactive_options.plugin_signing_password is not None:
            _p = non_interactive_options.plugin_signing_password
        elif non_interactive_options.non_interactive:
            _p = getpass('Plugin signing password: ')
        else:
            self._parser.error('no plugin signing password specified while in non-interactive mode')
        self._app.set_password(lambda: _p)

    def _release_plugin(self, release_plugin_command: ReleasePluginCommand) -> None:
        # Prerequisites
        self._app.load_plugin_sets(release_plugin_command.plugin_set_catalog)
        self._app.load_plugin_registries(release_plugin_command.plugin_registry_catalog)
        self._app.load_plugin_signing_credentials(release_plugin_command.plugin_signing_credentials)
        self._obtain_password(release_plugin_command)
        # Action
        # ... plugin_id -> list of (registry_id, layer_id, dst_path, plugin)
        ret = self._app.release_plugin(release_plugin_command.get_plugin_identifiers(),
                                       release_plugin_command.get_plugin_registry_layers(),
                                       interactive=not release_plugin_command.non_interactive)
        # Output
        print(tabulate.tabulate([[plugin_id, plugin.get_version(), registry_id, layer_id, dst_path] for plugin_id, val in ret.items() for registry_id, layer_id, dst_path, plugin in val],
                                headers=['Plugin identifier', 'Plugin version', 'Plugin registry', 'Plugin registry layer', 'Deployed JAR'],
                                tablefmt=release_plugin_command.output_format))

    def _rp(self, release_plugin_command: ReleasePluginCommand) -> None:
        self._release_plugin(release_plugin_command)

    def _version(self, string_command: StringCommand) -> None:
        self._do_string_command(string_command)


def main():
    TurtlesCli().run()


if __name__ == '__main__':
    main()

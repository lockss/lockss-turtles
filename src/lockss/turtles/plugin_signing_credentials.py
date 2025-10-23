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
Module to represent plugin signing credentials.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field

from .util import BaseModelWithRoot


#: A type alias for the plugin signing credentials kind.
PluginSigningCredentialsKind = Literal['PluginSigningCredentials']


class PluginSigningCredentials(BaseModelWithRoot):
    """
    A Pydantic model (``lockss.turtles.util.BaseModelWithRoot``) to represent
    plugin signing credentials.
    """

    #: This object's kind.
    kind: PluginSigningCredentialsKind = Field(title='Kind',
                                               description="This object's kind")

    #: Path to the plugin signing keystore.
    plugin_signing_keystore: str = Field(alias='plugin-signing-keystore',
                                         title='Plugin Signing Keystore',
                                         description='A path to the plugin signing keystore')

    #: Alias to use from the plugin signing keystore.
    plugin_signing_alias: str = Field(alias='plugin-signing-alias',
                                      title='Plugin Signing Alias',
                                      description='The plugin signing alias to use')

    def get_plugin_signing_alias(self) -> str:
        """
        Returns the alias to use from the plugin signing keystore.

        :return: The plugin signing alias.
        :rtype: str
        """
        return self.plugin_signing_alias

    def get_plugin_signing_keystore(self) -> Path:
        """
        The file path for the plugin signing keystore; a relative path is
        understood to be relative to the file containing the definition.

        :return: The file path for the plugin signing keystore.
        :rtype: Path
        """
        return self.get_root().joinpath(self.plugin_signing_keystore)

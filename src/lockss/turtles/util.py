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
Utility module.
"""

# Remove in Python 3.14; see https://stackoverflow.com/a/33533514
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional, Union

from lockss.pybasic.fileutil import path
from pydantic import BaseModel


#: Type alias for the union of ``Path`` and ``str``.
PathOrStr = Union[Path, str]


class BaseModelWithRoot(BaseModel):
    """
    A Pydantic model with a root path which can be used to resolve relative
    paths.
    """

    #: An internal root path.
    _root: Optional[Path]

    def model_post_init(self, context: Any) -> None:
        """
        Pydantic post-initialization method to create the ``_root`` field.
        """
        self._root = None

    def get_root(self) -> Path:
        """
        Returns this object's root path.

        See ``initialize``.

        :return: This object's root path.
        :rtype: Path
        :raises ValueError: If this object's ``initialize`` method was not
                            called.
        """
        if self._root is None:
            raise ValueError('Uninitialized root')
        return self._root

    def initialize(self,
                   root_path_or_str: PathOrStr) -> BaseModelWithRoot:
        """
        Mandatory initialization of the root path.

        :param root_path_or_str: This object's root path.
        :type root_path_or_str: PathOrStr
        :return: This object, for chaining.
        :rtype: BaseModelWithRoot
        """
        self._root = path(root_path_or_str)
        return self


def file_or(paths: Iterable[Path]) -> str:
    """
    Turns an iterable of file paths into a ``" or "``-separated string suitable
    for CLI messages.

    :param paths: A non-null list of file paths.
    :type paths: Iterable[Path]
    :return: A ``" or "``-separated string of the given file paths.
    :rtype: str
    """
    return ' or '.join(map(str, paths))

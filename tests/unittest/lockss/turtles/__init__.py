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

from collections.abc import Callable
from pathlib import Path
from pydantic import ValidationError
from pydantic_core import ErrorDetails
from typing import Any, Optional, Tuple, Union
from unittest import TestCase


ROOT: Path = Path('.').absolute()


Loc = Union[Tuple[str], str]


class PydanticTestCase(TestCase):

    def assertPydanticListType(self, func: Callable[[], Any], loc_tuple_or_str: Loc, msg=None) -> None:
        self._assertPydanticValidationError(func,
                                            lambda e: e.get('type') == 'list_type' \
                                                      and e.get('loc') == self._loc(loc_tuple_or_str),
                                            msg=msg)

    def assertPydanticLiteralError(self, func: Callable[[], Any], loc_tuple_or_str: Loc, expected: Union[Tuple[str], str], msg=None) -> None:
        if isinstance(expected, str):
            exp = f"'{expected}'"
        elif len(expected) == 0:
            raise RuntimeError(f"'expected' cannot be an empty tuple")
        elif len(expected) == 1:
            exp = f"'{expected[0]}'"
        else:
            exp = f'''{", ".join(f"'{e}'" for e in expected[:-1])} or '{expected[-1]}\''''
        self._assertPydanticValidationError(func,
                                            lambda e: e.get('type') == 'literal_error' \
                                                      and e.get('loc') == self._loc(loc_tuple_or_str) \
                                                      and (ctx := e.get('ctx')) \
                                                      and ctx.get('expected') == exp,
                                            msg=msg)

    def assertPydanticModelAttributesType(self, func: Callable[[], Any], loc_tuple_or_str: Loc, msg=None) -> None:
        self._assertPydanticValidationError(func,
                                            lambda e: e.get('type') == 'model_attributes_type' \
                                                      and e.get('loc') == self._loc(loc_tuple_or_str),
                                            msg=msg)

    def assertPydanticMissing(self, func: Callable[[], Any], loc_tuple_or_str: Loc, msg=None) -> None:
        self._assertPydanticValidationError(func,
                                            lambda e: e.get('type') == 'missing' \
                                                      and e.get('loc') == self._loc(loc_tuple_or_str),
                                            msg=msg)

    def assertPydanticStringType(self, func: Callable[[], Any], loc_tuple_or_str: Loc, msg=None) -> None:
        self._assertPydanticValidationError(func,
                                            lambda e: e.get('type') == 'string_type' \
                                                      and e.get('loc') == self._loc(loc_tuple_or_str),
                                            msg=msg)

    def assertPydanticTooShort(self, func: Callable[[], Any], loc_tuple_or_str: Loc, msg=None) -> None:
        self._assertPydanticValidationError(func,
                                            lambda e: e.get('type') == 'too_short' \
                                                      and e.get('loc') == self._loc(loc_tuple_or_str),
                                            msg=msg)

    def _assertPydanticValidationError(self,
                                       func: Callable[[], Any],
                                       matcher: Callable[[ErrorDetails], bool],
                                       msg: Optional[str]=None) -> None:
        with self.assertRaises(ValidationError) as cm:
            func()
        ve: ValidationError = cm.exception
        for e in ve.errors():
            if matcher(e):
                return
        self.fail(msg or f'Did not get a matching ValidationError; got:\n{"\n".join([str(e) for e in ve.errors()])}\n{ve!s}')

    def _loc(self, loc_tuple_or_str: Loc) -> tuple[str]:
        return (loc_tuple_or_str,) if isinstance(loc_tuple_or_str, str) else loc_tuple_or_str

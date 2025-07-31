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
from pydantic import ValidationError
from pydantic_core import ErrorDetails
from typing import Any, Optional, Tuple, Union
from unittest import TestCase


Loc = Union[Tuple[str], str]


class PydanticTestCase(TestCase):

    def _assertPydanticValidationError(self,
                                       func: Callable[[], Any],
                                       matcher: Callable[[ErrorDetails], bool],
                                       msg: Optional[str]=None):
        with self.assertRaises(ValidationError) as cm:
            func()
            self.fail('Expected ValidationError but did not get one')
        self.assertIsInstance(cm.exception, ValidationError)
        ve: ValidationError = cm.exception
        for e in ve.errors():
            if matcher(e):
                return
        self.fail(msg or f'Did not get a matching ValidationError; got:\n{"\n".join([str(e) for e in ve.errors()])}\n{ve!s}')

    def assertPydanticMissing(self, func: Callable[[], Any], loc: Loc, msg=None) -> None:
        if isinstance(loc, str):
            loc = (loc,)
        self._assertPydanticValidationError(func, lambda e: e.get('type') == 'missing' and e.get('loc') == loc)

    def assertPydanticLiteralError(self, func: Callable[[], Any], loc: Loc, expected: str, msg=None) -> None:
        if isinstance(loc, str):
            loc = (loc,)
        self._assertPydanticValidationError(func, lambda e: e.get('type') == 'literal_error' and e.get('loc') == loc and (ctx := e.get('ctx')) and ctx.get('expected') == repr(expected))

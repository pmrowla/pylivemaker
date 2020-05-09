# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Peter Rowlands <peter@pmrowla.com>
# Copyright (C) 2014 tinfoil <https://bitbucket.org/tinfoil/>
#
# This file is a part of pylivemaker.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.
"""pylivemaker translatable text module."""

from abc import ABC
from hashlib import blake2b

from funcy import cached_property

from ..exceptions import BadTextIdentifierError, InvalidCharError


class BaseTranslatable(ABC):
    """Base class for translatable text objects."""

    def __init__(self, text):
        self._orig_text = "\n".join(text.splitlines())
        self.text = self._orig_text

    @property
    def orig_text(self):
        return self._orig_text

    @property
    def text(self):
        return "\n".join(self._text)

    @text.setter
    def text(self, text):
        for ch in text:
            try:
                ch.encode("cp932")
            except UnicodeEncodeError:
                raise InvalidCharError(ch)
        self._text = text.splitlines()

    @cached_property
    def digest(self):
        return self.text_digest(self.orig_text)

    def __str__(self):
        return str(self.text)

    def __hash__(self):
        return hash(self.digest)

    def __eq__(self, other):
        return hash(self) == hash(other)

    @staticmethod
    def text_digest(text):
        hash_ = blake2b(digest_size=8)
        hash_.update(text.encode("utf-8"))
        return hash_.hexdigest()


class BaseTextIdentifier:
    """Base identifier for translatable text inside an LSB."""

    type = "base"

    def __init__(self, filename, line_no, name=""):
        self.filename = filename
        self.line_no = int(line_no)
        self.name = name

    def __hash__(self):
        return hash(self.parts)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __str__(self):
        return ":".join([str(x) for x in self.parts])

    @property
    def _parts(self):
        return []

    @property
    def parts(self):
        return ("pylm", self.type, self.filename, self.line_no, *self._parts)

    @classmethod
    def from_string(cls, string, **kwargs):
        parts = string.split(":")
        if len(parts) < 2 or parts[0] != "pylm":
            raise BadTextIdentifierError(f"{string} is not a valid pylm identifier")
        if parts[1] != cls.type:
            raise BadTextIdentifierError(f"{string} is not a valid pylm:{cls.type} identifier")
        try:
            return cls(*parts[2:], **kwargs)
        except ValueError as e:
            raise BadTextIdentifierError(f"{string} is not a valid pylm:{cls.type} identifier: {e}")


class TextBlockIdentifier(BaseTextIdentifier):
    """Identifier for scenario text block."""

    type = "text"

    def __init__(self, filename, line_no, block_index, **kwargs):
        super().__init__(filename, line_no, **kwargs)
        self.block_index = int(block_index)

    @property
    def _parts(self):
        return (self.block_index,)


class BaseMenuIdentifier(BaseTextIdentifier):
    """Base identifier for selection menus."""

    type = "menu"

    def __init__(self, filename, line_no, choice_index, **kwargs):
        super().__init__(filename, line_no, **kwargs)
        self.choice_index = int(choice_index)

    @property
    def _parts(self):
        return (self.choice_index,)


class TextMenuIdentifier(BaseMenuIdentifier):
    """Identifier for text selection menu."""

    type = "menu-text"


class LPMMenuIdentifier(BaseMenuIdentifier):
    """Identifier for text selection menu."""

    type = "menu-lpm"


supported_identifiers = [
    TextBlockIdentifier,
    TextMenuIdentifier,
    LPMMenuIdentifier,
]


def make_identifier(string):
    for cls in supported_identifiers:
        try:
            return cls.from_string(string)
        except BadTextIdentifierError:
            pass
    raise BadTextIdentifierError(f"{string} is not a valid pylm identifier")

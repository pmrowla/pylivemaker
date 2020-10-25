# -*- coding: utf-8
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
"""LiveMaker preview menu file (LPM) module."""

from io import IOBase

import construct

from .exceptions import LiveMakerException


DEFAULT_LPM_VERSION = 106


class BadLPMError(LiveMakerException):
    pass


class _LPMVersionAdapter(construct.Adapter):
    def _decode(self, obj, ctx, path):
        return int(obj)

    def _encode(self, obj, ctx, path):
        return f"{obj:03}".encode("ascii")


class LPMVersionValidator(construct.Validator):
    def _validate(self, obj, ctx, path):
        return obj >= 100

    def _decode(self, obj, ctx, path):
        if not self._validate(obj, ctx, path):
            raise construct.ValidationError(f"Unsupported LPM version: {obj}")
        return obj


class LMLivePrevMenu:
    """Class for handling preview menu files.

    RE'd from TLivePrevMenu, TLivePrevImages classes in LiveMaker code.

    """

    def __init__(self, version=DEFAULT_LPM_VERSION, unk1=0, buttons=[], **kwargs):
        self.version = version
        self.unk1 = unk1
        self.buttons = buttons

    def __iter__(self):
        return iter(self.items())

    def __getitem__(self, key):
        if key in self.keys():
            return getattr(self, key)
        raise KeyError

    def keys(self):
        return [
            "version",
            "project_name",
            "unk1",
            "buttons",
        ]

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    @classmethod
    def _struct(cls):
        return construct.Struct(
            "signature" / construct.Const(b"LivePrevMenu"),
            "version" / LPMVersionValidator(_LPMVersionAdapter(construct.Bytes(3))),
            "unk1" / construct.Bytes(8),
            "buttons"
            / construct.PrefixedArray(
                construct.Int32ul,
                construct.Struct(
                    "width" / construct.Int32ul,
                    "height" / construct.Int32ul,
                    "src" / construct.PascalString(construct.Int32ul, "cp932"),
                    "unk2" / construct.Byte,
                    "name" / construct.PascalString(construct.Int32ul, "cp932"),
                    "src_selected" / construct.PascalString(construct.Int32ul, "cp932"),
                    "unk3" / construct.PascalString(construct.Int32ul, "cp932"),
                    "unk4" / construct.PascalString(construct.Int32ul, "cp932"),
                    "unk5"
                    / construct.If(
                        construct.this._._.version > 100,
                        construct.PascalString(construct.Int32ul, "cp932"),
                    ),
                    "unk6"
                    / construct.If(
                        construct.this._._.version > 102,
                        construct.Struct(
                            construct.PascalString(construct.Int32ul, "cp932"),
                            construct.PascalString(construct.Int32ul, "cp932"),
                        ),
                    ),
                    "unk7" / construct.PascalString(construct.Int32ul, "cp932"),
                    "unk8" / construct.PascalString(construct.Int32ul, "cp932"),
                    "unk9" / construct.PascalString(construct.Int32ul, "cp932"),
                    "unk10"
                    / construct.If(
                        construct.this._._.version > 101,
                        construct.Struct(
                            construct.PascalString(construct.Int32ul, "cp932"),
                            construct.PascalString(construct.Int32ul, "cp932"),
                        ),
                    ),
                    "unk15" / construct.Int32ul,
                    "unk16" / construct.Int32ul,
                    "unk17" / construct.PascalString(construct.Int32ul, "cp932"),
                    "unk18"
                    / construct.If(
                        construct.this._._.version > 103,
                        construct.Struct(
                            construct.PascalString(construct.Int32ul, "cp932"),
                            construct.PascalString(construct.Int32ul, "cp932"),
                            construct.PascalString(construct.Int32ul, "cp932"),
                            construct.PascalString(construct.Int32ul, "cp932"),
                            construct.PascalString(construct.Int32ul, "cp932"),
                            construct.Int32ul,
                        ),
                    ),
                    "unk19"
                    / construct.If(
                        construct.this._._.version > 104,
                        construct.PascalString(construct.Int32ul, "cp932"),
                    ),
                    "unk20"
                    / construct.If(
                        construct.this._._.version > 105,
                        construct.PascalString(construct.Int32ul, "cp932"),
                    ),
                ),
            ),
        )

    @classmethod
    def from_struct(cls, struct, **kwargs):
        """Create an LMProject from the specified struct."""
        if isinstance(struct, construct.Container):
            d = {k: v for k, v in struct.items()}
            d.update(kwargs)
            return cls(**d)
        raise NotImplementedError

    @classmethod
    def from_file(cls, infile):
        """Parse the specified file into an LMLivePrevMenu.

        Args:
            infile: Input .lpm file. Can be string, path-like or file-like object.

        """
        if not isinstance(infile, IOBase):
            infile = open(infile, "rb")
        try:
            return cls.from_struct(cls._struct().parse_stream(infile))
        except construct.ConstructError as e:
            raise BadLPMError(e)

    def to_lpm(self):
        """Compile settings into binary .lpm format."""
        try:
            return self._struct().build(self)
        except construct.ConstructError as e:
            raise BadLPMError(e)

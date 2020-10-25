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
"""LiveMaker project settings file (LPB) module."""

from io import IOBase

import construct
import numpy

from .exceptions import BadLpbError
from .lsb.core import ParamType
from .lsb.lmscript import DEFAULT_LSB_VERSION, LsbVersionValidator, lsb_to_lm_ver


class LMProject:
    """Class for handling project settings files.

    RE'd from TProject, TProjectSettings classes in LiveMaker code.

    """

    def __init__(
        self,
        version=DEFAULT_LSB_VERSION,
        project_name="",
        unk1=0,
        unk2=0,
        init_lsb="",
        exit_lsb="",
        project_dir="",
        unk3=0,
        bool1=0,
        bool2=0,
        audio_formats=".wav.wma.ogg.mid.mp3",
        bool3=0,
        bool4=0,
        bool5=1,
        insert_disk_prompt="",
        exit_prompt="",
        system_settings=[],
        **kwargs,
    ):
        self.version = version
        self.project_name = project_name
        self.unk1 = unk1
        self.unk2 = unk2
        self.init_lsb = init_lsb
        self.exit_lsb = exit_lsb
        self.project_dir = project_dir
        self.unk3 = unk3
        self.bool1 = bool1
        self.bool2 = bool2
        self.audio_formats = audio_formats
        self.bool3 = bool3
        self.bool4 = bool4
        self.bool5 = bool5
        self.insert_disk_prompt = insert_disk_prompt
        self.exit_prompt = exit_prompt
        if isinstance(system_settings, construct.ListContainer):
            settings = []
            for setting in system_settings:
                settings.append({"name": setting.name, "type": str(setting.type), "value": setting.value})
            self.system_settings = settings
        else:
            self.system_settings = system_settings

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
            "unk2",
            "init_lsb",
            "exit_lsb",
            "project_dir",
            "unk3",
            "bool1",
            "bool2",
            "audio_formats",
            "bool3",
            "bool4",
            "bool5",
            "insert_disk_prompt",
            "exit_prompt",
            "system_settings",
        ]

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    @property
    def lm_version(self):
        return lsb_to_lm_ver(self.version)

    @classmethod
    def _struct(cls):
        return construct.Struct(
            "version" / LsbVersionValidator(construct.Int32ul),
            "project_name" / construct.PascalString(construct.Int32ul, "cp932"),
            "unk1" / construct.Int64ul,
            "unk2" / construct.Int64ul,
            "init_lsb" / construct.PascalString(construct.Int32ul, "cp932"),
            "exit_lsb"
            / construct.If(
                construct.this.version > 0x6D,
                construct.PascalString(construct.Int32ul, "cp932"),
            ),
            "project_dir" / construct.PascalString(construct.Int32ul, "cp932"),
            "unk3" / construct.Int32ul,
            "bool1" / construct.Byte,
            "bool2"
            / construct.If(
                construct.this.version >= 0x6A,
                construct.Byte,
            ),
            "audio_formats"
            / construct.If(
                construct.this.version >= 0x6D,
                construct.PascalString(construct.Int32ul, "cp932"),
            ),
            "bool3"
            / construct.If(
                construct.this.version >= 0x71,
                construct.Byte,
            ),
            "bool4"
            / construct.If(
                construct.this.version >= 0x72,
                construct.Byte,
            ),
            "bool5"
            / construct.If(
                construct.this.version >= 0x74,
                construct.Byte,
            ),
            "insert_disk_prompt" / construct.PascalString(construct.Int32ul, "cp932"),
            "exit_prompt" / construct.PascalString(construct.Int32ul, "cp932"),
            "system_settings"
            / construct.PrefixedArray(
                construct.Int32ul,
                construct.Struct(
                    "type" / construct.Enum(construct.Byte, ParamType),
                    "name" / construct.PascalString(construct.Int32ul, "cp932"),
                    "value"
                    / construct.Switch(
                        construct.this.type,
                        {
                            "Int": construct.Int32sl,
                            "Float": construct.ExprAdapter(
                                construct.Bytes(10),
                                lambda obj, ctx: numpy.frombuffer(obj.rjust(16, b"\x00"), dtype=numpy.longdouble),
                                lambda obj, ctx: numpy.longdouble(obj).tobytes()[-10:],
                            ),
                            "Flag": construct.Byte,
                            "Str": construct.PascalString(construct.Int32ul, "cp932"),
                        },
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
        """Parse the specified file into an LMProject.

        Args:
            infile: Input .lpb file. Can be string, path-like or file-like object.

        """
        if not isinstance(infile, IOBase):
            infile = open(infile, "rb")
        try:
            return cls.from_struct(cls._struct().parse_stream(infile))
        except construct.ConstructError as e:
            raise BadLpbError(e)

    def to_lpb(self):
        """Compile settings into binary .lpb format."""
        try:
            return self._struct().build(self)
        except construct.ConstructError as e:
            raise BadLpbError(e)

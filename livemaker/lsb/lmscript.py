# -*- coding: utf-8
#
# Copyright (C) 2019 Peter Rowlands <peter@pmrowla.com>
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
"""LiveMaker LSB/LSC script classes.

Attributes:
    MIN_LSB_VERSION (int): Minimum supported compiled LSB version.
    DEFAULT_LSB_VERSION (int): Default compiled LSB version.
    MAX_LSB_VERSION (int): Maximum supported compiled LSB version.

"""

import logging
import math
from io import IOBase

import construct

from lxml import etree

from .core import BaseSerializable
from .command import CommandType, PropertyType, _command_classes, _command_structs
from ..exceptions import BadLsbError


log = logging.getLogger(__name__)


# Known LSB format versions
MIN_LSB_VERSION = 103
DEFAULT_LSB_VERSION = 117
MAX_LSB_VERSION = 117


class _LsbVersionValidator(construct.Validator):
    """Construct validator for supported compiled LSB versions."""

    def _validate(self, obj, ctx, path):
        return obj >= MIN_LSB_VERSION and obj <= MAX_LSB_VERSION

    def _decode(self, obj, ctx, path):
        if not self._validate(obj, ctx, path):
            raise construct.ValidationError('Unsupported LSB version: {}'.format(obj))
        return obj


class _ParamStreamAdapter(construct.Adapter):
    """Construct adapter for converting command parameter bitstream into a list of bools."""

    def _decode(self, obj, ctx, path):
        bools = []
        for x in obj:
            for shift in range(0, 8):
                bools.append(x & (1 << shift) != 0)
        return bools

    def _encode(self, obj, ctx, path):
        stream = []
        for i in range(0, len(obj), 8):
            flags = obj[i:i + 8]
            if len(flags) < 8:
                flags.extend([False] * (8 - len(flags)))
            byte = 0
            for j, flag in enumerate(flags):
                byte |= (flag << j)
            stream.append(byte.to_bytes(1, byteorder='little'))
        return b''.join(stream)


class LMScript(BaseSerializable):
    """LiveMaker script class.

    A LiveMaker script is a collection of LiveMaker novel commands.
    One LiveMaker/LiveNovel "Chart" will be serialized as one script
    file.

    Args:
        version (int): Version number. If `version` is not in the range [`MIN_LSB_VERSION`, `MAX_LSB_VERSION`],
            this LMScript cannot be compiled into a binary LSB.
        param_type: Unknown type flag (always 1?).
        flags (int): Unknown (always 0?).
        call_name (str): String name for calling this script (only used for documentation).
        novel_params (iterable): Iterable containing string descriptions for parameters that
            this script accepts (only used for documentation).
        command_params (iterable(iterable(bool))): Two dimensional array of booleans specifying the command
            parameters are for Component type commands.
            (i.e. `command_params[CommandType.BoxNew][PropertyType.PR_NAME] == True`
            means that `BoxNew` takes a `PR_NAME` parameter.)
        commands (iterable): Iterable containing this script's `Command` objects.

    Raises:
        BadLsbError: If the specified LMScript would be invalid or unsupported.

    """

    # internal use field to specify where this LMScript came from
    _parsed_from = None

    def __init__(self, version=DEFAULT_LSB_VERSION, param_type=1, flags=0,
                 call_name='', novel_params=[], command_params=[[]], commands=[], **kwargs):
        if version < MIN_LSB_VERSION or version > MAX_LSB_VERSION:
            log.warn('LSB compilation unsupported for LMScript version {}'.format(version))
        self.version = version
        self.param_type = param_type
        self.flags = flags
        self.call_name = call_name
        self.novel_params = novel_params
        if len(command_params) > (max(CommandType) + 1):
            log.warn('len(command_params) exceeds max command type value')
        self.command_params = command_params
        if isinstance(commands, construct.ListContainer):
            self.commands = []
            for c in commands:
                cmd = _command_classes[CommandType(int(c.type))].from_struct(
                    c, command_params=command_params[int(c.type)])
                self.commands.append(cmd)
        else:
            self.commands = commands

    def __len__(self):
        return len(self.commands)

    def __repr__(self):
        return '<LMScript version={} commands={}>'.format(self.version, repr(self.commands))

    def __iter__(self):
        return iter(self.items())

    def __getitem__(self, key):
        if key in self.keys():
            return getattr(self, key)
        raise KeyError

    def keys(self):
        return ['version', 'flags', 'command_count', 'param_stream_size',
                'command_params', 'commands']

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    @property
    def command_count(self):
        """Return the number of command types supported by this script."""
        return len(self.command_params)

    @property
    def param_stream_size(self):
        """Return the length of this script's param flag bytestream."""
        return math.ceil(len(self.command_params[-1]) / 8)

    @property
    def lm_version(self):
        """Return LiveMaker app version based on an LSB version."""
        if self.version < MIN_LSB_VERSION:
            raise BadLsbError('Unknown LSB version: {}'.format(self.version))
        elif self.version < 117:
            return 2
        return 3

    def to_lsc(self):
        """Return this script in the tex .lsc format."""
        lines = [
            'LiveMaker{:03}'.format(self.version),
            str(self.param_type),
        ]
        if self.version >= 104:
            lines.append('')    # unk, call name?
        lines.append(str(len(self.command_params)))
        for params in self.command_params:
            lines.append('\t'.join([str(i) for i, flag in enumerate(params) if flag]))

        return '\r\n'.join(lines)

    @classmethod
    def from_lsc(cls, s):
        """Create an LMScript from the specified string.

        Args:
            s: String containing text .lsc format data.

        Raises:
            BadLsbError if the string could not be parsed.

        Note:
            Currently only supports reading version information.

        """
        if not s.startswith('LiveMaker'):
            raise BadLsbError('String does not contain LiveMaker script data.')
        lines = s.splitlines()
        try:
            if lines[0].startswith('LiveMakerB'):
                version = int(lines[0][10:])
            else:
                version = int(lines[0][9:])
            # param_type = int(lines[1])
            # if version >= 104:
            #     flags = int(lines[3])
            #     command_params_count = int(lines[4])
            #     command_params_start = 5
            # else:
            #     flags = int(lines[2])
            #     command_params_count = int(lines[3])
            #     command_params_start = 4
            # command_params = []
            # for line in lines[command_params_start:command_params_start + command_params_count]:
            #     params = [False] * (max(PropertyType) + 1)
            #     for index in line.split():
            #         params[int(index)] = True
            #     command_params.append(params)
            # commands = []
            # for command in lines[command_params_start + command_params_count:]:
            #     pass
        except (IndexError, ValueError):
            raise BadLsbError('String does not contain LiveMaker script data.')
        # lm = cls(version=version, param_type=param_type, flags=flags,
        #          command_params=command_params, commands=commands)
        lm = cls(version=version)
        lm._parsed_from = 'lsc'

    @classmethod
    def _struct(cls):
        return construct.Struct(
            'version' / _LsbVersionValidator(construct.Int32ul),
            'flags' / construct.Byte,
            'command_count' / construct.Int32ul,
            'param_stream_size' / construct.Int32ul,
            'command_params' / construct.Array(
                construct.this.command_count,
                _ParamStreamAdapter(construct.Bytes(construct.this.param_stream_size)),
            ),
            'commands' / construct.PrefixedArray(
                construct.Int32ul,
                construct.Select(*_command_structs)
            ),
        )

    @classmethod
    def from_struct(cls, struct):
        """Create an LMScript from the specified struct."""
        lm = LMScript(
            version=struct.version,
            flags=struct.flags,
            command_params=struct.command_params,
            commands=struct.commands,
        )
        lm._parsed_from = 'lsb'
        return lm

    def to_lsb(self):
        """Compile this script into binary .lsb format."""
        try:
            return self._struct().build(self)
            # return construct.Debugger(self._struct()).build(self)
        except construct.ConstructError as e:
            raise BadLsbError(e)

    def to_xml(self):
        """Return this script as an .lsc format XML etree.Element."""
        root = etree.Element('Page')
        version = etree.SubElement(root, 'Version')
        version.text = str(self.version)
        call_name = etree.SubElement(root, 'CallName')
        call_name.text = self.call_name
        novel_param = etree.SubElement(root, 'NovelParam')
        for x in self.novel_params:
            item = etree.SubElement(novel_param, 'Item')
            item .text = x
        param = etree.SubElement(root, 'Param')
        for i, params in enumerate(self.command_params):
            cmd = etree.SubElement(param, CommandType(i).name)
            for j, flag in enumerate(params):
                if flag:
                    item = etree.SubElement(cmd, PropertyType(j).name)
                    item.text = "1"
        command = etree.SubElement(root, 'Command')
        for c in self.commands:
            command.append(c.to_xml())
        return root

    @classmethod
    def from_xml(cls, root):
        """Create an LMScript from the specified XML element.

        Args:
            root: The root tree element.

        Raises:
            BadLsbError: If the XML tree could not be parsed.

        Note:
            Currently only supports reading header information.

        """
        version = 0
        # param_type = 0
        # flags = 0
        # call_name = ''
        # novel_params = []
        # command_params = []
        # for i in range(max(CommandType) + 1):
        #     command_params.append([False] * (max(PropertyType) + 1))
        # commands = []
        if root.tag != 'Page':
            raise BadLsbError('Expected an LMScript XML tree')
        for child in root:
            if child.tag == 'Version':
                version = int(child.text)
            # elif child.tag == 'PropertyType':
            #     param_type = int(child.text)
            # elif child.tag == 'CallName':
            #     call_name = child.text
            # elif child.tag == 'NovelParam':
            #     for item in child:
            #         novel_params.append(item.text())
            # elif child.tag == 'Param':
            #     for cmd in child:
            #         cmd_type = CommandType[cmd.tag]
            #         for param in cmd:
            #             param_type = PropertyType[param.tag]
            #             if int(param.text):
            #                 command_params[cmd_type][param_type] = True
            # if child.tag == 'Command':
            #     pass
        # lm = cls(version=version, param_type=param_type, flags=flags, call_name=call_name,
        #          novel_params=novel_params, command_params=command_params, commands=commands)
        lm = cls(version=version)
        lm._parsed_from = 'lsc-xml'
        return lm

    @classmethod
    def from_file(cls, infile):
        """Parse the specified file into an LMScript.

        Args:
            infile: Input .lsc or .lsb file. Can be a string, path-like, or file-like object.

        Raises:
            BadLsbError: If the input file could not be parsed.

        """
        if not isinstance(infile, IOBase):
            infile = open(infile, 'rb')
        data = infile.read(9)
        infile.seek(0)
        if data.startswith(b'LiveMaker'):
            return cls.from_lsc(infile.read().decode('cp932'))
        elif data.startswith(b'<?xml'):
            return cls.from_xml(etree.parse(infile))
        try:
            return cls.from_struct(cls._struct().parse_stream(infile))
        except construct.ConstructError as e:
            raise BadLsbError(e)

    @classmethod
    def from_lsb(cls, data):
        """Parse the specified compiled .lsb data into an LMScript.

        Args:
            data: Input .lsb data.

        Raises:
            BadLsbError: If the input data could not be parsed.

        """
        try:
            return cls.from_struct(cls._struct().parse(data))
        except construct.ConstructError as e:
            raise BadLsbError(e)

    def text_scenarios(self):
        """Return a list of LiveNovel text scenarios contained in this script.

        Returns:
            tuple(int, str, :class:`TpWord`): (line_num, name, scenario)

        """
        scenarios = []
        for i, cmd in enumerate(self.commands):
            if cmd.type == CommandType.TextIns:
                # TextIns command should always occur in sequence:
                #   Label <scenario_name>
                #   Calc <set system message flag to non-empty>
                #   TextIns <scenario>
                name = self.commands[i - 2].get('Name', '')
                scenario = cmd.get('Text')
                scenarios.append((cmd.LineNo, name, scenario))
        return scenarios

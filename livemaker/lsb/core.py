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
"""Core lmscript classes."""

import enum
from abc import ABC, abstractmethod

import construct
import numpy
from loguru import logger
from lxml import etree


class BaseSerializable(ABC):
    """Base class for serializable LiveMaker objects.

    Note:
        LiveMaker uses 3 different script serialization formats:

            - LSC (old text .lsc)
            - XML (new XML .lsc)
            - LSB (compiled binary .lsb)

        In pylivemaker, we currently only support serializing to and from
        the binary LSB format. Subclasses of `BaseSerializable` do support
        serialization to pseudo-LSC and pseudo-XML formats so that a script
        can be examined for patching purposes, however, these exported formats
        cannot currently be re-read as input by pylivemaker.

        This means that pylivemaker cannot be used to compile .lsc files from
        a LiveMaker/LiveNovel template or project directory.

    """

    def __init__(*args, **kwargs):
        pass

    # __iter__ and/or __getitem__ need to be implemented in subclasses for
    # construct to be able to build an object.

    def __iter__(self):
        raise NotImplementedError

    def __getitem__(self, key):
        raise NotImplementedError

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    @abstractmethod
    def to_lsc(self):
        """Serialize this object as pseudo-LSC data."""
        pass

    @classmethod
    def from_lsc(cls, data):
        """Parse text .lsc data into an object."""
        raise NotImplementedError

    @abstractmethod
    def to_xml(self):
        """Serialize an object as pseudo-LSC XML."""
        pass

    @classmethod
    def from_xml(cls, root):
        """Parse XML into an object."""
        raise NotImplementedError

    @classmethod
    def _struct(cls):
        """Return a construct Struct for this class."""
        return construct.Struct()

    @classmethod
    def from_struct(cls, struct, **kwargs):
        """Instantiate an object from a construct Struct."""
        if isinstance(struct, construct.Container):
            d = {k: v for k, v in struct.items()}
            d.update(kwargs)
            return cls(**d)
        raise NotImplementedError


class ParamType(enum.IntEnum):
    """:class:`Param` data type."""

    Var = 0x00
    """Variable name.

    Internally, LiveMaker stores TParamVar as a Delphi Variant type which in theory supports
    any possible Delphi type, but LiveMaker only uses it as a variable length string.
    """

    Int = 0x01
    """Integer."""

    Float = 0x02
    """Floating point value.

    LiveMaker TParamFloats are IEEE 80-bit precision floats, in pylivemaker we handle them
    as numpy `longdouble`.
    According to numpy docs, ``np.longdouble` is either `float96` or ``float128`` depending on platform,
    and in both cases they are actually ``float80`` padded with zeroes to 96 or 128 bits.
    """

    Flag = 0x03
    """1-byte Enum/Flag type."""

    Str = 0x04
    """CP932 encoded string.

    Internally, pylivemaker handles all strings as Python unicode strings.
    """


class OpeDataType(enum.IntEnum):
    """:class:`OpeData` operator type.

    Operator type determines how an expression will be evaluated.

    """

    None_ = 0x00

    To = 0x01
    """Operator ``=`` (assignment)."""

    Plus = 0x02
    """Operator ``+``.

    Note:
        In LiveMaker, + can be used for both addition and string concatenation, depending
        on the data type of the result variable. If the result variable is a numeric type
        and one of the arguments is a string, the string will be coerced to number
        (i.e. for ``x = 1 + "2"`` and ``x`` is an ``Int``, the final value of ``x`` will be ``3``).
    """

    Minus = 0x03
    """Operator ``-``."""

    Mul = 0x04
    """Operator ``*``."""

    Div = 0x05
    """Operator ``/``."""

    Mod = 0x06
    """Operator ``%``."""

    Or = 0x07
    """Operator ``|``.

    Note:
        In LiveMaker, ``|`` is used for both bitwise OR and logical OR, depending
        on the data type of the operands.

    """

    And = 0x08
    """Operator ``&``.

    Note:
        In LiveMaker, ``&`` is used for both bitwise AND and logical AND, depending
        on the data type of the operands.

    """

    Xor = 0x09
    """Operator ``^`` (bitwise XOR)."""

    DimTo = 0x0A
    """Operator ``[]`` (array access)."""

    Func = 0x0B
    """Operator ``()`` (function call).

    Available functions are listed in :class:`OpeFuncType`.

    """

    Equal = 0x0C
    """Operator ``==`` (equals)."""

    Big = 0x0D
    """Operator ``>`` (greater than)."""

    Small = 0x0E
    """Operator ``<`` (less than)."""

    EBig = 0x0F
    """Operator ``>=`` (greater than or equals)."""

    ESmall = 0x10
    """Operator ``<=`` (less than or equals)."""

    ShiftL = 0x11
    """Operator ``<<`` (bitwise shift left)."""

    ShiftR = 0x12
    """Operator ``>>`` (bitwise shift right)."""

    ComboStr = 0x13
    """Operator ``++`` (string concatenation)."""

    NEqual = 0x14
    """Operator ``!=`` (not equals)."""


class OpeFuncType(enum.IntEnum):
    """Function type.

    See LiveNovel docs for details on each available function.

    """

    IntToStr = 0x00
    IntToHex = 0x01
    GetProp = 0x02
    SetProp = 0x03
    GetArraySize = 0x04
    Length = 0x05
    JLength = 0x06
    Copy = 0x07
    JCopy = 0x08
    Delete = 0x09
    JDelete = 0x0A
    Insert = 0x0B
    JInsert = 0x0C
    CompareStr = 0x0D
    CompareText = 0x0E
    Pos = 0x0F
    JPos = 0x10
    Trim = 0x11
    JTrim = 0x12
    Exists = 0x13
    Not = 0x14
    SetArray = 0x15
    FillMem = 0x16
    CopyMem = 0x17
    GetCheck = 0x18
    SetCheck = 0x19
    Random = 0x1A
    GetSaveCaption = 0x1B
    ArrayToString = 0x1C
    StringToArray = 0x1D
    IndexOfStr = 0x1E
    SortStr = 0x1F
    ListCompo = 0x20
    ToClientX = 0x21
    ToClientY = 0x22
    ToScreenX = 0x23
    ToScreenY = 0x24
    Int = 0x25
    Float = 0x26
    Sin = 0x27
    Cos = 0x28
    Tan = 0x29
    ArcSin = 0x2A
    ArcCos = 0x2B
    ArcTan = 0x2C
    ArcTan2 = 0x2D
    Hypot = 0x2E
    IndexOfMenu = 0x2F
    Abs = 0x30
    Fabs = 0x31
    VarExists = 0x32
    EncodeDate = 0x33
    EncodeTime = 0x34
    DecodeDate = 0x35
    DecodeTime = 0x36
    GetYear = 0x37
    GetMonth = 0x38
    GetDay = 0x39
    GetHour = 0x3A
    GetMin = 0x3B
    GetSec = 0x3C
    GetWeek = 0x3D
    GetWeekStr = 0x3E
    GetWeekJStr = 0x3F
    FixStr = 0x40
    GetDisplayMode = 0x41
    AddArray = 0x42
    InsertArray = 0x43
    DeleteArray = 0x44
    InPrimary = 0x45
    CopyArray = 0x46
    FileExists = 0x47
    LoadTextFile = 0x48
    LowerCase = 0x49
    UpperCase = 0x4A
    ExtractFilePath = 0x4B
    ExtractFileName = 0x4C
    ExtractFileExt = 0x4D
    IsPathDelimiter = 0x4E
    AddBackSlash = 0x4F
    ChangeFileExt = 0x50
    IsDelimiter = 0x51
    StringOfChar = 0x52
    StringReplace = 0x53
    AssignTemp = 0x54
    HanToZen = 0x55
    ZenToHan = 0x56
    DBCreateTable = 0x57
    DBSetActive = 0x58
    DBAddField = 0x59
    DBSetRecNo = 0x5A
    DBInsert = 0x5B
    DBDelete = 0x5C
    DBGetInt = 0x5D
    DBSetInt = 0x5E
    DBGetFloat = 0x5F
    DBSetFloat = 0x60
    DBGetBool = 0x61
    DBSetBool = 0x62
    DBGetStr = 0x63
    DBSetStr = 0x64
    DBRecordCount = 0x65
    DBFindFirst = 0x66
    DBFindLast = 0x67
    DBFindNext = 0x68
    DBFindPrior = 0x69
    DBLocate = 0x6A
    DBLoadTsvFile = 0x6B
    DBDirectGetInt = 0x6C
    DBDirectSetInt = 0x6D
    DBDirectGetFloat = 0x6E
    DBDirectSetFloat = 0x6F
    DBDirectGetBool = 0x70
    DBDirectSetBool = 0x71
    DBDirectGetStr = 0x72
    DBDirectSetStr = 0x73
    DBCopyTable = 0x74
    DBDeleteTable = 0x75
    DBInsertTable = 0x76
    DBCopy = 0x77
    DBClearTable = 0x78
    DBSort = 0x79
    DBGetActive = 0x7A
    DBGetRecNo = 0x7B
    DBClearRecord = 0x7C
    SetWallPaper = 0x7D
    Min = 0x7E
    Max = 0x7F
    Fmin = 0x80
    Fmax = 0x81
    GetVarType = 0x82
    GetEnabled = 0x83
    SetEnabled = 0x84
    AddDelimiter = 0x85
    ListSaveCaption = 0x86
    OpenUrl = 0x87
    Calc = 0x88
    SaveScreen = 0x89
    StrToIntDef = 0x8A
    StrToFloatDef = 0x8B
    GetVisible = 0x8C
    SetVisible = 0x8D
    GetHistoryCount = 0x8E
    GetHistoryMaxCount = 0x8F
    SetHistoryMaxCount = 0x90
    GetGroupIndex = 0x91
    GetSelected = 0x92
    SetSelected = 0x93
    SelectOpenFile = 0x94
    SelectSaveFile = 0x95
    SelectDirectory = 0x96
    ExtractFile = 0x97
    Chr = 0x98
    Ord = 0x99
    InCabinet = 0x9A
    PushVar = 0x9B
    PopVar = 0x9C
    DeleteStack = 0x9D
    CopyFile = 0x9E
    DBGetTableCount = 0x9F
    DBGetTable = 0xA0
    CreateObject = 0xA1
    DeleteObject = 0xA2
    GetItem = 0xA3
    UniqueArray = 0xA4
    TrimArray = 0xA5
    GetImeOpened = 0xA6
    SetImeOpened = 0xA7
    Alert = 0xA8
    GetCinemaProp = 0xA9
    SetCinemaProp = 0xAA


class Param(BaseSerializable):
    """Expression parameter (operand).

    Internally, LiveMaker subclasses each possible TParam type,
    but in pylivemaker we handle them all here.

    Args:
        value: The value for this parameter.
        type (:class:`ParamType`): The data type for this parameter.
            If type is not specified, it will be guessed based on value.

    Note:
        If `value` is a variable name, ``Var`` type must be explicity specified,
        otherwise it will incorrectly be guessed to be ``Str``.

        If `value` is an integer flag, ``Flag`` type must be explicitly specified,
        otherwise it will be incorrectly guessed to be ``Int``.

    """

    def __init__(self, value=None, type=None, **kwargs):
        self.value = value
        if type is None:
            if isinstance(value, int):
                self.type = ParamType.Int
            elif isinstance(value, (float, numpy.longdouble)):
                self.type = ParamType.Float
                self.value = numpy.longdouble(value)
            elif isinstance(value, bool):
                self.type = ParamType.Flag
            elif isinstance(value, str):
                self.type = ParamType.Str
            else:
                raise ValueError("Could not guess datatype for {}".format(value))
        else:
            self.type = ParamType(int(type))

    def __str__(self):
        return str(self.value)

    def __iter__(self):
        return iter(self.items())

    def __getitem__(self, key):
        if key == "type":
            return self.type.name
        elif key == "value":
            return self.value
        raise KeyError

    def keys(self):
        return ["type", "value"]

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    def to_lsc(self):
        if self.type == ParamType.Str:
            return '"{}"'.format(self.value)
        return str(self)

    def to_xml(self):
        xml = self.to_lsc()
        if self.type == ParamType.Var and "\x01" in xml:
            logger.warning('Replacing invalid xml char "\\x01" in varname {}'.format(self.value))
            xml = xml.replace("\x01", "*")
        return xml

    @classmethod
    def _struct(cls):
        return construct.Struct(
            "type" / construct.Enum(construct.Byte, ParamType),
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
                # else 'Var' variable name type
                construct.Select(
                    construct.PascalString(construct.Int32ul, "cp932"),
                ),
            ),
        )


class OpeData(BaseSerializable):
    """Expression operator class.

    Internal LiveMaker TOpeData class.

    Args:
        type (:class:`OpeDataType`): Operator type for this expression.
        name (str): The name of result variable for this expression.
        func (:class:`OpeFuncType`): Function for this expression (only applicable if
            `type` is `OpeDataType.Func`.
        operands (list(:class:`Param`)): The operands for this expression.

    """

    def __init__(self, type=OpeDataType.None_, name="", func=None, operands=[], **kwargs):
        self.type = OpeDataType(int(type))
        self.name = name
        if self.type == OpeDataType.Func:
            self.func = OpeFuncType(int(func))
        else:
            self.func = None
        if isinstance(operands, construct.ListContainer):
            operands = [Param.from_struct(x) for x in operands]
        self.operands = operands

    def __str__(self):
        out = []
        for token in self.tokenize():
            if isinstance(token, Param):
                out.append(token.to_lsc())
            else:
                out.append(str(token))
        return "".join(out)

    def __iter__(self):
        return iter(self.items())

    def __len__(self):
        return len(self.operands)

    def __getitem__(self, key):
        if key in self.keys():
            v = getattr(self, key)
            if isinstance(v, enum.Enum):
                v = v.name
            return v
        raise KeyError

    def keys(self):
        return ["type", "name", "count", "func", "operands"]

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    @property
    def count(self):
        """Return the number of operands in this expression."""
        return len(self.operands)

    def to_lsc(self):
        return str(self)

    def to_xml(self):
        out = []
        for token in self.tokenize():
            if isinstance(token, Param):
                out.append(token.to_xml())
            else:
                out.append(str(token))
        return "".join(out)

    @classmethod
    def _struct(cls):
        return construct.Struct(
            "type" / construct.Enum(construct.Byte, OpeDataType),
            "name" / construct.PascalString(construct.Int32ul, "cp932"),
            "count" / construct.Int32ul,
            "func" / construct.Switch(construct.this.type, {"Func": construct.Enum(construct.Byte, OpeFuncType)}),
            "operands" / construct.Array(construct.this.count, Param._struct()),
        )

    def _to(self):
        return [self.operands[-1]]

    # TODO: LiveMaker allows for doing math operators on strings via type
    # conversion - the docs say "50" + 100 should result in either 150 or "150"
    # depending on the result var's datatype.
    #
    # For our purposes don't worry about dealing with type coercion unless
    # someone finds a script that actually requires supporting it

    def _plus(self):
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return [p1, " + ", p2]
        elif p1.type == ParamType.Str or p2.type == ParamType.Str:
            raise NotImplementedError("Plus() expected numeric type")
        return [Param(value=p1.value + p2.value)]

    def _minus(self):
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return [p1, " - ", p2]
        elif p1.type == ParamType.Str or p2.type == ParamType.Str:
            raise NotImplementedError("Minus() expected numeric type")
        return [Param(value=p1.value - p2.value)]

    def _mul(self):
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return [p1, " * ", p2]
        elif p1.type == ParamType.Str or p2.type == ParamType.Str:
            raise NotImplementedError("Mul() expected numeric type")
        return [Param(value=p1.value * p2.value)]

    def _div(self):
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return [p1, " / ", p2]
        elif p1.type == ParamType.Str or p2.type == ParamType.Str:
            raise NotImplementedError("Div() expected numeric type")
        return [Param(value=p1.value / p2.value)]

    def _mod(self):
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return [p1, " % ", p2]
        elif p1.type == ParamType.Str or p2.type == ParamType.Str:
            raise NotImplementedError("Mod() expected numeric type")
        return [Param(value=p1.value % p2.value)]

    def _or(self):
        # LiveMaker uses | to specify both bitwise and boolean OR
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return ["(", p1, " | ", p2, ")"]
        elif p1.type == ParamType.Str or p2.type == ParamType.Str:
            raise NotImplementedError("Or() expected numeric type")
        if p1.type == ParamType.Flag and p2.type == ParamType.Flag:
            return [Param(value=p1.value or p2.value)]
        return [Param(value=p1.value | p2.value)]

    def _and(self):
        # LiveMaker uses | to specify both bitwise and boolean AND
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return ["(", p1, " & ", p2, ")"]
        elif p1.type == ParamType.Str or p2.type == ParamType.Str:
            raise NotImplementedError("And() expected numeric type")
        if p1.type == ParamType.Flag and p2.type == ParamType.Flag:
            return [Param(value=p1.value and p2.value)]
        return [p1.value & p2.value]

    def _xor(self):
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return [p1, " ^ ", p2]
        elif p1.type == ParamType.Str or p2.type == ParamType.Str:
            raise NotImplementedError("Xor() expected numeric type")
        return [Param(p1.value ^ p2.value)]

    def _dimto(self):
        # Array access
        x = [self.operands[0]]
        for p in self.operands[1:]:
            x.extend(["[", p, "]"])
        return x

    def _func(self):
        x = ["{}(".format(self.func.name)]
        for i, p in enumerate(self.operands):
            x.append(p)
            if i != len(self.operands) - 1:
                x.append(", ")
        x.append(")")
        return x

    def _equal(self):
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return [p1, " == ", p2]
        return [Param(value=p1.value == p2.value)]

    def _big(self):
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return [p1, " > ", p2]
        return [Param(value=p1.value > p2.value)]

    def _small(self):
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return [p1, " < ", p2]
        return [Param(value=p1.value < p2.value)]

    def _ebig(self):
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return [p1, " >= ", p2]
        return [Param(value=p1.value >= p2.value)]

    def _esmall(self):
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return [p1, " <= ", p2]
        return [Param(value=p1.value <= p2.value)]

    def _shiftl(self):
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return [p1, " << ", p2]
        elif p1.type == ParamType.Str or p2.type == ParamType.Str:
            raise NotImplementedError("ShiftL() expected numeric type")
        return [Param(p1.value << p2.value)]

    def _shiftr(self):
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return [p1, " >> ", p2]
        elif p1.type == ParamType.Str or p2.type == ParamType.Str:
            raise NotImplementedError("ShiftR() expected numeric type")
        return [Param(p1.value >> p2.value)]

    def _combostr(self):
        # String join
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return [p1, " ++ ", p2]
        elif p1.type != ParamType.Str or p2.type != ParamType.Str:
            raise NotImplementedError("ComboStr() expected string type")
        return [Param(value="".join([p1.value, p2.value]))]

    def _nequal(self):
        (p1, p2) = self.operands
        if p1.type == ParamType.Var or p2.type == ParamType.Var:
            return [p1, " != ", p2]
        return [Param(value=p1.value != p2.value)]

    def tokenize(self):
        """Return a tokenized version of this expression.

        Returns:
            list(str, :class:`Param`): List of tokens.

        Raises:
            NotImplementedError: If an operator does not support this combination of
                operands.

        """
        try:
            tokens = {
                OpeDataType.To: self._to,
                OpeDataType.Plus: self._plus,
                OpeDataType.Minus: self._minus,
                OpeDataType.Mul: self._mul,
                OpeDataType.Div: self._div,
                OpeDataType.Mod: self._mod,
                OpeDataType.Or: self._or,
                OpeDataType.And: self._and,
                OpeDataType.Xor: self._xor,
                OpeDataType.DimTo: self._dimto,
                OpeDataType.Func: self._func,
                OpeDataType.Equal: self._equal,
                OpeDataType.Big: self._big,
                OpeDataType.Small: self._small,
                OpeDataType.EBig: self._ebig,
                OpeDataType.ESmall: self._esmall,
                OpeDataType.ShiftL: self._shiftl,
                OpeDataType.ShiftR: self._shiftr,
                OpeDataType.ComboStr: self._combostr,
                OpeDataType.NEqual: self._nequal,
            }[self.type]()
            return tokens
        except KeyError:
            raise NotImplementedError("Cannot compute value for {} types.".format(self.type))


class LiveParser(BaseSerializable):
    """Parses a list of OpeData expressions into one result expression.

    Args:
        entries (list(:class:`OpeData`)): List of child expressions

    """

    def __init__(self, entries=[], **kwargs):
        if isinstance(entries, construct.ListContainer):
            entries = [OpeData.from_struct(x) for x in entries]
        self.entries = entries

    def __str__(self):
        return self._simplify()

    def __iter__(self):
        return iter(self.items())

    def __len__(self):
        return len(self.entries)

    def __getitem__(self, key):
        if key == "entries":
            return self.entries
        raise KeyError

    def keys(self):
        return ["entries"]

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    def to_lsc(self):
        return str(self)

    def to_xml(self):
        xml = self.to_lsc()
        if "\x01" in xml:
            logger.warning('Replacing invalid xml char "\\x01"')
            xml = xml.replace("\x01", "*")
        return xml

    @classmethod
    def _struct(cls):
        return construct.Struct(
            "entries" / construct.PrefixedArray(construct.Int32ul, OpeData._struct()),
        )

    #     @classmethod
    #     def from_struct(cls, struct):
    #         """Return a LiveParser for the specified struct."""
    #         return cls(entries=[OpeData.from_struct(x) for x in struct.entries])

    def _simplify(self):
        """Return a simplified expression for all expressions in this parser."""

        def _resolve(var, exprs):
            if var in exprs:
                operands = exprs[var]
                for i, op in enumerate(operands):
                    if isinstance(op, Param):
                        if op.type == ParamType.Var:
                            if op.value.startswith("____"):
                                # LiveParser parameter name
                                operands[i] = _resolve(op.value, exprs)
                            else:
                                operands[i] = op.value
                        elif op.type == ParamType.Str:
                            operands[i] = '"{}"'.format(op.value).replace("\n", "\\n").replace("\r", "\\r")
                        else:
                            operands[i] = op.value

            else:
                operands = [var]
            return "".join([str(x) for x in operands])

        exprs = {}
        for e in self.entries:
            exprs.update({e.name: e.tokenize()})
        if self.entries:
            e = self.entries[-1]
            if e.type == OpeDataType.To:
                if e.name == "____arg":
                    return _resolve("____arg", exprs)
                return "{} = {}".format(e.name, _resolve(e.name, exprs))
            else:
                logger.warning("Last entry in LiveParser was not a To statement: {}".format(self.entries[-1]))
        return ""


class LiveParserArray(BaseSerializable):
    """Internal use convenience class for handling arrays of :obj:`LiveParser` objects.

    Args:
        parsers (iterable): Iterable containing this array's parsers.
        name (str): Name for this field, used as XML tag name when serializing.

    """

    def __init__(self, parsers=[], prefixed=True):
        if isinstance(parsers, construct.ListContainer):
            parsers = [LiveParser.from_struct(x) for x in parsers]
        self.parsers = parsers
        self.prefixed = prefixed

    def __str__(self):
        return " ".join([str(x) for x in self.parsers])

    def __iter__(self):
        return iter(self.parsers)

    def __len__(self):
        return len(self.parsers)

    def to_lsc(self):
        """Return this command in text .lsc format."""
        out = []
        for parser in self.parsers:
            if parser:
                out.append(parser.to_lsc())
            else:
                out.append("")
        return "\t".join(out)

    # @classmethod
    # def from_lsc(cls, *args, **kwargs):
    #     parsers = []
    #     for arg in args:
    #         if arg:
    #             parsers.append(LiveParser.from_lsc(arg))
    #         else:
    #             parsers.append('')
    #     return cls(parsers)

    def to_xml(self):
        # NOTE: For whatever reason, LiveMaker uses a '\x02' separated list of
        # strings for variable width lists, and child <Item> tags for fixed
        # size lists.
        #
        # '\x02' is not a legal XMl character and lxml will not accept it, so
        # we just use \t.
        out = []
        if self.prefixed:
            for parser in self.parsers:
                if hasattr(parser, "to_xml"):
                    out.append(parser.to_xml())
                else:
                    out.append(str(parser))
            return "\t".join(out)
        for parser in self.parsers:
            item = etree.Element("Item")
            if hasattr(parser, "to_xml"):
                item.text = parser.to_xml()
            else:
                item.text = str(parser)
            out.append(item)
        return out

    # @classmethod
    # def from_xml(cls, root, **kwargs):
    #     parsers = []
    #     prefixed = True
    #     if len(root):
    #         prefixed = False
    #         for child in root:
    #             if child.tag == 'Item':
    #                 parsers.append(LiveParser.from_xml(child))
    #     else:
    #         for parser in root.text.split('\x02'):
    #             if parser:
    #                 parsers.append(LiveParser.from_xml(child))
    #             else:
    #                 parsers.append('')
    #     return LiveParserArray(parsers, prefixed=prefixed)

    @classmethod
    def _struct(cls, subcon, prefixed=True):
        """Return a construct Struct for this class.

        Args:
            subcon: Can be a subcon or fixed size, depending on value of `prefixed`.
            prefixed: True if this is a PrefixedArray.

        """
        if prefixed:
            return construct.PrefixedArray(subcon, LiveParser._struct())
        else:
            return construct.Array(subcon, LiveParser._struct())

    @classmethod
    def from_struct(cls, struct, prefixed=True):
        return cls(struct, prefixed=prefixed)


class PropertyType(enum.IntEnum):
    """LiveMaker object property constants."""

    PR_NONE = 0x00
    PR_NAME = 0x01
    PR_PARENT = 0x02
    PR_SOURCE = 0x03
    PR_LEFT = 0x04
    PR_TOP = 0x05
    PR_WIDTH = 0x06
    PR_HEIGHT = 0x07
    PR_ZOOMX = 0x08
    PR_COLOR = 0x09
    PR_BORDERWIDTH = 0x0A
    PR_BORDERCOLOR = 0x0B
    PR_ALPHA = 0x0C
    PR_PRIORITY = 0x0D
    PR_OFFSETX = 0x0E
    PR_OFFSETY = 0x0F
    PR_FONTNAME = 0x10
    PR_FONTHEIGHT = 0x11
    PR_FONTSTYLE = 0x12
    PR_LINESPACE = 0x13
    PR_FONTCOLOR = 0x14
    PR_FONTLINKCOLOR = 0x15
    PR_FONTBORDERCOLOR = 0x16
    PR_FONTHOVERCOLOR = 0x17
    PR_FONTHOVERSTYLE = 0x18
    PR_HOVERCOLOR = 0x19
    PR_ANTIALIAS = 0x1A
    PR_DELAY = 0x1B
    PR_PAUSED = 0x1C
    PR_VOLUME = 0x1D
    PR_REPEAT = 0x1E
    PR_BALANCE = 0x1F
    PR_ANGLE = 0x20
    PR_ONPLAYING = 0x21
    PR_ONNOTIFY = 0x22
    PR_ONMOUSEMOVE = 0x23
    PR_ONMOUSEOUT = 0x24
    PR_ONLBTNDOWN = 0x25
    PR_ONLBTNUP = 0x26
    PR_ONRBTNDOWN = 0x27
    PR_ONRBTNUP = 0x28
    PR_ONWHEELDOWN = 0x29
    PR_ONWHEELUP = 0x2A
    PR_BRIGHTNESS = 0x2B
    PR_ONPLAYEND = 0x2C
    PR_INDEX = 0x2D
    PR_COUNT = 0x2E
    PR_ONLINK = 0x2F
    PR_VISIBLE = 0x30
    PR_COLCOUNT = 0x31
    PR_ROWCOUNT = 0x32
    PR_TEXT = 0x33
    PR_MARGINX = 0x34
    PR_MARGINY = 0x35
    PR_HALIGN = 0x36
    PR_BORDERSOURCETL = 0x37
    PR_BORDERSOURCETC = 0x38
    PR_BORDERSOURCETR = 0x39
    PR_BORDERSOURCECL = 0x3A
    PR_BORDERSOURCECC = 0x3B
    PR_BORDERSOURCECR = 0x3C
    PR_BORDERSOURCEBL = 0x3D
    PR_BORDERSOURCEBC = 0x3E
    PR_BORDERSOURCEBR = 0x3F
    PR_BORDERHALIGNT = 0x40
    PR_BORDERHALIGNC = 0x41
    PR_BORDERHALIGNB = 0x42
    PR_BORDERVALIGNL = 0x43
    PR_BORDERVALIGNC = 0x44
    PR_BORDERVALIGNR = 0x45
    PR_SCROLLSOURCE = 0x46
    PR_CHECKSOURCE = 0x47
    PR_AUTOSCRAP = 0x48
    PR_ONSELECT = 0x49
    PR_RCLICKSCRAP = 0x4A
    PR_ONOPENING = 0x4B
    PR_ONOPENED = 0x4C
    PR_ONCLOSING = 0x4D
    PR_ONCLOSED = 0x4E
    PR_CARETX = 0x4F
    PR_CARETY = 0x50
    PR_IGNOREMOUSE = 0x51
    PR_TEXTPAUSED = 0x52
    PR_TEXTDELAY = 0x53
    PR_HOVERSOURCE = 0x54
    PR_PRESSEDSOURCE = 0x55
    PR_GROUPINDEX = 0x56
    PR_ALLOWALLUP = 0x57
    PR_SELECTED = 0x58
    PR_CAPTUREMASK = 0x59
    PR_POWER = 0x5A
    PR_ORIGWIDTH = 0x5B
    PR_ORIGHEIGHT = 0x5C
    PR_APPEARX = 0x5D
    PR_APPEARY = 0x5E
    PR_PARTMOTION = 0x5F
    PR_PARAM = 0x60
    PR_PARAM2 = 0x61
    PR_TOPINDEX = 0x62
    PR_READONLY = 0x63
    PR_CURSOR = 0x64
    PR_POSZOOMED = 0x65
    PR_ONPLAYSTART = 0x66
    PR_PARAM3 = 0x67
    PR_ONMOUSEIN = 0x68
    PR_ONMAPIN = 0x69
    PR_ONMAPOUT = 0x6A
    PR_MAPSOURCE = 0x6B
    PR_AMP = 0x6C
    PR_WAVELEN = 0x6D
    PR_SCROLLX = 0x6E
    PR_SCROLLY = 0x6F
    PR_FLIPH = 0x70
    PR_FLIPV = 0x71
    PR_ONIDLE = 0x72
    PR_DISTANCEX = 0x73
    PR_DISTANCEY = 0x74
    PR_CLIPLEFT = 0x75
    PR_CLIPTOP = 0x76
    PR_CLIPWIDTH = 0x77
    PR_CLIPHEIGHT = 0x78
    PR_DURATION = 0x79
    PR_THUMBSOURCE = 0x7A
    PR_BUTTONSOURCE = 0x7B
    PR_MIN = 0x7C
    PR_MAX = 0x7D
    PR_VALUE = 0x7E
    PR_ORIENTATION = 0x7F
    PR_SMALLCHANGE = 0x80
    PR_LARGECHANGE = 0x81
    PR_MAPTEXT = 0x82
    PR_GLYPHWIDTH = 0x83
    PR_GLYPHHEIGHT = 0x84
    PR_ZOOMY = 0x85
    PR_CLICKEDSOURCE = 0x86
    PR_ANIPAUSED = 0x87
    PR_ONHOLD = 0x88
    PR_ONRELEASE = 0x89
    PR_REVERSE = 0x8A
    PR_PLAYING = 0x8B
    PR_REWINDONLOAD = 0x8C
    PR_COMPOTYPE = 0x8D
    PR_FONTSHADOWCOLOR = 0x8E
    PR_FONTBORDER = 0x8F
    PR_FONTSHADOW = 0x90
    PR_ONKEYDOWN = 0x91
    PR_ONKEYUP = 0x92
    PR_ONKEYREPEAT = 0x93
    PR_HANDLEKEY = 0x94
    PR_ONFOCUSIN = 0x95
    PR_ONFOCUSOUT = 0x96
    PR_OVERLAY = 0x97
    PR_TAG = 0x98
    PR_CAPTURELINK = 0x99
    PR_FONTHOVERBORDER = 0x9A
    PR_FONTHOVERBORDERCOLOR = 0x9B
    PR_FONTHOVERSHADOW = 0x9C
    PR_FONTHOVERSHADOWCOLOR = 0x9D
    PR_BARSIZE = 0x9E
    PR_MUTEONLOAD = 0x9F
    PR_PLUSX = 0xA0
    PR_PLUSY = 0xA1
    PR_CARETHEIGHT = 0xA2
    PR_REPEATPOS = 0xA3
    PR_BLURSPAN = 0xA4
    PR_BLURDELAY = 0xA5
    PR_FONTCHANGEABLED = 0xA6
    PR_IMEMODE = 0xA7
    PR_FLOATANGLE = 0xA8
    PR_FLOATZOOMX = 0xA9
    PR_FLOATZOOMY = 0xAA
    PR_CAPMASKLEVEL = 0xAB
    PR_PADDINGLEFT = 0xAC
    PR_PADDING_RIGHT = 0xAD

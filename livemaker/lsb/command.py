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
"""LiveMaker LSB/LSC script command classes."""

import enum
from collections import OrderedDict

import construct

from loguru import logger

from lxml import etree

from .core import BaseSerializable, LiveParser, LiveParserArray, ParamType, PropertyType
from .novel import TpWord
from ..exceptions import BadLsbError


class CommandType(enum.IntEnum):
    """LiveMaker script command type.

    Note:
        In some cases, for some reason the internal LiveMaker Delphi class names differ from
        the string command name used in script files (ex. TComEntryHist becomes FormatHist).
        For these cases, use the command names from serialized script files.

    """

    If = 0x00
    Elseif = 0x01
    Else = 0x02
    Label = 0x03
    Jump = 0x04
    Call = 0x05
    Exit = 0x06
    Wait = 0x07
    BoxNew = 0x08
    ImgNew = 0x09
    MesNew = 0x0A
    Timer = 0x0B
    Movie = 0x0C
    Flip = 0x0D
    Calc = 0x0E
    VarNew = 0x0F
    VarDel = 0x10
    GetProp = 0x11
    SetProp = 0x12
    ObjDel = 0x13
    TextIns = 0x14
    MovieStop = 0x15
    ClrHist = 0x16
    Cinema = 0x17
    Caption = 0x18
    Menu = 0x19
    MenuClose = 0x1A
    Comment = 0x1B
    TextClr = 0x1C
    CallHist = 0x1D
    Button = 0x1E
    While = 0x1F
    WhileInit = 0x20
    WhileLoop = 0x21
    Break = 0x22
    Continue = 0x23
    ParticleNew = 0x24
    FireNew = 0x25
    GameSave = 0x26
    GameLoad = 0x27
    PCReset = 0x28
    Reset = 0x29
    Sound = 0x2A
    EditNew = 0x2B
    MemoNew = 0x2C
    Terminate = 0x2D
    DoEvent = 0x2E
    ClrRead = 0x2F
    MapImgNew = 0x30
    WaveNew = 0x31
    TileNew = 0x32
    SliderNew = 0x33
    ScrollbarNew = 0x34
    GaugeNew = 0x35
    CGCaption = 0x36
    MediaPlay = 0x37
    PrevMenuNew = 0x38
    PropMotion = 0x39
    FormatHist = 0x3A  # TComEntryHist
    SaveCabinet = 0x3B  # TComCabinetSave
    LoadCabinet = 0x3C  # TComCabinetLoad
    IFDEF = 0x3D  # TComIfdef
    IFNDEF = 0x3E  # TComIfndef
    ENDIF = 0x3F  # TComEndif


class LabelReference(BaseSerializable):
    """Internal use class for resolving label references.

    Label lookups will be done at serialization time as needed. When serializing
    to an LSC format, lookup will be done if the original reference is to a label index.
    When serializing to LSB, lookup will be done if the original reference is to a string
    label name.

    Note:
        If the original reference is in the correct format (i.e. string name for LSC to
        LSC or index for LSB to LSB, no lookup will be done to validate that the specified
        label exists)!

    """

    def __init__(self, Page="", Label=0):
        """Initialize a LabelReference.

        Params:
            Page (str): Page name (a path string). File extension for `Page` can be either
                .lsc or .lsb. When attempting to resolve the label reference, both extensions
                will be checked as needed.
            Label (int, str): Label index or string name.

        """
        self.Page = Page
        self.Label = Label

    def __str__(self):
        return "{}:{}".format(self.Page, self.Label)

    def __iter__(self):
        return iter(self.items())

    def __getitem__(self, key):
        if key == "Page":
            return self.Page
        elif key == "Label":
            return self.lookup_index()
        raise KeyError(key)

    def keys(self):
        return ["Page", "Label"]

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    def lookup_name(self):
        """Lookup the label name for this reference."""
        if isinstance(self.Label, int):
            if Label == 0:
                # Reference to start of page
                return ""
            # TODO lookup label
            logger.warning("Label lookup not yet implemented.")
            return str(self.Label)
        else:
            return str(self.Label)

    def lookup_index(self):
        """Lookup the label command index for this reference."""
        if isinstance(self.Label, int):
            return self.Label
        else:
            if not self.Label:
                # Reference to start of page
                return 0
            # TODO lookup label
            logger.warning("Label lookup not yet implemented.")
            return 0

    def to_lsc(self):
        """Return this label reference in text .lsc format."""
        return "\t".join([self.Page, self.lookup_name()])

    # @classmethod
    # def from_lsc(cls, Page, Label):
    #     return cls(Page, Label)

    def to_xml(self):
        """Return an XML representation of this label reference."""
        return ":".join([self.Page, self.lookup_name()])

    # @classmethod
    # def from_xml(cls, root):
    #     """Create a label reference from the specified XML element.

    #     Args:
    #         root: The root tree element.

    #     Raises:
    #         BadLsbError: If the XML tree could not be parsed.

    #     """
    #     if root.tag != 'Page':
    #         raise BadLsbError('XML node is not a page label reference')
    #     try:
    #         page, label = root.text.split(':', 1)
    #     except ValueError:
    #         # Reference to start of page
    #         page = root.text
    #         label = 0
    #     return LabelReference(page, label)

    @classmethod
    def _struct(cls):
        return construct.Struct(
            "Page" / construct.PascalString(construct.Int32ul, "cp932"),
            "Label" / construct.Int32ul,
        )

    @classmethod
    def from_struct(cls, struct):
        return cls(struct.Page, struct.Label)


class BaseCommand(BaseSerializable):
    """Base command class.

    Args:
        Indent: Indentation level. `Indent` level specifies the scope for commands like `If`/`WhileLoop`/etc.
        Mute: True if this command can be ignored during processing (used for comments).
        NotUpdate: Unknown.
        Color: Unknown (always False for novels?).
        LineNo: LineNo (line number) for this command. When a script is compiled into a binary LSB,
            target label name references (for jumps and calls) are replaced with a reference to
            the LineNo of the target label command.

    Attributes:
        type (:class:`CommandType`): Command type.
        args: OrderedDict of this command's arguments. If an argument is not applicable in
            a given LSB version, it's value should be set to None. Any arg set to None
            will not be serialized. If an arg is applicable in a given version and needs
            to be set to an empty value, use the empty string ''. This should make serialization
            for the .lsc formats consistent with how construct handles optional (version specific)
            values when reading to/from binary .lsb format.

    Note:
        The order `args` are initialized is important, since they will be serialized
        in the same order.

    """

    type = None
    _struct_fields = construct.Struct()

    def __init__(self, Indent=0, Mute=False, NotUpdate=False, Color=0, LineNo=0, **kwargs):
        self.Indent = Indent
        self.Mute = Mute
        self.NotUpdate = NotUpdate
        self.LineNo = LineNo
        self.Color = Color
        self.args = OrderedDict()

    def __str__(self):
        return " ".join(str(x) for x in [self.type.name] + list(self.args.values()))

    def __repr__(self):
        params = []
        for k in self.keys():
            v = self.get(k)
            if v is not None:
                params.append("{}={}".format(k, repr(v)))
        return "{}({})".format(type(self).__name__, ", ".join(params))

    def __iter__(self):
        return iter(self.items())

    def __getitem__(self, key):
        if key in ("type", "LineNo", "Indent", "Mute", "NotUpdate"):
            v = getattr(self, key)
        else:
            v = self.args[key]
        if isinstance(v, enum.Enum):
            v = v.name
        return v

    def keys(self):
        """Return a list of dictionary keys for this command."""
        return ["type", "LineNo", "Indent", "Mute", "NotUpdate"] + list(self.args.keys())

    def items(self):
        """Return a list of (key, value) pairs for this command."""
        return [(k, self[k]) for k in self.keys()]

    def to_lsc(self):
        """Return this command in text .lsc format."""
        out = [self.type.name, str(self.Indent), str(int(self.Mute)), str(self.NotUpdate), str(self.Color)]
        for arg in self.args:
            if hasattr(arg, "to_lsc"):
                out.append(arg.to_lsc())
            elif isinstance(arg, enum.Enum):
                out.append(str(arg.value))
            elif arg is not None:
                out.append(str(arg))
        return "\t".join(out)

    # def _parse_lsc_args(self, *args, **kwargs):
    #     raise NotImplementedError

    # @classmethod
    # def from_lsc(cls, data, **kwargs):
    #     """Parse text .lsc formatted data into a command object.

    #     Args:
    #         data (str) Text to parse.

    #     Raises:
    #         BadLsbError: If the data could not be parsed into this command.

    #     """
    #     if not data.startswith(cls.type.name):
    #         raise BadLsbError('Data does not contain a {} command'.format(cls.type.name))
    #     try:
    #         args = '\t'.split(data)
    #         (_, indent, mute, not_update, color) = args[:5]
    #     except ValueError:
    #         raise BadLsbError('Data does not contain a {} command'.format(cls.type.name))
    #     cmd = cls(Indent=int(indent), Mute=bool(int(mute)), NotUpdate=bool(int(not_update)), Color=int(color))
    #     if len(args) > 5:
    #         cmd._parse_lsc_args(*args[5:], **kwargs)
    #     return cmd

    def to_xml(self):
        """Return an XML representation of this command."""
        root = etree.Element(
            "Item",
            Command=self.type.name,
            LineNo=str(self.LineNo),
            Indent=str(self.Indent),
            Mute=str(int(self.Mute)),
            NotUpdate=str(int(self.NotUpdate)),
            Color=str(self.Color),
        )
        for k, v in self.args.items():
            item = etree.SubElement(root, k)
            if hasattr(v, "to_xml"):
                x = v.to_xml()
                if isinstance(x, (str, etree.CDATA)):
                    item.text = x
                elif isinstance(x, list):
                    for child in x:
                        item.append(child)
                else:
                    logger.warning("Ignoring unexpected child type returned by to_xml()")
            elif isinstance(v, enum.Enum):
                item.text = str(v.name)
            else:
                item.text = str(v)
        return root

    # def _parse_xml_args(self, root, **kwargs):
    #     raise NotImplementedError

    # @classmethod
    # def from_xml(cls, root, **kwargs):
    #     """Create a command from the specified XML element.

    #     Args:
    #         root: The root tree element.

    #     Raises:
    #         BadLsbError: If the XML tree could not be parsed.

    #     """
    #     if root.get('Command') != cls.type.name:
    #         raise BadLsbError('XML node is not a {}'.format(cls.type.name))
    #     cmd = cls(Indent=int(root.get('Indent')), Mute=bool(int(root.get('Mute'))),
    #               NotUpdate=bool(int(root.get('NotUpdate'))), Color=int(root.get('Color')))
    #     cmd._parse_xml_args(root, **kwargs)
    #     return cmd

    @classmethod
    def _struct(cls):
        """Return a construct Struct for this command type."""
        return construct.Struct(
            "type" / construct.Const(cls.type.name, construct.Enum(construct.Byte, CommandType)),
            "Indent" / construct.Int32ul,
            "Mute" / construct.Flag,
            "NotUpdate" / construct.Flag,
            "LineNo" / construct.Int32ul,
            # construct.Probe(),
            construct.Embedded(cls._struct_fields),
            # construct.Probe(),
        )


class If(BaseCommand):
    """Begin an If conditional block.

    Conditional block nesting is handled by the `Command.Indent` attribute.

    Args:
        Calc (:class:`LiveParser`): Conditional expression.

    """

    type = CommandType.If
    _struct_fields = construct.Struct(
        "Calc" / LiveParser._struct(),
    )

    def __init__(self, Calc=LiveParser(), **kwargs):
        super().__init__(**kwargs)
        if isinstance(Calc, construct.Container):
            Calc = LiveParser.from_struct(Calc)
        self.args["Calc"] = Calc

    # def _parse_lsc_args(self, Calc, *args, **kwargs):
    #     self.args['Calc'] = LiveParser.from_lsc(Calc)

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag == 'Calc':
    #             self.args['Calc'] = LiveParser.from_xml(child)


class Elseif(If):
    """Begin an Elseif conditional block."""

    type = CommandType.Elseif


class Else(BaseCommand):
    """Begin an Else conditional block."""

    type = CommandType.Else

    # def _parse_lsc_args(self, *args, **kwargs):
    #     pass

    # def _parse_xml_args(self, root, **kwargs):
    #     pass


class Label(BaseCommand):
    """Insert a named label which can be used as a Jump or Call target.

    Args:
        Name (str): Label name.

    Note:
        Original label names may not be available when decompiling a binary LSB.

    """

    type = CommandType.Label
    _struct_fields = construct.Struct(
        "Name" / construct.PascalString(construct.Int32ul, "cp932"),
    )

    def __init__(self, Name="", **kwargs):
        super().__init__(**kwargs)
        self.args["Name"] = Name

    # def _parse_lsc_args(self, Name, *args, **kwargs):
    #     self.args['Name'] = Name

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag == 'Name':
    #             self.args['Name'] = child.text


class Jump(BaseCommand):
    """Conditionally branch to a :class:`Label` or the start of a script.

    Args:
        Page (:class:`LabelReference`): Target label.
        Calc (:class:`LiveParser`): Jump to target label if `Calc` evaluates to True.

    """

    type = CommandType.Jump
    _struct_fields = construct.Struct(
        "Page" / LabelReference._struct(),
        "Calc" / LiveParser._struct(),
    )

    def __init__(self, Page=LabelReference(), Calc=LiveParser(), **kwargs):
        super().__init__(**kwargs)
        if isinstance(Page, construct.Container):
            Page = LabelReference.from_struct(Page)
        self.args["Page"] = Page
        if isinstance(Calc, construct.Container):
            Calc = LiveParser.from_struct(Calc)
        self.args["Calc"] = Calc

    # def _parse_lsc_args(self, Page, Label, Calc, *args, **kwargs):
    #     self.args['Page'] = LabelReference(Page, Label)
    #     self.args['Calc'] = LiveParser.from_lsc(Calc)

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag == 'Page':
    #             self.args['Page'] = LabelReference.from_xml(child)
    #         elif child.tag == 'Calc':
    #             self.args['Calc'] = LiveParser.from_xml(child)


class Call(BaseCommand):
    """Conditionally call a :class:`Label` or script with optional parameter arguments.

    Args:
        Page (:class:`LabelReference`): Target label.
        Result (str): Variable name to store call return value, if unset (empty string)
            the return value will not be stored.
        Calc (:class:`LiveParser`): Call target script if `Calc` evaluates to True.
        Params (:class:`LiveParserArray`): List of parameters to be passed into the called script.

    """

    type = CommandType.Call
    _struct_fields = construct.Struct(
        "Page" / LabelReference._struct(),
        "Result" / construct.PascalString(construct.Int32ul, "cp932"),
        "Calc" / LiveParser._struct(),
        "Params" / LiveParserArray._struct(construct.Int32ul),
    )

    def __init__(self, Page=LabelReference(), Result="", Calc=LiveParser(), Params=LiveParserArray(), **kwargs):
        super().__init__(**kwargs)
        if isinstance(Page, construct.Container):
            Page = LabelReference.from_struct(Page)
        self.args["Page"] = Page
        self.args["Result"] = Result
        if isinstance(Calc, construct.Container):
            Calc = LiveParser.from_struct(Calc)
        self.args["Calc"] = Calc
        if isinstance(Params, construct.ListContainer):
            Params = LiveParserArray.from_struct(Params)
        self.args["Params"] = Params

    # def _parse_lsc_args(self, Page, Label, Result, Calc, *args, **kwargs):
    #     raise NotImplementedError('Parsing Call from text LSC not supported')
    #     # TODO: Test this if someone finds an example .lsc
    #     self.args['Page'] = LabelReference(Page, Label)
    #     self.args['Result'] = Result
    #     self.args['Calc'] = LiveParser.from_lsc(Calc)
    #     self.args['Params'] = LiveParserArray.from_lsc(*args)

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag == 'Page':
    #             self.args['Page'] = LabelReference.from_xml(child)
    #         elif child.tag == 'Result':
    #             self.args['Result'] = child.text
    #         elif child.tag == 'Calc':
    #             self.args['Calc'] = LiveParser.from_xml(child)
    #         elif child.tag == 'Params':
    #             self.args['Params'] = LiveParserArray.from_xml(child)


class Exit(BaseCommand):
    """Conditionally return from the current script.

    Args:
        Calc (:class:`LiveParser`): Return if `Calc` evaluates to True.

    """

    type = CommandType.Exit
    _struct_fields = construct.Struct(
        "Calc" / LiveParser._struct(),
    )

    def __init__(self, Calc=LiveParser(), **kwargs):
        super().__init__(**kwargs)
        if isinstance(Calc, construct.Container):
            Calc = LiveParser.from_struct(Calc)
        self.args["Calc"] = Calc

    # def _parse_lsc_args(self, Calc, *args, **kwargs):
    #     self.args['Calc'] = LiveParser.from_lsc(Calc)

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag == 'Calc':
    #             self.args['Calc'] = LiveParser.from_xml(child)


class Wait(BaseCommand):
    """Conditionally wait for some amount of time.

    Args:
        Calc (:class:`LiveParser`): Wait if `Calc` evaluates to True.
        Time (:class:`LiveParser`): Time to wait in milliseconds.
        StopEvent (:class:`LiveParser`): Event processing will be stopped while waiting
            if `StopEvent` evaluates to True. Only used in LM versions 107 and later.

    """

    type = CommandType.Wait
    _struct_fields = construct.Struct(
        "Calc" / LiveParser._struct(),
        "Time" / LiveParser._struct(),
        "StopEvent" / construct.If(construct.this._._.version > 0x6A, LiveParser._struct()),
    )

    def __init__(self, Calc=LiveParser(), Time=LiveParser(), StopEvent=None, **kwargs):
        super().__init__(**kwargs)
        if isinstance(Calc, construct.Container):
            Calc = LiveParser.from_struct(Calc)
        self.args["Calc"] = Calc
        if isinstance(Time, construct.Container):
            Time = LiveParser.from_struct(Time)
        self.args["Time"] = Time
        if isinstance(StopEvent, construct.Container):
            StopEvent = LiveParser.from_struct(StopEvent)
        self.args["StopEvent"] = StopEvent

    # def _parse_lsc_args(self, Calc, Time, StopEvent, *args, **kwargs):
    #     self.args['Calc'] = LiveParser.from_lsc(Calc)
    #     self.args['Time'] = LiveParser.from_lsc(Time)
    #     if StopEvent is not None:
    #         self.args['StopEvent'] = LiveParser.from_lsc(StopEvent)
    #     else:
    #         self.args['StopEvent'] = None

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag in ('Calc', 'Time', 'StopEvent'):
    #             self.args[child.tag] = LiveParser.from_xml(child)


def _count_params(ctx):
    cmd_type = ctx.type
    if isinstance(cmd_type, str):
        cmd_type = CommandType[cmd_type]
    else:
        cmd_type = int(cmd_type)
    return sum(ctx._._.command_params[cmd_type])


class BaseComponentCommand(BaseCommand):
    """Base class for Component type commands.

    Component commands take list of LiveParser arguments, where the number of arguments
    depends on which parameters are enabled for a given command (i.e. the boolean flag
    list of parameters from the top level LMScript).

    Args:
        components (iterable(:class:`LiveParser`)): Iterable containing the parameters for this command.
            Each parameter should correspond to an enabled PropertyType for this command.
        command_params (list(bool)): List containing enabled parameter flags for this command.

    """

    # NOTE: We don't use LiveParserArray here because we would still need to do
    # the special handling for parameter names/types anyways
    type = None
    _struct_fields = construct.Struct(
        "components" / construct.Array(_count_params, LiveParser._struct()),
    )

    def __init__(self, components=[], command_params=[], **kwargs):
        super().__init__(**kwargs)
        if len(components) > sum(command_params):
            raise BadLsbError(
                "Got more param components than expected for this LM version,"
                " got {} expected {}.".format(len(components), sum(command_params))
            )
        self._component_keys = []
        if components:
            i = 0
            for type_index, flag in enumerate(command_params):
                if i >= len(components):
                    break
                if flag:
                    c = components[i]
                    if isinstance(c, construct.Container):
                        c = LiveParser.from_struct(c)
                    # type_index is 1-indexed (0 is PR_NONE and is ignored)
                    param_type = PropertyType(type_index + 1)
                    if param_type == PropertyType.PR_NAME:
                        # PR_NAME is a special case
                        self.args["Name"] = c
                        self._component_keys.append("Name")
                    else:
                        self.args[param_type.name] = c
                        self._component_keys.append(param_type.name)
                    i += 1

    def __getitem__(self, key):
        if key == "components":
            return [self.args[x] for x in self._component_keys]
        return super().__getitem__(key)

    def keys(self):
        return super().keys() + ["components"]

    # def _parse_lsc_args(self, *args, **kwargs):
    #     if 'command_params' not in kwargs:
    #         logger.warning('Attempting to parse component command without specifying param flags.')
    #     command_params = kwargs.get('command_params', [])
    #     components = [LiveParser.from_lsc(x) for x in args]
    #     if len(components) > sum(command_params):
    #         raise BadLsbError('Got more param components than expected for this LM version.')
    #     if components:
    #         i = 0
    #         for type_index, flag in enumerate(command_params):
    #             if i >= len(components):
    #                 break
    #             if flag:
    #                 c = components[i]
    #                 param_type = PropertyType(type_index)
    #                 if param_type == PropertyType.PR_NAME:
    #                     self.args['Name'] = c
    #                 else:
    #                     self.args[param_type.name] = c
    #                 i += 1

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag == 'Name' or child.tag in PropertyType.__members__:
    #             self.args[child.tag] = LiveParser.from_xml(child)


class BoxNew(BaseComponentCommand):
    """Draw a rectangle in the specified screen region."""

    type = CommandType.BoxNew


class ImgNew(BaseComponentCommand):
    """Draw an image in the specified screen region."""

    type = CommandType.ImgNew


class MesNew(BaseComponentCommand):
    """Draw a message box in the specified screen region."""

    type = CommandType.MesNew


class Timer(BaseComponentCommand):
    """Create a timer that calls a specified callback script when the timer expires."""

    type = CommandType.Timer


class Movie(BaseComponentCommand):
    "Play a movie clip in the specified screen region." ""

    type = CommandType.Movie


class Flip(BaseCommand):
    """Apply a named flip (transition) effect to the specified object.

    The specifics of how a flip is applied to an object varies depending on the
    flip type. See the LiveNovel docs for detailed information on flip types and
    parameters.

    Args:
        Wipe (:class:`LiveParser`): Flip effect name.
        Time (:class:`LiveParser`): Flip duration.
        Reverse (:class:`LiveParser`): If evaluates to True, flip direction will be reversed.
        Act (:class:`LiveParser`): If evaluates to FL_STAY, object will remain on screen
            after flip (i.e. a fade-in effect), if FL_OUT, object will be removed after
            flip (i.e. a fade-out).
        Targets (:class:`LiveParserArray`): List of objects to be affected by this flip.
        Delete (:class:`LiveParser`): If evaluates to TRUE, object will be deleted after this flip.
        Source (:class:`LiveParser`): Source for this flip. Only used in LM version > 100.
        DifferenceOnly (:class:`LiveParser`): Unknown. Only used in LM version > 116.
        StopEvent (:class:`LiveParser`): If evaluates to TRUE, event processing will be
            stopped during this flip. Only used in LM version > 106.
        Param (:class:`LiveParserArray`): List of parameter arguments for this flip, optional
            optional depending on flip type.

    """

    type = CommandType.Flip
    _struct_fields = construct.Struct(
        "Wipe" / LiveParser._struct(),
        "Time" / LiveParser._struct(),
        "Reverse" / LiveParser._struct(),
        "Act" / LiveParser._struct(),
        "Targets" / LiveParserArray._struct(construct.Int32ul),
        "Delete" / LiveParser._struct(),
        "Param" / LiveParserArray._struct(2, False),
        "Source" / construct.If(construct.this._._.version > 0x64, LiveParser._struct()),
        "StopEvent" / construct.If(construct.this._._.version > 0x6A, LiveParser._struct()),
        "DifferenceOnly" / construct.If(construct.this._._.version > 0x74, LiveParser._struct()),
    )

    def __init__(
        self,
        Wipe=LiveParser(),
        Time=LiveParser(),
        Reverse=LiveParser(),
        Act=LiveParser(),
        Targets=LiveParserArray(),
        Delete=LiveParser(),
        Source=None,
        DifferenceOnly=None,
        StopEvent=None,
        Param=LiveParserArray(prefixed=False),
        **kwargs,
    ):
        # TODO: lsb and lsc XML serialization order are different (lsb is by
        # version, and XML always puts Param last), for now we assume text lsc
        # version uses the same order as XML lsc, and NOT the same order as
        # binary lsb.
        super().__init__(**kwargs)
        if isinstance(Wipe, construct.Container):
            Wipe = LiveParser.from_struct(Wipe)
        self.args["Wipe"] = Wipe
        if isinstance(Time, construct.Container):
            Time = LiveParser.from_struct(Time)
        self.args["Time"] = Time
        if isinstance(Reverse, construct.Container):
            Reverse = LiveParser.from_struct(Reverse)
        self.args["Reverse"] = Reverse
        if isinstance(Act, construct.Container):
            Act = LiveParser.from_struct(Act)
        self.args["Act"] = Act
        if isinstance(Targets, construct.ListContainer):
            Targets = LiveParserArray.from_struct(Targets)
        self.args["Targets"] = Targets
        if isinstance(Delete, construct.Container):
            Delete = LiveParser.from_struct(Delete)
        self.args["Delete"] = Delete
        if isinstance(Source, construct.Container):
            Source = LiveParser.from_struct(Source)
        self.args["Source"] = Source
        if isinstance(DifferenceOnly, construct.Container):
            DifferenceOnly = LiveParser.from_struct(DifferenceOnly)
        self.args["DifferenceOnly"] = DifferenceOnly
        if isinstance(StopEvent, construct.Container):
            StopEvent = LiveParser.from_struct(StopEvent)
        self.args["StopEvent"] = StopEvent
        if isinstance(Param, construct.ListContainer):
            Param = LiveParserArray.from_struct(Param, prefixed=False)
        self.args["Param"] = Param

    # def _parse_lsc_args(self, Wipe, Time, Reverse, Act, Targets, Delete, Source, DifferenceOnly,
    #                     StopEvent, Param, *args, **kwargs):
    #     raise NotImplementedError
    #     # TODO: Implement this if someone finds an example .lsc

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag in ('Wipe', 'Time', 'Reverse', 'Act', 'Delete', 'Source', 'DifferenceOnly', 'StopEvent'):
    #             self.args[child.tag] = LiveParser.from_xml(child)
    #         elif child.tag == 'Targets':
    #             self.args['Targets'] = LiveParserArray.from_xml(child)
    #         elif child.tag == 'Param':
    #             self.args['Param'] = LiveParserArray.from_xml(child, prefixed=False)


class Calc(BaseCommand):
    """Evaluate some expression.

    Generally used to store the result of some calculation into a variable.

    Args:
        Calc (:class:`LiveParser`): Expression to evaluate.

    """

    type = CommandType.Calc
    _struct_fields = construct.Struct(
        "Calc" / LiveParser._struct(),
    )

    def __init__(self, Calc=LiveParser(), **kwargs):
        super().__init__(**kwargs)
        if isinstance(Calc, construct.Container):
            Calc = LiveParser.from_struct(Calc)
        self.args["Calc"] = Calc

    # def _parse_lsc_args(self, Calc, *args, **kwargs):
    #     self.args['Calc'] = LiveParser.from_lsc(Calc)

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag == 'Calc':
    #             self.args['Calc'] = LiveParser.from_xml(child)


class VarNew(BaseCommand):
    """Create a new variable and optionally initialize it.

    Args:
        Name (str): Variable name.
        Type (int or :class:`ParamType`): Data type.
        InitVal: Initial value.
        Scope: Variable scope (0 = global).

    """

    type = CommandType.VarNew
    _struct_fields = construct.Struct(
        "Name" / construct.PascalString(construct.Int32ul, "cp932"),
        "Type" / construct.Enum(construct.Byte, ParamType),
        "InitVal" / LiveParser._struct(),
        "Scope" / construct.Byte,
    )

    def __init__(self, Name="", Type=0, InitVal=LiveParser(), Scope=0, **kwargs):
        super().__init__(**kwargs)
        self.args["Name"] = Name
        if not isinstance(Type, ParamType):
            Type = ParamType(int(Type))
        self.args["Type"] = Type
        if isinstance(InitVal, construct.Container):
            InitVal = LiveParser.from_struct(InitVal)
        self.args["InitVal"] = InitVal
        self.args["Scope"] = int(Scope)

    # def _parse_lsc_args(self, Name, Type, InitVal, Scope, *args, **kwargs):
    #     self.args['Name'] = Name
    #     self.args['Type'] = ParamType(int(Type))
    #     self.args['InitVal'] = LiveParser.from_lsc(InitVal)
    #     self.args['Scope'] = int(Scope)

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag == 'Name':
    #             self.args['Name'] = child.text
    #         elif child.tag == 'Type':
    #             self.args['Type'] = ParamType(int(child.text))
    #         elif child.tag == 'InitVal':
    #             self.args['InitVal'] = LiveParser.from_xml(child)
    #         elif child.tag == 'Scope':
    #             self.args['Scope'] = int(child.text)


class VarDel(BaseCommand):
    """Delete a variable.

    Args:
        Name (str): Variable to delete.

    """

    type = CommandType.VarDel
    _struct_fields = construct.Struct(
        "Name" / construct.PascalString(construct.Int32ul, "cp932"),
    )

    def __init__(self, Name="", **kwargs):
        super().__init__(**kwargs)
        self.args["Name"] = Name

    # def _parse_lsc_args(self, Name, *args, **kwargs):
    #     self.args['Name'] = Name

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag == 'Name':
    #             self.args['Name'] = child.text


class GetProp(BaseCommand):
    """Get the specified object property.

    Args:
        ObjName (:class:`LiveParser`): Object name.
        ObjProp (:class:`LiveParser`): Property name.
        VarName (str): Object property will be stored in `VarName`.

    """

    type = CommandType.GetProp
    _struct_fields = construct.Struct(
        "ObjName" / LiveParser._struct(),
        "ObjProp" / LiveParser._struct(),
        "VarName" / construct.PascalString(construct.Int32ul, "cp932"),
    )

    def __init__(self, ObjName=LiveParser(), ObjProp=LiveParser(), VarName="", **kwargs):
        super().__init__(**kwargs)
        if isinstance(ObjName, construct.Container):
            ObjName = LiveParser.from_struct(ObjName)
        self.args["ObjName"] = ObjName
        if isinstance(ObjProp, construct.Container):
            ObjProp = LiveParser.from_struct(ObjProp)
        self.args["ObjProp"] = ObjProp
        self.args["VarName"] = VarName

    # def _parse_lsc_args(self, ObjName, ObjProp, VarName, *args, **kwargs):
    #     self.args['ObjName'] = LiveParser.from_lsc(ObjName)
    #     self.args['ObjProp'] = LiveParser.from_lsc(ObjProp)
    #     self.args['VarName'] = VarName

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag in ('ObjName', 'ObjProp'):
    #             self.args[child.tag] = LiveParser.from_xml(child)
    #         elif child.tag == 'VarName':
    #             self.args['VarName'] = child.text


class SetProp(BaseCommand):
    """Set the specified object property.

    Args:
        ObjName (:class:`LiveParser`): Object name.
        ObjProp (:class:`LiveParser`): Property name.
        Value (:class:`LiveParser`): Object property will be set to `Value`.

    """

    type = CommandType.SetProp
    _struct_fields = construct.Struct(
        "ObjName" / LiveParser._struct(),
        "ObjProp" / LiveParser._struct(),
        "Value" / LiveParser._struct(),
    )

    def __init__(self, ObjName=LiveParser(), ObjProp=LiveParser(), Value=LiveParser(), **kwargs):
        super().__init__(**kwargs)
        if isinstance(ObjName, construct.Container):
            ObjName = LiveParser.from_struct(ObjName)
        self.args["ObjName"] = ObjName
        if isinstance(ObjProp, construct.Container):
            ObjProp = LiveParser.from_struct(ObjProp)
        self.args["ObjProp"] = ObjProp
        if isinstance(Value, construct.Container):
            Value = LiveParser.from_struct(Value)
        self.args["Value"] = Value

    # def _parse_lsc_args(self, ObjName, ObjProp, Value, *args, **kwargs):
    #     self.args['ObjName'] = LiveParser.from_lsc(ObjName)
    #     self.args['ObjProp'] = LiveParser.from_lsc(ObjProp)
    #     self.args['Value'] = LiveParser.from_lsc(Value)

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag in ('ObjName', 'ObjProp', 'Value'):
    #             self.args[child.tag] = LiveParser.from_xml(child)


class ObjDel(BaseCommand):
    """Delete the specified object.

    Args:
        Name (:class:`LiveParser`): Name of object to delete.
    """

    type = CommandType.ObjDel
    _struct_fields = construct.Struct(
        "Name" / LiveParser._struct(),
    )

    def __init__(self, Name=LiveParser(), **kwargs):
        super().__init__(**kwargs)
        if isinstance(Name, construct.Container):
            Name = LiveParser.from_struct(Name)
        self.args["Name"] = Name


class TextIns(BaseCommand):
    """Insert a LiveNovel text block.

    The text block will be in a "compiled" TpWord format, rather than in the
    "HTML-like" LiveNovelScript format.

    Args:
        Text (:class:`TpWord`): The text block to insert.
        Target (:class:`LiveParser`): Name of the message box to display the text.
        Hist (:class:`LiveParser`): If TRUE, add the text to history.
        Wait (:class:`LiveParser`): If TRUE, wait until all text is read and message box
            is cleared before proceeding.
        StopEvent (:class:`LiveParser`): If TRUE, stop event processing while displaying
            this text. If FALSE, the value of `Wait` will be ignored. Only used if LM
            version > 106.

    """

    type = CommandType.TextIns
    _struct_fields = construct.Struct(
        "Text" / construct.Prefixed(construct.Int32ul, TpWord._struct()),
        # 'text' / construct.Prefixed(construct.Int32ul, construct.GreedyBytes),
        "Target" / LiveParser._struct(),
        "Hist" / LiveParser._struct(),
        "Wait" / LiveParser._struct(),
        "StopEvent" / construct.If(construct.this._._.version > 0x6A, LiveParser._struct()),
    )

    def __init__(
        self, Text=TpWord(), Target=LiveParser(), Hist=LiveParser(), Wait=LiveParser(), StopEvent=None, **kwargs
    ):
        super().__init__(**kwargs)
        if isinstance(Text, construct.Container):
            Text = TpWord.from_struct(Text)
        self.args["Text"] = Text
        if isinstance(Target, construct.Container):
            Target = LiveParser.from_struct(Target)
        self.args["Target"] = Target
        if isinstance(Hist, construct.Container):
            Hist = LiveParser.from_struct(Hist)
        self.args["Hist"] = Hist
        if isinstance(Wait, construct.Container):
            Wait = LiveParser.from_struct(Wait)
        self.args["Wait"] = Wait
        if isinstance(StopEvent, construct.Container):
            StopEvent = LiveParser.from_struct(StopEvent)
        self.args["StopEvent"] = StopEvent

    # def _parse_lsc_args(self, Text, ObjName, Hist, Wait, StopEvent, *args, **kwargs):
    #     self.args['Text'] = LiveParser.from_lsc(Text)
    #     self.args['ObjName'] = LiveParser.from_lsc(ObjName)
    #     self.args['Hist'] = LiveParser.from_lsc(Hist)
    #     self.args['Wait'] = LiveParser.from_lsc(Wait)
    #     if StopEvent is not None:
    #         self.args['StopEvent'] = LiveParser.from_lsc(StopEvent)
    #     else:
    #         self.args['StopEvent'] = None

    # def _parse_xml_args(self, root, **kwargs):
    #     logger.warning('Parsing XML for TextIns not fully supported.')
    #     for child in root:
    #         if child.tag == 'Text':
    #             self.args['Text'] = TpWord.from_xml(child)
    #         elif child.tag in ('ObjName', 'Hist', 'Wait', 'StopEvent'):
    #             self.args[child.tag] = LiveParser.from_xml(child)


class MovieStop(BaseCommand):
    """Stop playback and delete the specified media clip.

    Args:
        Target (:class:`LiveParser`): Name of media clip to stop.
        Time (:class:`LiveParser`): Time for playback to fade out in milliseconds
            (0 is immediate with no fade out).
        Wait (:class:`LiveParser`): If TRUE, command processing will not proceed until
            the media clip is deleted.
        StopEvent (:class:`LiveParser`): If TRUE, event processing will be stopped until
            media clip is deleted. Only used in LM version > 106

    """

    type = CommandType.MovieStop
    _struct_fields = construct.Struct(
        "Target" / LiveParser._struct(),
        "Time" / LiveParser._struct(),
        "Wait" / LiveParser._struct(),
        "StopEvent" / construct.If(construct.this._._.version > 0x6A, LiveParser._struct()),
    )

    def __init__(self, Target=LiveParser(), Time=LiveParser(), Wait=LiveParser(), StopEvent=None, **kwargs):
        super().__init__(**kwargs)
        if isinstance(Target, construct.Container):
            Target = LiveParser.from_struct(Target)
        self.args["Target"] = Target
        if isinstance(Time, construct.Container):
            Time = LiveParser.from_struct(Time)
        self.args["Time"] = Time
        if isinstance(Wait, construct.Container):
            Wait = LiveParser.from_struct(Wait)
        self.args["Wait"] = Wait
        if isinstance(StopEvent, construct.Container):
            StopEvent = LiveParser.from_struct(StopEvent)
        self.args["StopEvent"] = StopEvent

    # def _parse_lsc_args(self, Target, Time, Wait, StopEvent, *args, **kwargs):
    #     self.args['Target'] = LiveParser.from_lsc(Target)
    #     self.args['Time'] = LiveParser.from_lsc(Time)
    #     self.args['Wait'] = LiveParser.from_lsc(Wait)
    #     if StopEvent is not None:
    #         self.args['StopEvent'] = LiveParser.from_lsc(StopEvent)
    #     else:
    #         self.args['StopEvent'] = None

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag in ('Target', 'Time', 'Wait', 'StopEvent'):
    #             self.args[child.tag] = LiveParser.from_xml(child)


class ClrHist(Else):
    """Clear text history."""

    type = CommandType.ClrHist


class Cinema(BaseComponentCommand):
    """Play the specified cinema object."""

    type = CommandType.Cinema


class Caption(BaseComponentCommand):
    """Display a caption."""

    type = CommandType.Caption


class Menu(BaseComponentCommand):
    """Display a menu."""

    type = CommandType.Menu


class MenuClose(BaseCommand):
    """Close the specified menu.

    Args:
        Target (:class:`LiveParser`): Menu to close.

    """

    type = CommandType.MenuClose
    _struct_fields = construct.Struct(
        "Target" / LiveParser._struct(),
    )

    def __init__(self, Target=LiveParser(), **kwargs):
        super().__init__(**kwargs)
        if isinstance(Target, construct.Container):
            Target = LiveParser.from_struct(Target)
        self.args["Target"] = Target

    # def _parse_lsc_args(self, Target, *args, **kwargs):
    #     self.args['Target'] = LiveParser.from_lsc(Target)

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag == 'Target':
    #             self.args['Target'] = LiveParser.from_xml(child)


class Comment(Label):
    """Create a comment."""

    type = CommandType.Comment


class TextClr(BaseCommand):
    """Clear the specified text.

    Args:
        Target (:class:`LiveParser`): Message box to clear.

    """

    type = CommandType.TextClr
    _struct_fields = construct.Struct(
        "Target" / LiveParser._struct(),
    )

    def __init__(self, Target=LiveParser(), **kwargs):
        super().__init__(**kwargs)
        if isinstance(Target, construct.Container):
            Target = LiveParser.from_struct(Target)
        self.args["Target"] = Target

    # def _parse_lsc_args(self, Target, *args, **kwargs):
    #     self.args['Target'] = LiveParser.from_lsc(Target)

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag == 'Target':
    #             self.args['Target'] = LiveParser.from_xml(child)


class CallHist(BaseCommand):
    """Open the text history (backlog).

    Args:
        Target (:class:`LiveParser`): Message box to display history.
        Index (:class:`LiveParser`): Index of line to start showing history from.
        Count (:class:`LiveParser`): Number of lines to show.
        CutBreak (:class:`LiveParser`): Normally a gap is displayed separating script
            pages (scenario pages) in the history. If `CutBreak` is TRUE, this gap
            will be removed.
        FormatName (:class:`LiveParser`): Name of history formatter to use. Only used in
            LM version > 110.

    """

    type = CommandType.CallHist
    _struct_fields = construct.Struct(
        "Target" / LiveParser._struct(),
        "Index" / LiveParser._struct(),
        "Count" / LiveParser._struct(),
        "CutBreak" / LiveParser._struct(),
        "FormatName" / construct.If(construct.this._._.version > 0x6E, LiveParser._struct()),
    )

    def __init__(
        self,
        Target=LiveParser(),
        Index=LiveParser(),
        Count=LiveParser(),
        CutBreak=LiveParser(),
        FormatName=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if isinstance(Target, construct.Container):
            Target = LiveParser.from_struct(Target)
        self.args["Target"] = Target
        if isinstance(Index, construct.Container):
            Index = LiveParser.from_struct(Index)
        self.args["Index"] = Index
        if isinstance(Count, construct.Container):
            Count = LiveParser.from_struct(Count)
        self.args["Count"] = Count
        if isinstance(CutBreak, construct.Container):
            CutBreak = LiveParser.from_struct(CutBreak)
        self.args["CutBreak"] = CutBreak
        if isinstance(FormatName, construct.Container):
            FormatName = LiveParser.from_struct(FormatName)
        self.args["FormatName"] = FormatName

    # def _parse_lsc_args(self, Target, Index, Count, CutBreak, FormatName, *args, **kwargs):
    #     self.args['Target'] = LiveParser.from_lsc(Target)
    #     self.args['Index'] = LiveParser.from_lsc(Index)
    #     self.args['Count'] = LiveParser.from_lsc(Count)
    #     self.args['CutBreak'] = LiveParser.from_lsc(CutBreak)
    #     if FormatName is not None:
    #         self.args['FormatName'] = LiveParser.from_lsc(FormatName)
    #     else:
    #         self.args['FormatName'] = None

    # def _parse_xml_args(self, root, **kwargs):
    #     for child in root:
    #         if child.tag in ('Target', 'Index', 'Count', 'CutBreak', 'FormatName'):
    #             self.args[child.tag] = LiveParser.from_xml(child)


class Button(BaseComponentCommand):
    """Create a clickable button."""

    type = CommandType.Button


class While(BaseCommand):
    """Insert while loop block conditional statement.

    Args:
        Calc (:class:`LiveParser`): Loop conditional expression (i.e. i < 10). If TRUE
            the loop will be run, otherwise execution will branch to `End` + 2 (Since
            `End` is followed by the closing `WhileLoop` command).
        End (int): Index of the last command contained by the loop. The command at `End`
            will be followed by the closing `WhileLoop` command for this loop.


    Note:
        We do not fully support serializing loops to and from XML. In an LSB file,
        a loop block looks like::

            TComWhileInit i = 0
            TComWhile i < 10
                <Nested commands>...
            TComWhileLoop i = i + 1

        TComWhileInit and TComWhile will have the same index (they are treated internally by
        LiveMaker as a single command).

        In LiveMaker's actual XML lsc format, they store this entire pattern as a single
        `While` command, even though it gets compiled into the 3 separate `WhileInit`,
        `While`, `WhileLoop` commands (with the final `WhileLoop` inserted before the
        next command with an indentation level outside of the loop).

        In pylivemaker, we just output the commands individually in the order they appear in
        an LSB.

    """

    type = CommandType.While
    _struct_fields = construct.Struct(
        "Calc" / LiveParser._struct(),
        "End" / construct.Int32ul,
    )

    def __init__(self, Calc=LiveParser(), End=0, **kwargs):
        super().__init__(**kwargs)
        if isinstance(Calc, construct.Container):
            Calc = LiveParser.from_struct(Calc)
        self.args["Calc"] = Calc
        self.args["End"] = int(End)


class WhileInit(BaseCommand):
    """Initialize a while loop.

    Args:
        Calc (:class:`LiveParser`): Loop initialization statement (i.e. i = 0).

    """

    type = CommandType.WhileInit
    _struct_fields = construct.Struct(
        "Calc" / LiveParser._struct(),
    )

    def __init__(self, Calc=LiveParser, **kwargs):
        super().__init__(**kwargs)
        if isinstance(Calc, construct.Container):
            Calc = LiveParser.from_struct(Calc)
        self.args["Calc"] = Calc

    def _parse_lsc_args(self, Calc, *args, **kwargs):
        self.args["Calc"] = LiveParser.from_lsc(Calc)

    def _parse_xml_args(self, root, **kwargs):
        for child in root:
            if child.tag == "Calc":
                self.args["Calc"] = LiveParser.from_xml(child)


class WhileLoop(WhileInit):
    """Close a while loop.

    Args:
        Start (int): Index of the command preceding this loop. After evaluating the
            statement in `Calc`, command processing will return to `Start` + 1,
            which should be the opening `WhileInit`/`While` commands.

    Note:
        `WhileLoop` is handled a subclass of :class:`WhileInit` for struct parsing purposes.
        `Calc` is an expression to be evaluated when reaching the end of the loop
        (i.e. i = i + 1).

    """

    type = CommandType.WhileLoop
    _struct_fields = construct.Struct(
        construct.Embedded(WhileInit._struct_fields),
        "Start" / construct.Int32ul,
    )

    def __init__(self, Start=0, **kwargs):
        super().__init__(**kwargs)
        self.args["Start"] = int(Start)


class Break(Exit):
    """Loop break statement.

    Args:
        End (int): Index for the end of the current loop.

    Note:
        `Break` is handled a subclass of :class:`Exit` for struct parsing purposes.
        If `Calc` is TRUE, command processing will exit the current loop.

    """

    type = CommandType.Break
    _struct_fields = construct.Struct(
        construct.Embedded(Exit._struct_fields),
        "End" / construct.Int32ul,
    )

    def __init__(self, End=0, **kwargs):
        super().__init__(**kwargs)
        self.args["End"] = int(End)


class Continue(Exit):
    """Loop continue statement.

    Args:
        Start (int): Index for the start of the current loop.

    Note:
        `Continue` is handled a subclass of :class:`Exit` for struct parsing purposes.
        If `Calc` is TRUE, command processing will return to the start of the current loop.

    """

    type = CommandType.Continue
    _struct_fields = construct.Struct(
        construct.Embedded(Exit._struct_fields),
        "Start" / construct.Int32ul,
    )

    def __init__(self, Start=0, **kwargs):
        super().__init__(**kwargs)
        self.args["Start"] = int(Start)


class ParticleNew(BaseComponentCommand):
    """Insert a particle effect."""

    type = CommandType.ParticleNew


class FireNew(BaseComponentCommand):
    """Insert a flame effect."""

    type = CommandType.FireNew


class GameSave(BaseCommand):
    """Create a game save.

    Args:
        No (:class:`LiveParser`): Save slot number to use.
        Page (str): Save location is normally the command following this `GameSave`.
            If `Page` is specified, it will be used as the save location.
        Label (int): Label index in `Page` to load. Only used in LM version > 104.
        Caption (:class:`LiveParser`): Caption for this save.

    """

    type = CommandType.GameSave
    # NOTE: LabelReference is not used since the label field is versioned for
    # GameSave
    _struct_fields = construct.Struct(
        "No" / LiveParser._struct(),
        "Page" / construct.PascalString(construct.Int32ul, "cp932"),
        "Label" / construct.If(construct.this._._.version > 0x68, construct.Int32ul),
        "Caption" / LiveParser._struct(),
    )

    def __init__(self, No=LiveParser(), Page="", Label=None, Caption=LiveParser(), **kwargs):
        super().__init__(**kwargs)
        if isinstance(No, construct.Container):
            No = LiveParser.from_struct(No)
        self.args["No"] = No
        self.args["Page"] = Page
        if Label is not None:
            self.args["Label"] = int(Label)
        else:
            self.args["Label"] = None
        if isinstance(Caption, construct.Container):
            No = LiveParser.from_struct(Caption)
        self.args["Caption"] = Caption


class GameLoad(BaseCommand):
    """Load a game save.

    Args:
        No (:class:`LiveParser`): Save slot number to load.

    """

    type = CommandType.GameLoad
    _struct_fields = construct.Struct(
        "No" / LiveParser._struct(),
    )

    def __init__(self, No=LiveParser(), **kwargs):
        super().__init__(**kwargs)
        if isinstance(No, construct.Container):
            No = LiveParser.from_struct(No)
        self.args["No"] = No


class PCReset(BaseCommand):
    """Reset program counter to the specified page.

    See LiveNovel documentation for details.

    Args:
        Page (:class:`LabelReference`): PC will be reset to `Page`.
        AllClear (int): If non-zero, all call stack information will be
            cleared after the reset.

    """

    type = CommandType.PCReset
    _struct_fields = construct.Struct(
        "Page" / LabelReference._struct(),
        "AllClear" / construct.Byte,
    )

    def __init__(self, Page=LabelReference(), AllClear=0, **kwargs):
        super().__init__(**kwargs)
        if isinstance(Page, construct.Container):
            LabelReference.from_struct(Page)
        self.args["Page"] = Page
        self.args["AllClear"] = int(AllClear)


class Reset(PCReset):
    """Delete all components, variables and stacks and transfer processing to the specified page."""

    type = CommandType.Reset


class Sound(BaseComponentCommand):
    """Play the specified sound."""

    type = CommandType.Sound


class EditNew(BaseComponentCommand):
    """Create an edit component."""

    type = CommandType.EditNew


class MemoNew(BaseComponentCommand):
    """Create a memo component."""

    type = CommandType.MemoNew


class Terminate(Else):
    """Unconditionally exit the program."""

    type = CommandType.Terminate


class DoEvent(Else):
    """Process the specified event."""

    type = CommandType.DoEvent


class ClrRead(Else):
    """Clear read text information."""

    type = CommandType.ClrRead


class MapImgNew(BaseComponentCommand):
    """Create an image surface component."""

    type = CommandType.MapImgNew


class WaveNew(BaseComponentCommand):
    """Create a wave surface component."""

    type = CommandType.WaveNew


class TileNew(BaseComponentCommand):
    """Create a tiled surface component."""

    type = CommandType.TileNew


class SliderNew(BaseComponentCommand):
    """Create a slider."""

    type = CommandType.SliderNew


class ScrollbarNew(BaseComponentCommand):
    """Create a scrollbar."""

    type = CommandType.ScrollbarNew


class GaugeNew(BaseComponentCommand):
    """Create a gauge."""

    type = CommandType.GaugeNew


class CGCaption(BaseComponentCommand):

    type = CommandType.CGCaption


class MediaPlay(BaseCommand):
    """Play the specified media.

    Args:
        Target (:class:`LiveParser`): Media object to play.

    """

    type = CommandType.MediaPlay
    _struct_fields = construct.Struct(
        "Target" / LiveParser._struct(),
    )

    def __init__(self, Target=LiveParser(), **kwargs):
        super().__init__(**kwargs)
        if isinstance(Target, construct.Container):
            Target = LiveParser.from_struct(Target)
        self.args["Target"] = Target


class PrevMenuNew(BaseComponentCommand):
    """Create a preview menu component."""

    type = CommandType.PrevMenuNew


class PropMotion(BaseCommand):
    """Gradually change the specified object property to the specified value over time.

    Args:
        Name (:class:`LiveParser`): Name of this motion.
        ObjName (:class:`LiveParser`): Object to modify.
        ObjProp (:class:`LiveParser`): Property to modify.
        Value (:class:`LiveParser`): Value to set.
        Time (:class:`LiveParser`): Duration in milliseconds.
        MoveType (:class:`LiveParser`): Move type, see LiveNovel docs for details.
        Paused: (:class:`LiveParser`): Unknown. Only used for LM version > 107.

    """

    type = CommandType.PropMotion
    _struct_fields = construct.Struct(
        "Name" / LiveParser._struct(),
        "ObjName" / LiveParser._struct(),
        "ObjProp" / LiveParser._struct(),
        "Value" / LiveParser._struct(),
        "Time" / LiveParser._struct(),
        "MoveType" / LiveParser._struct(),
        "Paused" / construct.If(construct.this._._.version > 0x6B, LiveParser._struct()),
    )

    def __init__(
        self,
        Name=LiveParser(),
        ObjName=LiveParser(),
        ObjProp=LiveParser(),
        Value=LiveParser(),
        Time=LiveParser(),
        MoveType=LiveParser(),
        Paused=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if isinstance(Name, construct.Container):
            Name = LiveParser.from_struct(Name)
        self.args["Name"] = Name
        if isinstance(ObjName, construct.Container):
            ObjName = LiveParser.from_struct(ObjName)
        self.args["ObjName"] = ObjName
        if isinstance(ObjProp, construct.Container):
            ObjProp = LiveParser.from_struct(ObjProp)
        self.args["ObjProp"] = ObjProp
        if isinstance(Value, construct.Container):
            Value = LiveParser.from_struct(Value)
        self.args["Value"] = Value
        if isinstance(Time, construct.Container):
            Time = LiveParser.from_struct(Time)
        self.args["Time"] = Time
        if isinstance(MoveType, construct.Container):
            MoveType = LiveParser.from_struct(MoveType)
        self.args["MoveType"] = MoveType
        if isinstance(Paused, construct.Container):
            Paused = LiveParser.from_struct(Paused)
        self.args["Paused"] = Paused


class FormatHist(BaseCommand):
    """Register a history display format.

    Args:
        Name (:class:`LiveParser`): Name of this format.
        Target (:class:`LiveParser`): Target message box. Only used in LM version > 110.

    """

    type = CommandType.FormatHist
    _struct_fields = construct.Struct(
        "Name" / LiveParser._struct(),
        "Target" / construct.If(construct.this._._.version > 0x6E, LiveParser._struct()),
    )

    def __init__(self, Name=LiveParser(), Target=LiveParser(), **kwargs):
        super().__init__(**kwargs)
        if isinstance(Name, construct.Container):
            Name = LiveParser.from_struct(Name)
        self.args["Name"] = Name
        if isinstance(Target, construct.Container):
            Target = LiveParser.from_struct(Target)
        self.args["Target"] = Target


class SaveCabinet(BaseComponentCommand):
    """Move screen components into the specified save cabinet.

    See LiveNovel docs for details.

    Args:
        Act (:class:`LiveParser`): If FALSE the specified screen objects will be saved.
            If TRUE, all screen objects other than the specified ones will be saved.
        Targets (:class:`LiveParserArray`): List of objects to save.

    """

    type = CommandType.SaveCabinet
    _struct_fields = construct.Struct(
        construct.Embedded(BaseComponentCommand._struct_fields),
        "Act" / LiveParser._struct(),
        "Targets" / LiveParserArray._struct(construct.Int32ul),
    )

    def __init__(self, Act=LiveParser(), Targets=LiveParserArray(), **kwargs):
        super().__init__(**kwargs)
        if isinstance(Act, construct.Container):
            Act = LiveParser.from_struct(Act)
        self.args["Act"] = Act
        if isinstance(Targets, construct.ListContainer):
            Targets = LiveParserArray.from_struct(Targets)
        self.args["Targets"] = Targets


class LoadCabinet(SaveCabinet):
    """Load screen objects from the specified cabinet."""

    type = CommandType.LoadCabinet


class IFDEF(Else):
    """Ifdef compiler directive, removed during LSB compilation."""

    type = CommandType.IFDEF


class IFNDEF(Else):
    """Ifndef compiler directive, removed during LSB compilation."""

    type = CommandType.IFNDEF


class ENDIF(Else):
    """Endif compiler directive, removed during LSB compilation."""

    type = CommandType.ENDIF


_command_classes = {x: globals()[x.name] for x in CommandType}
_command_structs = [globals()[x.name]._struct() for x in CommandType]

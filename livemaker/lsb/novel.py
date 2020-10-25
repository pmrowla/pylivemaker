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
"""LiveMaker LiveNovel LNS script classes."""

import enum
import os
import re
import _markupbase
from bisect import bisect

import construct

from loguru import logger

from lxml import etree

from .core import BaseSerializable, LiveParser
from ..exceptions import BadLnsError, InvalidCharError
from .translate import BaseTranslatable


class LNSTag(enum.Enum):

    a = "A"
    br = "BR"
    clr = "CLR"
    condition = "CONDITION"
    div = "DIV"
    event = "EVENT"
    histchar = "HISTCHAR"
    indent = "INDENT"
    img = "IMG"
    pg = "PG"
    ps = "PS"
    scenario = "SCENARIO"
    style = "STYLE"
    txspd = "TXSPD"
    txspf = "TXSPF"
    txspn = "TXSPN"
    txsps = "TXSPS"
    undent = "UNDENT"
    var = "VAR"

    @classmethod
    def open(cls, tag, attributes={}):
        out = ["<{}".format(tag.value)]
        if attributes:
            out.append(" {}".format(" ".join(['{}="{}"'.format(k, v) for k, v in attributes.items()])))
        out.append(">")
        return "".join(out)

    @classmethod
    def close(cls, tag):
        return "</{}>".format(tag.value)


class AlignEnum(enum.IntEnum):
    """Horizontal or vertical alignment.

    Original script tags have separate possible values for horizontal/vertical alignment
    depending on the tag, but internally LM handles them all as a single enum type when
    compiled into a binary script.

    Note: When translating scripts, users should be aware that pylivemaker will accept
    all possible alignment values for any tags that take "ALIGN" attributes,
    but LM behavior may be undefined depending on specific tag/alignment combinations.
    Refer to the official LiveNovel documentation for information on which tags horizontal (L/C/R)
    alignment values and which tags take vertical (T/C/B) values.
    """

    LEFT = 1
    RIGHT = 2
    CENTER = 3
    TOP = 4
    BOTTOM = 5


class BreakType(enum.IntEnum):
    """Break type."""

    LINE = 0
    PAGE = 1
    PAUSE = 2
    CLEAR = 3


class TWdType(enum.IntEnum):
    """LiveNovel script word (entry) type."""

    TWdChar = 0x01
    TWdOpeDiv = 0x02
    TWdOpeReturn = 0x03
    TWdOpeIndent = 0x04
    TWdOpeUndent = 0x05
    TWdOpeEvent = 0x06
    TWdOpeVar = 0x07
    TWdImg = 0x09
    TWdOpeHistChar = 0x0A


class BaseTWdGlyph(BaseSerializable):
    """Base TWd Glyph type.

    A TWdGlyph is a single glyph or entry in a compiled LiveNovel script.
    A tag from LiveNovel's documented "HTML-like" scenario script format can generally be
    mapped to a TWdGlyph subclass.

    Args:
        Condition (int): Index for the condition to be applied to this glyph

    """

    type = None
    _struct_fields = construct.Struct(
        # Note: LiveMaker's parser for TWdGlyph has a conditional to only read
        # this field if their condition obj pointer is non-null, but as far as
        # I can tell, for our purposes it will always be non-null?
        "condition"
        / construct.If(construct.this._._.version >= 104, construct.Int32sl),
    )

    def __init__(self, condition=None, **kwargs):
        self._keys = set(("type", "condition"))
        self.condition = condition

    def __str__(self):
        return "<{}>".format(repr(self))

    def __repr__(self):
        return "{}({})".format(
            type(self).__name__, ", ".join(["{}={}".format(k, getattr(self, k)) for k in self._keys])
        )

    def __iter__(self):
        return iter(self.items())

    def __getitem__(self, key):
        if key in self._keys:
            v = getattr(self, key)
            if isinstance(v, enum.Enum):
                v = v.name
            return v
        raise KeyError

    def keys(self):
        return list(self._keys)

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    def to_lsc(self):
        raise NotImplementedError("TWd glyph serialization must be done in parent TpWord block.")

    def to_xml(self):
        raise NotImplementedError("TWd glyph serialization must be done in parent TpWord block.")

    @classmethod
    def _struct(cls):
        """Return a construct Struct for this TWd type."""
        return construct.Struct(
            "type" / construct.Const(cls.type.name, construct.Enum(construct.Byte, TWdType)),
            construct.Embedded(cls._struct_fields),
            # construct.Probe(),
        )

    @classmethod
    def lns_escape(self, s):
        for i, j in [("\\", "\\\\"), ("<", "\\<"), (">", "\\>"), ("{", "\\{"), ("}", "\\}"), ('"', '\\"')]:
            s = s.replace(i, j)
        return s


class BaseTWdReal(BaseTWdGlyph):
    """Base class for TWdReal types.

    Args:
        link_name (str): Name of referenced link for this glyph.
            Used in LNScript version < 105.
        link (int): Index of referenced link for this glyph.
            Used in LNScript version >= 105.
        text_speed (int): Text display speed for this glyph.

    """

    # BaseTWdReal is an abstract type and is always used via a subclass
    type = None
    _struct_fields = construct.Struct(
        construct.Embedded(BaseTWdGlyph._struct_fields),
        "link_name"
        / construct.If(construct.this._._.version < 105, construct.PascalString(construct.Int32ul, "cp932")),
        "link" / construct.If(construct.this._._.version >= 105, construct.Int32sl),
        "text_speed" / construct.Int32ul,
    )

    def __init__(self, link_name=None, link=None, text_speed=0, **kwargs):
        super().__init__(**kwargs)
        self._keys.update(("link_name", "link", "text_speed"))
        self.link_name = link_name
        self.link = link
        self.text_speed = text_speed


class _TWdCharAdapter(construct.Adapter):
    # construct PaddedString only supports ascii and utf encodings

    def _decode(self, obj, ctx, path):
        ch = obj.to_bytes(2, byteorder="big").decode("cp932")
        if ch.startswith("\x00"):
            ch = ch[1]
        return ch

    def _encode(self, obj, ctx, path):
        return int.from_bytes(obj.encode("cp932"), byteorder="big")


class TWdChar(BaseTWdReal):
    """An individual CP932 encoded character.

    All text in a LiveNovel script is compiled into runs of TWdChar glyphs.

    Args:
        ch (str): The character.
        decorator (int): Index of the decorator (style) to be applied to this
            character.

    """

    type = TWdType.TWdChar
    _struct_fields = construct.Struct(
        construct.Embedded(BaseTWdReal._struct_fields),
        "ch" / _TWdCharAdapter(construct.Int16ul),
        "decorator" / construct.Int32sl,
    )

    def __init__(self, ch="", decorator=0, **kwargs):
        super().__init__(**kwargs)
        try:
            ch.encode("cp932")
        except UnicodeEncodeError:
            raise InvalidCharError(ch)
        self._keys.update(("ch", "decorator"))
        self.ch = ch
        self.decorator = decorator

    def __str__(self):
        return self.ch

    def match(self, other):
        """Return True if these two characters can be grouped into one text run."""
        if not isinstance(other, TWdChar):
            return False
        for k in self._keys:
            if k == "ch":
                continue
            if getattr(self, k) != getattr(other, k):
                return False
        return True


class TWdOpeDiv(BaseTWdGlyph):
    """Specify div (row) attributes.

    Args:
        align (int): Horizontal alignment.
        padleft (int): Left padding.
        padright (int): Right padding.
        noheight (int): TRUE if this line has no height (the next line will
            be drawn at the same y-coordiante as this one).

    """

    type = TWdType.TWdOpeDiv
    _struct_fields = construct.Struct(
        construct.Embedded(BaseTWdGlyph._struct_fields),
        "align" / construct.Byte,
        "padleft" / construct.If(construct.this._._.version >= 105, construct.Int32sl),
        "padright" / construct.If(construct.this._._.version >= 105, construct.Int32sl),
        "noheight" / construct.If(construct.this._._.version >= 105, construct.Byte),
    )

    def __init__(self, align=0, padleft=0, padright=0, noheight=0, **kwargs):
        super().__init__(**kwargs)
        self._keys.update(("align", "padleft", "padright", "noheight"))
        self.align = int(align)
        self.padleft = int(padleft)
        self.padright = int(padright)
        self.noheight = int(noheight)

    def __str__(self):
        attrs = {
            "ALIGN": AlignEnum(self.align).name,
            "PADLEFT": self.padleft,
            "PADRIGHT": self.padright,
            "NOHEIGHT": self.noheight,
        }
        return LNSTag.open(LNSTag.div, attrs)


class TWdOpeReturn(BaseTWdGlyph):
    """Insert a line or page break.

    Args:
        break_type (int): Break type.

    """

    type = TWdType.TWdOpeReturn
    _struct_fields = construct.Struct(
        construct.Embedded(BaseTWdGlyph._struct_fields),
        "break_type" / construct.Byte,
    )

    def __init__(self, break_type=0, **kwargs):
        super().__init__(**kwargs)
        self._keys.add("break_type")
        self.break_type = int(break_type)

    def __str__(self):
        break_type = BreakType(self.break_type)
        if break_type == BreakType.LINE:
            # new line
            tag = LNSTag.br
        elif break_type == BreakType.PAGE:
            # new page
            tag = LNSTag.pg
        elif break_type == BreakType.PAUSE:
            # TODO: verify this
            # pause for mouse click
            tag = LNSTag.ps
        else:
            # TODO: verify this
            tag = LNSTag.clr
        return LNSTag.open(tag)


class TWdOpeIndent(BaseTWdGlyph):
    """Increase indent level."""

    type = TWdType.TWdOpeIndent

    def __str__(self):
        return LNSTag.open(LNSTag.indent)


class TWdOpeUndent(BaseTWdGlyph):
    """Decrease indent level."""

    type = TWdType.TWdOpeUndent

    def __str__(self):
        return LNSTag.open(LNSTag.undent)


class TWdOpeEvent(BaseTWdGlyph):
    """Run the specified event.

    Args:
        event (str): Event name and arguments.

    """

    type = TWdType.TWdOpeEvent
    _struct_fields = construct.Struct(
        construct.Embedded(BaseTWdGlyph._struct_fields),
        "event" / construct.PascalString(construct.Int32ul, "cp932"),
    )

    def __init__(self, event="", **kwargs):
        super().__init__(**kwargs)
        self._keys.add("event")
        self.event = event

    def __str__(self):
        event = self.event.split("\r\n")
        e = event[0]
        args = event[1:]
        if e.startswith("\x01"):
            # System event
            e = e[1:]
            if args:
                args = " {}".format(" ".join(['"{}"'.format(x) for x in args]))
            else:
                args = ""
            return "{{{0}{1}}}".format(e, args)
        return LNSTag.open(LNSTag.event, {"VALUE": "\\r\\n".join([e] + args)})

    @property
    def _parts(self):
        return self.event.split("\r\n")

    @property
    def name(self):
        name = self._parts[0]
        if self.is_system(name):
            return name[1:]
        return name

    @property
    def args(self):
        return self.parts[1:]

    @staticmethod
    def is_system(name):
        return name.startswith("\x01")


class TWdOpeVar(BaseTWdGlyph):
    """Insert the value of the specified variable.

    Args:
        decorator (int): Index of the decorator to be applied to this text
        unk3: Unknown.
        link_name: Name of the link to be applied to this glyph.
            Used in LN scenario script versions 100 to 104 (inclusive).
        link: Index of the link to be applied to this glyph. Used in LN scenario script version > 104.
        var_name_params (:class:`LiveParser`): Variable name. Used in LN scenario script version < 102.
        var_name (str): Variable name. Used in LN scenario script version >= 102.

    """

    type = TWdType.TWdOpeVar
    _struct_fields = construct.Struct(
        construct.Embedded(BaseTWdGlyph._struct_fields),
        "decorator" / construct.Int32sl,
        "unk3" / construct.If(construct.this._._.version >= 100, construct.Int32ul),
        "link_name"
        / construct.If(100 <= construct.this._._.version < 105, construct.PascalString(construct.Int32ul, "cp932")),
        "link" / construct.If(construct.this._._.version >= 105, construct.Int32sl),
        "var_name_params" / construct.If(construct.this._._.version < 102, LiveParser._struct()),
        "var_name"
        / construct.If(construct.this._._.version >= 102, construct.PascalString(construct.Int32ul, "cp932")),
    )

    def __init__(
        self, decorator=0, unk3=None, link_name=None, link=None, var_name_params=None, var_name=None, **kwargs
    ):
        super().__init__(**kwargs)
        self._keys.update(("decorator", "unk3", "link_name", "link", "var_name_params", "var_name"))
        self.decorator = decorator
        self.unk3 = unk3
        self.link_name = link_name
        self.link = link
        if isinstance(var_name_params, construct.Container):
            var_name_params = LiveParser.from_struct(var_name_params)
        self.var_name_params = var_name_params
        self.var_name = var_name

    def __str__(self):
        return LNSTag.open(LNSTag.var, {"NAME": self.lns_escape(self.name), "unk3": self.unk3})

    @property
    def name(self):
        """Return the variable name for this object."""
        if self.var_name is not None:
            return self.var_name
        elif self.var_name_params is not None:
            return str(self.var_name_params)
        return ""


class TWdImg(BaseTWdReal):
    """Display an image in the text box.

    Args:
        src (str): Dispaly image.
        align (int): Vertical alignment.
        hoversrc (str): Image to display on mouse hover.
        mgnleft (int): Left margin in pixels.
        mgnright (int): Right margin in pixels.
        mgntop (int): Top margin in pixels.
        mgnbottom (int): Bottom margin in pixels.
        downsrc (str): Image to display on mouse click.

    Note:
        This displays the image inline with text, and is not the same thing as displaying a CG.
        One use case is to insert icons for replaying sounds into the history backlogger.

    """

    type = TWdType.TWdImg
    _struct_fields = construct.Struct(
        construct.Embedded(BaseTWdReal._struct_fields),
        "src" / construct.PascalString(construct.Int32ul, "cp932"),
        "align" / construct.Byte,
        "hoversrc"
        / construct.If(construct.this._._.version >= 103, construct.PascalString(construct.Int32ul, "cp932")),
        "mgnleft"
        / construct.If(
            construct.this._._.version >= 105,
            construct.Int32sl,
        ),
        "mgnright"
        / construct.If(
            construct.this._._.version >= 105,
            construct.Int32sl,
        ),
        "mgntop"
        / construct.If(
            construct.this._._.version >= 105,
            construct.Int32sl,
        ),
        "mgnbottom"
        / construct.If(
            construct.this._._.version >= 105,
            construct.Int32sl,
        ),
        "downsrc"
        / construct.If(construct.this._._.version >= 105, construct.PascalString(construct.Int32ul, "cp932")),
    )

    def __init__(
        self, src="", align=0, hoversrc="", mgnleft=0, mgnright=0, mgntop=0, mgnbottom=0, downsrc="", **kwargs
    ):
        super().__init__(**kwargs)
        self._keys.update(("src", "align", "hoversrc", "mgnleft", "mgnright", "mgntop", "mgnbottom", "downsrc"))
        self.src = src
        self.align = int(align)
        self.hoversrc = hoversrc
        if mgnleft is None:
            mgnleft = 0
        self.mgnleft = int(mgnleft)
        if mgnright is None:
            mgnright = 0
        self.mgnright = int(mgnright)
        if mgntop is None:
            mgntop = 0
        self.mgntop = int(mgntop)
        if mgnbottom is None:
            mgnbottom = 0
        self.mgnbottom = int(mgnbottom)
        self.downsrc = downsrc

    def __str__(self):
        attrs = {
            "SRC": self.src,
            "HOVERSRC": self.hoversrc,
            "DOWNSRC": self.downsrc,
            "ALIGN": AlignEnum(self.align).name,
            "MGNLEFT": self.mgnleft,
            "MGNRIGHT": self.mgnright,
            "MGNTOP": self.mgntop,
            "MGNBOTTOM": self.mgnbottom,
        }
        return LNSTag.open(LNSTag.img, attrs)


class TWdOpeHistChar(TWdOpeVar):
    """Display the value of a variable in history only."""

    type = TWdType.TWdOpeHistChar

    def __str__(self):
        return LNSTag.open(LNSTag.histchar, {"NAME": self.lns_escape(self.name), "unk3": self.unk3})


_twd_classes = {x: globals()[x.name] for x in TWdType}
_twd_structs = [globals()[x.name]._struct() for x in TWdType]


class TDecorate(BaseSerializable):
    """Text decorator (font styling) to apply to a glyph.

    Font tags from an original script are replaced with references
    to an entry in the font/style table for this LiveMaker game when
    compiling to LSB.

    Args:
        count: The total number of TWd glyphs affected by this decorator.

    """

    def __init__(
        self, count=0, unk2=0, unk3=0, unk4=0, unk5=0, unk6=0, unk7=0, unk8="", ruby="", unk10=0, unk11=0, **kwargs
    ):
        self.count = count
        self.unk2 = unk2
        self.unk3 = unk3
        self.unk4 = unk4
        self.unk5 = unk5
        self.unk6 = unk6
        self.unk7 = unk7
        self.unk8 = unk8
        self.ruby = ruby
        self.unk10 = unk10
        self.unk11 = unk11

    def __iter__(self):
        return iter(self.items())

    def __getitem__(self, key):
        if key in self.keys():
            return getattr(self, key)
        raise KeyError

    def __str__(self):
        return "TDecorate({})".format(", ".join(["{}={}".format(k, v) for k, v in self.items()]))

    def keys(self):
        return ["count", "unk2", "unk3", "unk4", "unk5", "unk6", "unk7", "unk8", "ruby", "unk10", "unk11"]

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    def to_lsc(self):
        raise NotImplementedError

    def to_xml(self):
        raise NotImplementedError

    @classmethod
    def _struct(cls):
        return construct.Struct(
            "count" / construct.Int32ul,
            "unk2" / construct.Int32ul,
            "unk3" / construct.Int32ul,
            "unk4" / construct.Int32ul,
            "unk5" / construct.Byte,
            "unk6" / construct.Byte,
            "unk7" / construct.IfThenElse(construct.this._._.version < 100, construct.Byte, construct.Int32ul),
            "unk8" / construct.PascalString(construct.Int32ul, "cp932"),
            "ruby" / construct.PascalString(construct.Int32ul, "cp932"),
            "unk10"
            / construct.If(
                construct.this._._.version >= 100,
                construct.Int32ul,
            ),
            "unk11"
            / construct.If(
                construct.this._._.version >= 100,
                construct.Int32ul,
            ),
        )


class TWdCondition(BaseSerializable):
    """Text display conditions.

    Display condition for a glyph determines things like whether or not it will
    be only displayed the history backlogger.

    Args:
        count: The total number of TWd glyphs affected by this condition.
        target: Target message box (i.e. history message box).

    """

    def __init__(self, count=0, target="", **kwargs):
        self.count = count
        self.target = target

    def __str__(self):
        return "TWdCondition({})".format(", ".join(["{}={}".format(k, v) for k, v in self.items()]))

    def __iter__(self):
        return iter(self.items())

    def __getitem__(self, key):
        if key in self.keys():
            return getattr(self, key)
        raise KeyError

    def keys(self):
        return ["count", "target"]

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    def to_lsc(self):
        raise NotImplementedError

    def to_xml(self):
        raise NotImplementedError

    @classmethod
    def _struct(cls):
        return construct.Struct(
            "count" / construct.Int32ul,
            "target" / construct.PascalString(construct.Int32ul, "cp932"),
        )


class TWdLink(BaseSerializable):
    """Hyperlink (i.e. make a glyph clickable).

    Args:
        count: The total number of TWd glyphs affected by this link.
        event: Event to run on click.
        unk3: Unknown.

    """

    def __init__(self, count=0, event="", unk3="", **kwargs):
        self.count = count
        self.event = event
        self.unk3 = unk3

    def __str__(self):
        s = "TWdLink({})".format(", ".join(["{}={}".format(k, v) for k, v in self.items()]))
        return s.replace("\r", "\\r").replace("\n", "\\n")

    def __iter__(self):
        return iter(self.items())

    def __getitem__(self, key):
        if key in self.keys():
            return getattr(self, key)
        raise KeyError

    def keys(self):
        return ["count", "event", "unk3"]

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    def to_lsc(self):
        raise NotImplementedError

    def to_xml(self):
        raise NotImplementedError

    @classmethod
    def _struct(cls):
        return construct.Struct(
            "count" / construct.Int32ul,
            "event" / construct.PascalString(construct.Int32ul, "cp932"),
            "unk3" / construct.PascalString(construct.Int32ul, "cp932"),
        )


class _TpWordVersionAdapter(construct.Adapter):
    # TpWord version is an integer converted to a 3-byte (3-digit) string

    def _decode(self, obj, ctx, path):
        return int(obj)

    def _encode(self, obj, ctx, path):
        return "{:03}".format(obj).encode("ascii")


class TpWord(BaseSerializable):
    """Compiled LiveNovel scenario script.

    Args:
        version (int): LiveNovel scenario script version.
        decorators (list(:class:)`TDecorate`)): List of decorators (text styles) used in this script.
        conditions (list(:class:`TWdCondition`)): List of conditions used in this script.
        links (list(:class:`TWdLink`)): List of links used in this script.
        body (list(:class:`BaseTWdGlyph`))): Compiled script text body.

    Note:
        LiveNovel scenario script version is independent of LiveMaker (command) script version.

    """

    def __init__(self, version=0, decorators=[], conditions=[], links=[], body=[], **kwargs):
        self.version = version
        if isinstance(decorators, construct.ListContainer):
            decorators = [TDecorate.from_struct(x) for x in decorators]
        self.decorators = decorators
        if isinstance(conditions, construct.ListContainer):
            conditions = [TWdCondition.from_struct(x) for x in conditions]
        self.conditions = conditions
        if isinstance(links, construct.ListContainer):
            links = [TWdLink.from_struct(x) for x in links]
        self.links = links
        if isinstance(body, construct.ListContainer):
            self._body = []
            for x in body:
                if isinstance(x, int):
                    self._body.append(x)
                else:
                    self._body.append(_twd_classes[TWdType(int(x.type))].from_struct(x))
        else:
            self._body = body

    def __iter__(self):
        return iter(self.items())

    def __getitem__(self, key):
        if key in self.keys():
            return getattr(self, key)
        raise KeyError

    def keys(self):
        return ["version", "decorators", "conditions", "links", "body"]

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    def to_lsc(self):
        dec = LNSDecompiler(sep="")
        return dec.decompile(self)

    def to_xml(self):
        dec = LNSDecompiler()
        xml = dec.decompile(self)
        if "\x01" in xml:
            logger.warning("Removing illegal xml char \\x01")
            xml = xml.replace("\x01", "*")
        return etree.CDATA(xml)

    @classmethod
    def _struct(cls):
        # Note: LiveMaker's parser silently ignores invalid TWdType's,
        # so use Byte as the last Select() option to do the same thing
        select_subcons = _twd_structs
        select_subcons.append(construct.Byte)
        return construct.Struct(
            "signature" / construct.Const(b"TpWord"),
            "version" / _TpWordVersionAdapter(construct.Bytes(3)),
            "decorators" / construct.PrefixedArray(construct.Int32ul, TDecorate._struct()),
            "conditions"
            / construct.If(
                construct.this.version >= 104,
                construct.PrefixedArray(construct.Int32ul, TWdCondition._struct()),
            ),
            "links"
            / construct.If(
                construct.this.version >= 105,
                construct.PrefixedArray(construct.Int32ul, TWdLink._struct()),
            ),
            "body" / construct.PrefixedArray(construct.Int32ul, construct.Select(*select_subcons)),
        )

    @classmethod
    def from_struct(cls, struct):
        d = {k: v for k, v in struct.items()}
        if struct.decorators is not None:
            d["decorators"] = [TDecorate.from_struct(x) for x in struct.decorators]
        if struct.conditions is not None:
            d["conditions"] = [TWdCondition.from_struct(x) for x in struct.conditions]
        if struct.links is not None:
            d["links"] = [TWdLink.from_struct(x) for x in struct.links]
        body = []
        for x in struct.body:
            if isinstance(x, int):
                body.append(x)
            else:
                body.append(_twd_classes[TWdType(int(x.type))].from_struct(x))
        d["body"] = body
        return cls(**d)

    @property
    def body(self):
        return self._body

    def replace_body(self, body, ruby_text=None):
        """Replace the current text block body with a new one.

        Updates the appropriate character counts as needed.

        Args:
            body (list(:class:`TWdGlyph`)): The new body. This should generally be
                a script body compiled via `LNSCompiler.compile()`.
            ruby_text (dict): Optional dict mapping {decorator_id: text}.
                If provided, the ruby entry for the specified decorator will
                be replaced.

        Raises:
            `BadLnsError`: If the new script body is invalid for this TpWord block
                (for example, if it references a decorator that does not exist).

        """
        decorator_counts = [0] * len(self.decorators)
        if self.conditions is not None:
            condition_counts = [0] * len(self.conditions)
        if self.links is not None:
            link_counts = [0] * len(self.links)
        for i, wd in enumerate(body):
            try:
                if hasattr(wd, "decorator") and wd.decorator is not None:
                    decorator_counts[wd.decorator] += 1
            except IndexError:
                raise BadLnsError("TWd #{} ({}) references a decorator that does not exist.".format(i, wd))
            try:
                if self.conditions is not None:
                    if hasattr(wd, "condition") and wd.condition is not None:
                        condition_counts[wd.condition] += 1
            except IndexError:
                raise BadLnsError("TWd #{} ({}) references a condition that does not exist.".format(i, wd))
            try:
                if self.links is not None:
                    if hasattr(wd, "link") and wd.link is not None:
                        link_counts[wd.link] += 1
            except IndexError:
                raise BadLnsError("TWd #{} ({}) references a condition that does not exist.".format(i, wd))
            # TODO: not sure how old scripts which use link_name use the count
            # field, implement this if/when someone finds an example.
            if hasattr(wd, "link_name") and wd.link_name:
                raise NotImplementedError(
                    "Inserting scripts from LM versions which use link_name is not supported,"
                    " please file a bug report."
                )
        self._body = body
        for i, dec in enumerate(self.decorators):
            dec.count = decorator_counts[i]
        if self.conditions is not None:
            for i, cond in enumerate(self.conditions):
                cond.count = condition_counts[i]
        if self.links is not None:
            for i, link in enumerate(self.links):
                link.count = link_counts[i]

        if ruby_text:
            warned = False
            for id_, text in ruby_text.items():
                try:
                    dec = self.decorators[id_]
                except IndexError:
                    raise BadLnsError(f"Ruby text entry {id_} references a decorator that does not exist.")
                if dec.ruby != text:
                    if not warned:
                        logger.warning("Ruby text support is experimental")
                        warned = True
                    dec.ruby = text

    def get_text_blocks(self):
        """Return :class:`LNSText` blocks for this TpWord."""
        return LNSText.from_tpword(self)

    def replace_text_blocks(self, blocks, strict=True):
        """Replace text blocks for this TpWord with the contents of ``blocks``.

        Args:
            blocks (:class:`LNSText`): Replacement blocks. ``blocks`` should be an object
                previously returned by `get_text_blocks()` (but with modified text).
            strict (bool): If True, `BadLnsError` will be raised if ``blocks`` contains blocks
                with Blake2 digests which do not match the current TpWord.
        """
        new_body = self.body[:]
        if strict and blocks != self.get_text_blocks():
            raise BadLnsError("Replacement blocks do not match this TpWord.")
        # iterate in reverse so we can use slice assignment
        for block in reversed(blocks):
            start = block.start
            # use style/cond/link/etc values for initial char
            start_ch = new_body[start]
            d = {}
            for attr in ("decorator", "text_speed", "link_name", "link", "condition"):
                d[attr] = getattr(start_ch, attr, None)
            new_block = []
            for ch in block.text:
                if ch == "\n":
                    new_ch = TWdOpeReturn(**d)
                else:
                    new_ch = TWdChar(ch=ch, **d)
                new_block.append(new_ch)
            new_body[block.start : block.end] = new_block
        self.replace_body(new_body)


class LNSDecompiler(object):
    """Attempt to decompile a TpWord text block into something that resembles
    LiveMaker's LiveNovel scenario script format.

    Args:
        sep (str): Output line separator (defaults to ``os.linesep``).
        include_comments (bool): Include comment lines in output.
        text_only (bool): Output text only (all tags will be removed except for variable names).

    Raises:
        ValueError: If `tpword` is not a :class:`TpWord` instance.

    """

    def __init__(self, sep=os.linesep, include_comments=True, text_only=False):
        self.sep = sep
        self.include_comments = include_comments
        self.text_only = text_only
        self._reset()

    def _reset(self):
        # reset decompiler state
        self._lines = []
        self._line = []
        self._condition = 0
        self._decorator = 0
        self._link = 0
        self._link_name = ""
        self._text_speed = None
        self._div = False
        self._need_endl = False

    def _header(self):
        lines = []
        if self.include_comments:
            lines.append(";pylm")
            # TODO: ideally find font table and actually label styles properly
            if self.tpword.decorators is not None:
                lines.append("; Font styles:")
                for i, x in enumerate(self.tpword.decorators):
                    lines.append("; {:4}: {}".format(i, x))
            if self.tpword.conditions is not None:
                lines.append("; Display conditions:")
                for i, x in enumerate(self.tpword.conditions):
                    lines.append("; {:4}: {}".format(i, x))
            if self.tpword.links is not None:
                lines.append("; Links:")
                for i, x in enumerate(self.tpword.links):
                    lines.append("; {:4}: {}".format(i, x))
            lines.extend(
                [
                    ";---------------------------------------",
                    "; BEGIN DECOMPILED SCRIPT",
                    ";---------------------------------------",
                ]
            )
        lines.append(LNSTag.open(LNSTag.scenario, {"VER": self.tpword.version}))
        return lines

    def _endl(self):
        # end line
        self._lines.append("".join(self._line))
        self._line = []
        self._need_endl = False

    def _check_cond(self, w):
        if hasattr(w, "condition"):
            if w.condition != self._condition:
                if self._line:
                    self.endl()
                self._condition = w.condition
                if self._condition is not None:
                    self._line.append(LNSTag.open(LNSTag.condition, {"ID": self._condition}))
                    self._endl()

    def _close_decorator(self):
        if self._decorator:
            self._line.append(LNSTag.close(LNSTag.style))
            self._decorator = 0

    def _check_decorator(self, w):
        if hasattr(w, "decorator"):
            if w.decorator != self._decorator:
                self._close_link()
                self._close_decorator()
                if self._need_endl:
                    self._endl()
                self._decorator = w.decorator
                if self._decorator:
                    attrs = {"ID": self._decorator}
                    dec = self.tpword.decorators[self._decorator]
                    ruby = dec.get("ruby")
                    if ruby:
                        attrs["RUBY"] = ruby
                    self._line.append(LNSTag.open(LNSTag.style, attrs))
        else:
            self._close_link()
            self._close_decorator()

    def _close_link(self):
        if self._link or self._link_name:
            self._line.append(LNSTag.close(LNSTag.a))
            self._link = 0
            self._link_name = ""

    def _check_link(self, w):
        if hasattr(w, "link") and w.link is not None:
            if w.link != self._link:
                self._close_link()
                if self._need_endl:
                    self._endl()
                self._link = w.link
                if self._link:
                    self._line.append(LNSTag.open(LNSTag.a, {"ID": self._link}))
        elif hasattr(w, "link_name") and w.link_name is not None:
            if w.link_name != self._link_name:
                self._close_link()
                if self._need_endl:
                    self._endl()
                self._link_name = w.link_name
                if self._link_name:
                    self._line.append(LNSTag.open(LNSTag.a, {"NAME": self._link_name}))
        else:
            self._close_link()

    def _check_spd(self, w):
        if hasattr(w, "text_speed") and w.text_speed is not None:
            if w.text_speed != self._text_speed:
                self._text_speed = w.text_speed
                if self._text_speed == 0:
                    # instant
                    self._line.append(LNSTag.open(LNSTag.txspf))
                elif self._text_speed == 50:
                    # normal
                    self._line.append(LNSTag.open(LNSTag.txspn))
                elif self._text_speed == 300:
                    # slow
                    self._line.append(LNSTag.open(LNSTag.txsps))
                else:
                    self._line.append(LNSTag.open(LNSTag.txspd, {"TIME": self._text_speed}))

    def _close_div(self):
        if self._div:
            self._close_link()
            self._close_decorator()
            if self._line:
                self._endl()
            self._line.append(LNSTag.close(LNSTag.div))
            self._endl()

    def _decompile_full(self, tpword):
        self._reset()
        self.tpword = tpword
        self._lines.extend(self._header())
        for w in tpword.body:
            # Tag nesting should always follow:
            # <div>
            #   <decorator>
            #     <link>
            #     </link
            #   </decorator>
            # </div>
            #
            # note: condition is not a nested tag, it just replaces the
            # previous condition state for all objects
            self._check_cond(w)

            if w.type == TWdType.TWdOpeDiv:
                # link/decorator closed in _close_div() if needed
                self._close_div()
                # tag gets its own line
                self._lines.append(str(w))
                self._div = True

            self._check_decorator(w)
            self._check_link(w)

            if self._need_endl:
                self._endl()

            self._check_spd(w)

            if w.type == TWdType.TWdChar:
                self._line.append(str(w.ch))
            elif w.type == TWdType.TWdOpeDiv:
                pass  # already handled
            elif w.type == TWdType.TWdOpeReturn:
                self._line.append(str(w))
                self._need_endl = True
            elif w.type == TWdType.TWdOpeIndent:
                self._line.append(str(w))
            elif w.type == TWdType.TWdOpeUndent:
                self._line.append(str(w))
            elif w.type == TWdType.TWdOpeEvent:
                if self._line:
                    self._endl()
                # tag gets its own line
                self._lines.append(str(w))
            elif w.type == TWdType.TWdOpeVar:
                self._line.append(str(w))
            elif w.type == TWdType.TWdImg:
                self._line.append(str(w))
            elif w.type == TWdType.TWdOpeHistChar:
                if self._line:
                    self._endl()
                # tag gets its own line
                self._lines.append(str(w))
            else:
                raise NotImplementedError
        if self._line:
            self._endl()
        if self.include_comments:
            self._lines.extend(
                [
                    ";---------------------------------------",
                    "; END DECOMPILED SCRIPT",
                    ";---------------------------------------",
                ]
            )
        return self.sep.join(self._lines)

    def decompile(self, tpword):
        """Decompile the specified TpWord scenario script.

        Args:
            tpword (:class:`TpWord`): TpWord object to decompile.

        """
        if self.text_only:
            self._reset()
            for w in tpword.body:
                if w.type == TWdType.TWdChar:
                    self._line.append(str(w.ch))
                elif w.type == TWdType.TWdOpeReturn:
                    self._endl()
                elif w.type == TWdType.TWdOpeVar:
                    self._line.append(str(w))
                elif w.type == TWdType.TWdOpeHistChar:
                    if self._line:
                        self._endl()
                    # tag gets its own line
                    self._lines.append(str(w))
            if self._line:
                self._endl()
            return self.sep.join(self._lines)
        else:
            return self._decompile_full(tpword)


# Regular expressions used for parsing

interesting_normal = re.compile(r"(?<!\\)[<{]")
incomplete = re.compile("&[a-zA-Z#]")

entityref = re.compile("&([a-zA-Z][-.a-zA-Z0-9]*)[^a-zA-Z0-9]")
charref = re.compile("&#(?:[0-9]+|[xX][0-9a-fA-F]+)[^0-9a-fA-F]")

starttagopen = re.compile("[<{][a-zA-Z]")
piclose = re.compile(r"(?<!\\)[>}]")
commentclose = re.compile(r"--\s*>")
# Note:
#  1) if you change tagfind/attrfind remember to update locatestarttagend too;
#  2) if you change tagfind/attrfind and/or locatestarttagend the parser will
#     explode, so don't do it.
# see http://www.w3.org/TR/html5/tokenization.html#tag-open-state
# and http://www.w3.org/TR/html5/tokenization.html#tag-name-state
tagfind_tolerant = re.compile(r"([a-zA-Z][^\t\n\r\f />}\x00]*)(?:\s|/(?![>}]))*")
attrfind_event_strict = re.compile(r'((?:")([^"]*)(?:"))(?:\s|/(?![>}]))*')
attrfind_tolerant = re.compile(
    r'((?<=["\s/])[^\s/>}][^\s/=>}]*)(\s*=+\s*' r'("[^"\\]*(?:\\.[^"\\]*)*"|(?!["])[^>\s]*))?(?:\s|/(?![>}]))*'
)
locatestarttagend_tolerant = re.compile(
    r"""
  (?<!\\)[<{][a-zA-Z][^\t\n\r\f />}\x00]*       # tag name
  (?:[\s/]*                          # optional whitespace before attribute name
    (?:(?<=['"\s/])[^\s/>}][^\s/=>}]*  # attribute name
      (?:\s*=+\s*                    # value indicator
        (?:'[^']*'                   # LITA-enclosed value
          |"[^"]*"                   # LIT-enclosed value
          |(?!['"])[^>}\s]*           # bare value
         )
         (?:\s*,)*                   # possibly followed by a comma
       )?(?:\s|/(?![>}]))*
     )*
   )?
  \s*                                # trailing whitespace
""",
    re.VERBOSE,
)
endendtag = re.compile(">")
# the HTML 5 spec, section 8.1.2.2, doesn't allow spaces between
# </ and the tag name, so maybe this should be fixed
endtagfind = re.compile(r"</\s*([a-zA-Z][-.a-zA-Z0-9:_]*)\s*>")


class LNSCompiler(_markupbase.ParserBase):
    """Attempt to compile a LiveNovel LNS script into a TpWord block.

    Based on Python3 html.parser.HTMLParser.

    Note:
        This is only intended to be used to compile scripts which have been
        decompiled by pylivemaker and then translated/edited for patching.
        Attempting to compile a script which was not initially generated by
        pylivemaker may not work as intended.

    """

    # Most LNS tags don't have matching </tag> end tags
    END_TAGS = (LNSTag.a.name, LNSTag.style.name, LNSTag.div.name)

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset this instance.  Loses all unprocessed data."""
        self.rawdata = ""
        self.lasttag = "???"
        self.interesting = interesting_normal
        _markupbase.ParserBase.reset(self)
        self.condition = 0
        self.decorator = 0
        self.text_speed = 50
        self.link = 0
        self.link_name = ""
        self.tpword_body = []
        self.version = 0
        self.ruby_text = {}

    def compile(self, script):
        """Compile a [decompiled] script into a TpWord block.

        Args:
            script (str): Script data

        """
        if not script.startswith(";pylm"):
            logger.warning("Attempting to compile script which was not generated by pylivemaker.")
        for line in script.splitlines():
            if not line.startswith(";"):
                self.feed(line)
        return self.tpword_body

    def feed(self, data):
        r"""Feed data to the parser.
        Call this as often as you want, with as little or as much text
        as you want (may include '\n').
        """
        self.rawdata = self.rawdata + data
        self.goahead(0)

    def close(self):
        """Handle any buffered data."""
        self.goahead(1)

    __starttag_text = None

    def get_starttag_text(self):
        """Return full source of start tag: '<...>'."""
        return self.__starttag_text

    # Internal -- handle data as far as reasonable.  May leave state
    # and data to be processed by a subsequent call.  If 'end' is
    # true, force handling all data as if followed by EOF marker.
    def goahead(self, end):
        rawdata = self.rawdata
        i = 0
        n = len(rawdata)
        while i < n:
            match = self.interesting.search(rawdata, i)  # < or {
            if match:
                j = match.start()
            else:
                j = n
            if i < j:
                self.handle_data(self.unescape(rawdata[i:j]))
            i = self.updatepos(i, j)
            if i == n:
                break
            startswith = rawdata.startswith
            if startswith("<", i) or startswith("{", i):
                if starttagopen.match(rawdata, i):  # < + letter
                    k = self.parse_starttag(i)
                elif startswith("</", i):
                    k = self.parse_endtag(i)
                elif (i + 1) < n:
                    if startswith("{}"):
                        # empty system event
                        self.handle_eventtag("", [])
                        k = i + 2
                    else:
                        logger.warning("got < or { at end of line")
                        self.handle_data("<")
                        k = i + 1
                else:
                    break
                if k < 0:
                    if not end:
                        break
                    k = rawdata.find(">", i + 1)
                    if k < 0:
                        k = rawdata.find("<", i + 1)
                        if k < 0:
                            k = i + 1
                    else:
                        k += 1
                    self.handle_data(self.unescape(rawdata[i:k]))
                i = self.updatepos(i, k)
            else:
                assert 0, "interesting.search() lied"
        # end while
        if end and i < n:
            self.handle_data(self.unescape(rawdata[i:n]))
            i = self.updatepos(i, n)
        self.rawdata = rawdata[i:]

    # Internal -- handle starttag, return end or -1 if not terminated
    def parse_starttag(self, i):
        self.__starttag_text = None
        endpos = self.check_for_whole_start_tag(i)
        if endpos < 0:
            return endpos
        rawdata = self.rawdata
        self.__starttag_text = rawdata[i:endpos]

        # Now parse the data between i+1 and j into a tag and attrs
        attrs = []
        match = tagfind_tolerant.match(rawdata, i + 1)
        assert match, "unexpected call to parse_starttag()"
        k = match.end()
        self.lasttag = tag = match.group(1)
        while k < endpos:
            if rawdata[i:endpos].startswith("{"):
                m = attrfind_event_strict.match(rawdata, k)
                if not m:
                    break
                attrname = m.group(1)
                attrs.append(attrname)
                k = m.end()
            else:
                m = attrfind_tolerant.match(rawdata, k)
                if not m:
                    break
                attrname, rest, attrvalue = m.group(1, 2, 3)
                if not rest:
                    attrvalue = None
                elif attrvalue[:1] == "'" == attrvalue[-1:] or attrvalue[:1] == '"' == attrvalue[-1:]:
                    attrvalue = attrvalue[1:-1]
                if attrvalue:
                    attrvalue = self.unescape(attrvalue)
                attrs.append((attrname, attrvalue))
                k = m.end()

        end = rawdata[k:endpos].strip()
        if end not in (">", "/>", "}"):
            lineno, offset = self.getpos()
            if "\n" in self.__starttag_text:
                lineno = lineno + self.__starttag_text.count("\n")
                offset = len(self.__starttag_text) - self.__starttag_text.rfind("\n")
            else:
                offset = offset + len(self.__starttag_text)
            self.handle_data(rawdata[i:endpos])
            return endpos
        if end.endswith("}"):
            self.handle_eventtag(tag, attrs)
        elif tag.lower() not in self.END_TAGS:
            self.handle_startendtag(tag, attrs)
        else:
            self.handle_starttag(tag, attrs)
        return endpos

    # Internal -- check to see if we have a complete starttag; return end
    # or -1 if incomplete.
    def check_for_whole_start_tag(self, i):
        rawdata = self.rawdata
        m = locatestarttagend_tolerant.match(rawdata, i)
        if m:
            j = m.end()
            next = rawdata[j : j + 1]
            if next == ">" or next == "}":
                return j + 1
            if next == "/":
                if rawdata.startswith("/>", j):
                    return j + 2
                if rawdata.startswith("/", j):
                    # buffer boundary
                    return -1
                # else bogus input
                if j > i:
                    return j
                else:
                    return i + 1
            if next == "":
                # end of input
                return -1
            if next in ("abcdefghijklmnopqrstuvwxyz=/" "ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
                # end of input in or before attribute value, or we have the
                # '/' from a '/>' ending
                return -1
            if j > i:
                return j
            else:
                return i + 1
        raise AssertionError("we should not get here!")

    # Internal -- parse endtag, return end or -1 if incomplete
    def parse_endtag(self, i):
        rawdata = self.rawdata
        assert rawdata[i : i + 2] == "</", "unexpected call to parse_endtag"
        match = endendtag.search(rawdata, i + 1)  # >
        if not match:
            return -1
        gtpos = match.end()
        match = endtagfind.match(rawdata, i)  # </ + tag + >
        if not match:
            # find the name: w3.org/TR/html5/tokenization.html#tag-name-state
            namematch = tagfind_tolerant.match(rawdata, i + 2)
            if not namematch:
                # w3.org/TR/html5/tokenization.html#end-tag-open-state
                if rawdata[i : i + 3] == "</>":
                    return i + 3
                else:
                    return self.parse_bogus_comment(i)
            tagname = namematch.group(1)
            # consume and ignore other stuff between the name and the >
            # Note: this is not 100% correct, since we might have things like
            # </tag attr=">">, but looking for > after tha name should cover
            # most of the cases and is much simpler
            gtpos = rawdata.find(">", namematch.end())
            self.handle_endtag(tagname)
            return gtpos + 1

        elem = match.group(1)  # script or style
        self.handle_endtag(elem)
        return gtpos

    def handle_eventtag(self, tag, attrs):
        event = ["\x01{}".format(tag)]
        for arg in attrs:
            event.append(arg.strip('"'))
        self.tpword_body.append(
            TWdOpeEvent(
                event="\r\n".join(event),
                decorator=self.decorator,
                text_speed=self.text_speed,
                link_name=self.link_name,
                link=self.link,
                condition=self.condition,
            )
        )

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_starttag(self, tag, attrs):
        tag = LNSTag[tag.lower()]
        attrs = {k: v for k, v in attrs}
        d = {
            "decorator": self.decorator,
            "text_speed": self.text_speed,
            "link_name": self.link_name,
            "link": self.link,
            "condition": self.condition,
        }
        if tag == LNSTag.a:
            self.link = int(attrs.get("ID", 0))
            self.link_name = attrs.get("NAME", "")
        elif tag == LNSTag.br:
            d["break_type"] = 0
            self.tpword_body.append(TWdOpeReturn(**d))
        elif tag == LNSTag.clr:
            d["break_type"] = 4
            self.tpword_body.append(TWdOpeReturn(**d))
        elif tag == LNSTag.condition:
            self.condition = int(attrs.get("ID", 0))
        elif tag == LNSTag.div:
            d["align"] = AlignEnum[attrs.get("ALIGN", "LEFT")].value
            d["padleft"] = int(attrs.get("PADLEFT", 0))
            d["padright"] = int(attrs.get("PADRIGHT", 0))
            d["noheight"] = int(attrs.get("NOHEIGHT", 0))
            self.tpword_body.append(TWdOpeDiv(**d))
        elif tag == LNSTag.event:
            event = attrs.get("VALUE", "").split("\\r\\n")
            d["event"] = "\r\n".join(event)
            self.tpword_body.append(TWdOpeEvent(**d))
        elif tag == LNSTag.histchar:
            d["var_name"] = attrs.get("NAME", "")
            d["unk3"] = int(attrs.get("unk3", 0))
            self.tpword_body.append(TWdOpeHistChar(**d))
        elif tag == LNSTag.indent:
            self.tpword_body.append(TWdOpeIndent(**d))
        elif tag == LNSTag.img:
            if "ALIGN" in attrs:
                attrs["ALIGN"] = AlignEnum[attrs["ALIGN"]].value
            for k in attrs:
                d[k.lower()] = attrs[k]
            self.tpword_body.append(TWdImg(**d))
        elif tag == LNSTag.pg:
            d["break_type"] = 1
            self.tpword_body.append(TWdOpeReturn(**d))
        elif tag == LNSTag.ps:
            d["break_type"] = 3
            self.tpword_body.append(TWdOpeReturn(**d))
        elif tag == LNSTag.scenario:
            self.version = int(attrs.get("VER", 0))
        elif tag == LNSTag.style:
            self.decorator = int(attrs["ID"])
            ruby = attrs.get("RUBY")
            if ruby:
                self.ruby_text[self.decorator] = ruby
        elif tag == LNSTag.txspd:
            self.text_speed = int(attrs.get("TIME"), 50)
        elif tag == LNSTag.txspn:
            self.text_speed = 50
        elif tag == LNSTag.txspf:
            self.text_speed = 0
        elif tag == LNSTag.txsps:
            self.text_speed = 300
        elif tag == LNSTag.undent:
            self.tpword_body.append(TWdOpeUndent(**d))
        elif tag == LNSTag.var:
            if self.version and self.version < 102:
                # TODO for LNS ver < 102 we have to convert var name back into
                # a live parser
                logger.warning("Compiling script ver < 102 with VAR tags not fully supported")
            d["var_name"] = attrs.get("NAME", "")
            d["unk3"] = int(attrs.get("unk3", 0))
            self.tpword_body.append(TWdOpeVar(**d))
        else:
            logger.warning("Unexpected tag: {}".format(tag))

    def handle_endtag(self, tag):
        tag = LNSTag[tag.lower()]
        if tag == LNSTag.a:
            self.link = 0
            self.link_name = ""
        elif tag == LNSTag.style:
            self.decorator = 0

    def handle_data(self, data):
        # Handle text data
        for c in data:
            ch = TWdChar(
                ch=c,
                decorator=self.decorator,
                text_speed=self.text_speed,
                link_name=self.link_name,
                link=self.link,
                condition=self.condition,
            )
            self.tpword_body.append(ch)

    def unescape(self, s):
        for i, j in [('\\"', '"'), ("\\<", "<"), ("\\>", ">"), ("\\{", "{"), ("\\}", "}"), ("\\\\", "\\")]:
            s = s.replace(i, j)
        return s


class LNSTextBlock(BaseTranslatable):
    """Contiguous text block in a TpWord body.

    Args:
        text (str): line text string.
        start (int): TpWord body index of the first TWdChar in this line
        end (int): TpWord body index of the first TWdGlyph following this line.
            If `end` is None, it will be set to ``start + len(text)``.
        name_label (str): associated namelabel event (speaker name).

    Text blocks are defined as continuous runs of `TWdChar` and `<BR>` line-breaks
    (`TWdOpeReturn` with `break_type == BreakType.LINE`).

    When working with `LNSTextLine` objects, the ``text`` attribute can be manipulated freely.
    The read-only ``digest``, ``start`` and ``end`` attributes will always remain tied to the original
    TpWord body, to ensure that modified (i.e. translated) lines are inserted in the correct position,
    even if the translated line differs in length from the original. Newlines in ``text`` will
    be converted to `<BR>` line-breaks when inserting a text block into a `TpWord` body.

    Note:
        Line equality (``__eq__``) is tested based on matching ``start``, ``end``, ``digest`` attributes.
        To test string equality between, compare the ``text`` attributes.
    """

    def __init__(self, text, start, end=None, name_label=None):
        super().__init__(text)
        self.name_label = name_label
        self._start = start
        if self._start < 0:
            raise ValueError("LNSTextLine start must be >= 0")
        if end is None:
            self._end = start + len(text)
        else:
            self._end = end
        if self._end <= start:
            raise ValueError("LNSTextLine end must be > start")

    @property
    def start(self):
        return self._start

    @property
    def end(self):
        return self._end

    def __hash__(self):
        return hash((self.start, self.end, self.digest))

    def __lt__(self, other):
        return self.start < other.start and self.end < other.end

    def overlaps(self, other):
        return (self.start >= other.start and self.start < other.end) or (
            self.end > other.start and self.end <= other.end
        )


class LNSText:
    """Convenience container for accessing text blocks in a TpWord body."""

    def __init__(self, strict=True):
        self._blocks = []
        self.strict = strict

    def __len__(self):
        return len(self._blocks)

    def __iter__(self):
        return iter(self._blocks)

    def __reversed__(self):
        return reversed(self._blocks)

    def __getitem__(self, key):
        if not self._blocks:
            raise IndexError
        if key < 0:
            key %= len(self._blocks)
        return self._blocks[key]

    def __eq__(self, other):
        if len(self) != len(other):
            return False
        for i, line in enumerate(self._blocks):
            if line != other[i]:
                return False
        return True

    def add(self, line):
        """Add the specified line to this container."""
        index = bisect(self._blocks, line)
        if self.strict:
            for i in (index, index + 1):
                if i < len(self) and self._blocks[i].overlaps(line):
                    raise BadLnsError("Invalid overlapping LNS lines")
        self._blocks.insert(index, line)

    @classmethod
    def from_tpword(cls, tpword):
        """Return blocks object for the specified TpWord block.

        Args:
            tpword (:class:`TpWord`): TpWord block to parse
        """
        blocks = LNSText()
        cur_block = []
        cur_name = None
        start = 0
        for i, w in enumerate(tpword.body):
            block_break = True
            if w.type == TWdType.TWdChar:
                if not cur_block:
                    start = i
                cur_block.append(str(w.ch))
                block_break = False
            elif w.type == TWdType.TWdOpeReturn:
                if cur_block and w.break_type == BreakType.LINE:
                    cur_block.append("\n")
                    block_break = False
            elif w.type == TWdType.TWdOpeEvent:
                if w.name == "NAMELABEL":
                    if w.is_system:
                        cur_name = None
                    else:
                        cur_name = w.args[0]

            if block_break:
                if cur_block:
                    # certain games (AGLS) use repeated blank lines to manually
                    # create blank message box screens, we can strip them here
                    # (they will still be preserved in-game)
                    text = "".join(cur_block).rstrip("\n")
                    blocks.add(LNSTextBlock(text, start, name_label=cur_name))
                cur_block.clear()
        return blocks

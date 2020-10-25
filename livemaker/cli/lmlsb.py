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
"""LiveMaker LSB script CLI tool."""

import hashlib
import re
import shutil
import sys
import csv
from pathlib import Path

import click
import numpy

from lxml import etree

from livemaker.lsb import LMScript
from livemaker.lsb.command import BaseComponentCommand, Calc, CommandType, Jump, LabelReference
from livemaker.lsb.core import OpeData, OpeDataType, OpeFuncType, Param, ParamType
from livemaker.lsb.menu import LPMSelectionChoice
from livemaker.lsb.novel import LNSDecompiler, LNSCompiler, TWdChar, TWdOpeReturn
from livemaker.project import PylmProject
from livemaker.lsb.translate import make_identifier, TextBlockIdentifier, TextMenuIdentifier
from livemaker.exceptions import BadLsbError, BadTextIdentifierError, LiveMakerException

from .cli import _version, __version__


@click.group()
@click.version_option(version=__version__, message=_version)
def lmlsb():
    """Command-line tool for manipulating LSB scripts."""
    pass


@lmlsb.command()
@click.argument("input_file", metavar="file", required=True, type=click.Path(exists=True, dir_okay=False))
def probe(input_file):
    """Output information about the specified LSB file in human-readable form.

    Novel script scenario character and line count are estimates. Depending
    on how a script was originally created, actual char/line counts may vary.

    """
    print(input_file)
    with open(input_file, "rb") as f:
        try:
            lm = LMScript.from_file(f)
        except BadLsbError as e:
            sys.exit("Could not read file: {}".format(e))
    if lm._parsed_from == "lsc":
        print("LiveMaker LSC script file:")
    elif lm._parsed_from == "lsc-xml":
        print("LiveMaker XML LSC script file:")
    elif lm._parsed_from == "lsb":
        print("LiveMaker compiled LSB script file:")
    else:
        print("LiveMaker script file:")
    print("  Version: {} (LiveMaker{})".format(lm.version, lm.lm_version))
    print("  Total commands: {}".format(len(lm)))
    cmd_types = set()
    for cmd in lm.commands:
        cmd_types.add(cmd.type)
    print("    Command types: {}".format(", ".join([x.name for x in sorted(cmd_types)])))
    scenarios = lm.text_scenarios()
    print("  Total text scenarios: {}".format(len(scenarios)))
    for index, name, scenario in scenarios:
        if not name:
            name = "Unlabeled scenario"
        print("    {}".format(name))
        tpwd_types = set()
        char_count = 0
        line_count = 0
        for wd in scenario.body:
            tpwd_types.add(wd.type)
            if isinstance(wd, TWdChar):
                char_count += 1
            elif isinstance(wd, TWdOpeReturn):
                line_count += 1
        print("      LiveNovel scenario version: {}".format(scenario.version))
        print("      TpWd types: {}".format(", ".join([x.name for x in sorted(tpwd_types)])))
        print("      Approx. character count: {}".format(char_count))
        if char_count:
            # don't count line breaks in event-only scenarios
            print("      Approx. line count: {}".format(line_count))


@lmlsb.command()
@click.argument("input_file", metavar="file", required=True, nargs=-1, type=click.Path(exists=True))
def validate(input_file):
    """Verify that the specified LSB file(s) can be processed.

    Validation is done by disassembling an input file, reassembling it,
    and then comparing the SHA256 digests of the original and reassembled
    versions of the file.

    If a file contains text scenarios, a test will also be done to verify that
    the scenarios can be decompiled, recompiled, and then reinserted into the
    lsb file.

    """
    for path in input_file:
        print(path)
        with open(path, "rb") as f:
            data = f.read()
        try:
            lsb = LMScript.from_lsb(data)
            orig = hashlib.sha256(data).hexdigest()
        except BadLsbError as e:
            print("  Failed to parse file: {}".format(e))
            continue
        try:
            built_data = lsb.to_lsb()
            reassembled = hashlib.sha256(built_data).hexdigest()
        except BadLsbError as e:
            print("  Failed to reassemble file: {}".format(e))
            continue
        print("  Orig: {} ({} bytes)".format(orig, len(data)))
        print("   New: {} ({} bytes)".format(reassembled, len(built_data)))
        if orig == reassembled:
            print("  SHA256 digest validation passed")
        if orig != reassembled:
            print("  SHA256 digest validation failed")
        for line, name, scenario in lsb.text_scenarios(run_order=False):
            print("  {}".format(name))
            orig_bytes = scenario._struct().build(scenario)
            dec = LNSDecompiler()
            script = dec.decompile(scenario)
            cc = LNSCompiler()
            new_body = cc.compile(script)
            scenario.replace_body(new_body, ruby_text=cc.ruby_text)
            new_bytes = scenario._struct().build(scenario)
            if new_bytes == orig_bytes:
                print("  script passed")
            else:
                print("  script mismatch, {} {}".format(len(orig_bytes), len(new_bytes)))


@lmlsb.command()
@click.option(
    "-m", "--mode", type=click.Choice(["text", "xml", "lines"]), default="text", help="Output mode (defaults to text)"
)
@click.option(
    "-e",
    "--encoding",
    type=click.Choice(["cp932", "utf-8"]),
    default="utf-8",
    help="Output text encoding (defaults to utf-8).",
)
@click.option(
    "-o",
    "--output-file",
    type=click.Path(dir_okay=False),
    help="Output file. If unspecified, output will be dumped to stdout.",
)
@click.argument("input_file", required=True, nargs=-1, type=click.Path(exists=True, dir_okay="False"))
def dump(mode, encoding, output_file, input_file):
    """Dump the contents of the specified LSB file(s) to stdout in a human-readable format.

    For text mode, the full LSB will be output as human-readable text.

    For xml mode, the full LSB file will be output as an XML document.

    For lines mode, only text lines will be output.
    """
    if output_file:
        outf = open(output_file, mode="w", encoding=encoding)
    else:
        outf = sys.stdout

    pylm = None
    skip_pylm = False

    for path in input_file:
        try:
            if skip_pylm:
                call_name = None
            elif not pylm:
                try:
                    pylm = PylmProject(path)
                    call_name = pylm.call_name(path)
                except LiveMakerException:
                    call_name = None
                    skip_pylm = True
            with open(path, "rb") as f:
                lsb = LMScript.from_file(f, call_name=call_name, pylm=pylm)
            if pylm:
                pylm.update_labels(lsb)
        except BadLsbError as e:
            sys.stderr.write("  Failed to parse file: {}".format(e))
            continue

        if mode == "xml":
            root = lsb.to_xml()
            print(
                etree.tostring(root, encoding=encoding, pretty_print=True, xml_declaration=True).decode(encoding),
                file=outf,
            )
        elif mode == "lines":
            lsb_path = Path(path)
            for line, name, scenario in lsb.text_scenarios():
                if name:
                    name = "{}-{}.lns".format(lsb_path.stem, name)
                if not name:
                    name = "{}-line{}.lns".format(lsb_path.stem, line)
                print(name, file=outf)
                print("------", file=outf)
                for block in scenario.get_text_blocks():
                    for line in block.text.splitlines():
                        print(line, file=outf)
        else:
            for c in lsb.commands:
                if c.Mute:
                    mute = ";"
                else:
                    mute = ""
                s = ["{}{:4}: {}".format(mute, c.LineNo, "    " * c.Indent)]
                s.append(str(c).replace("\r", "\\r").replace("\n", "\\n"))
                ref = c.get("Page")
                if ref and isinstance(ref, LabelReference):
                    if ref.Page.endswith("lsb") and pylm:
                        # resolve lsb refs
                        line_no, name = pylm.resolve_label(ref)
                        if line_no is not None:
                            s.append(f" (Label {line_no}: {name})")
                print("".join(s), file=outf)
                if c.type == CommandType.TextIns:
                    dec = LNSDecompiler()
                    print(dec.decompile(c.get("Text")), file=outf)


def _escape_scenario_name(name):
    """Replace invalid Windows path characters with underscore."""
    return re.sub(r'[\/:*?"<>|]+', "_", name)


@lmlsb.command()
@click.option(
    "-e",
    "--encoding",
    type=click.Choice(["cp932", "utf-8"]),
    default="utf-8",
    help="Output text encoding (defaults to utf-8).",
)
@click.option(
    "-o",
    "--output-dir",
    type=click.Path(file_okay=False),
    help="Output directory. Defaults to the current working directory if not specified."
    " If directory does not exist it will be created.",
)
@click.argument("input_file", required=True, nargs=-1, type=click.Path(exists=True, dir_okay=False))
def extract(encoding, output_dir, input_file):
    """Extract decompiled LiveNovel scripts from the specified input file(s).

    By default, extracted scripts will be encoded as utf-8, but if you intend
    to patch a script back into an LSB, you will still be limited to cp932
    characters only.

    Output files will be named <LSB name>-<scenario name>.lns

    """
    if output_dir:
        output_dir = Path(output_dir)
        if not output_dir.exists():
            output_dir.mkdir(parents=True)
    else:
        output_dir = Path.cwd()
    for path in input_file:
        print("Extracting scripts from {}".format(path))
        lsb_path = Path(path)
        lsb = LMScript.from_file(path)
        lsb_ref_filename = "{}.lsbref".format(lsb_path.stem)
        with open(output_dir.joinpath(lsb_ref_filename), "w", encoding=encoding) as lsb_ref_file:
            for line, name, scenario in lsb.text_scenarios():
                if name:
                    name = "{}-{}.lns".format(lsb_path.stem, _escape_scenario_name(name))
                if not name:
                    name = "{}-line{}.lns".format(lsb_path.stem, line)
                output_path = output_dir.joinpath(name)
                dec = LNSDecompiler()
                with open(output_path, "w", encoding=encoding) as f:
                    f.write(dec.decompile(scenario))
                print("  wrote {}".format(output_path))
                lsb_ref_file.write("{}:{}\n".format(name, line))


@lmlsb.command()
@click.option(
    "-e",
    "--encoding",
    type=click.Choice(["cp932", "utf-8"]),
    default="utf-8",
    help="The text encoding of script_file (defaults to utf-8).",
)
@click.argument("lsb_file", required=True, type=click.Path(exists=True, dir_okay=False))
@click.argument("script_file", required=True, type=click.Path(exists=True, dir_okay=False))
# TODO: make this optional and parse label/line number from script filename
@click.argument("line_number", required=True, type=int)
@click.option("--no-backup", is_flag=True, default=False, help="Do not generate backup of original archive file(s).")
def insert(encoding, lsb_file, script_file, line_number, no_backup):
    """Compile specified LNS script and insert it into the specified LSB file.

    The LSB command at line_number must be a TextIns command. The existing text
    block of the specified TextIns command will be replaced with the new one from
    script_file.

    script_file should be an LNS script which was initially generated by lmlsb extract.

    The original LSB file will be backed up to <lsb_file>.bak unless the
    --no-backup option is specified.

    """
    insert_lns(encoding, lsb_file, script_file, line_number, no_backup)


@lmlsb.command()
@click.option(
    "-e",
    "--encoding",
    type=click.Choice(["cp932", "utf-8"]),
    default="utf-8",
    help="The text encoding of script_file (defaults to utf-8).",
)
@click.argument("lsb_file", required=True, type=click.Path(exists=True, dir_okay=False))
@click.argument("script_dir", type=click.Path(file_okay=False))
@click.option("--no-backup", is_flag=True, default=False, help="Do not generate backup of original archive file(s).")
@click.option(
    "--ignore-missing", is_flag=True, default=False, help="Continue insert in case of missing script file(s)."
)
def batchinsert(encoding, lsb_file, script_dir, no_backup, ignore_missing):
    """Compile specified LNS script directory and insert it into the specified LSB file according to
    the Reference file.

    The Reference file must be inside script_dir.

    script_dir should be an LNS script directory which was initially generated by lmlsb extract.

    The original LSB file will be backed up to <lsb_file>.bak unless the
    --no-backup option is specified.

    If a file from .lsbref is missing, insertation is stopped, unless the
    --ignore-missing option is specified
    """
    script_dir = Path(script_dir)
    if not script_dir.exists():
        print("Input directory does not exist")
        return
    if not no_backup:
        print("Backing up original LSB.")
        shutil.copyfile(str(lsb_file), "{}.bak".format(str(lsb_file)))

    with open(lsb_file, "rb") as f:
        try:
            lsb = LMScript.from_file(f)
        except LiveMakerException as e:
            sys.exit("Could not open LSB file: {}".format(e))

    lsb_path = Path(lsb_file)
    lsb_ref_filename = "{}.lsbref".format(lsb_path.stem)
    with open(script_dir.joinpath(lsb_ref_filename), "r", encoding=encoding) as lsb_ref_file:
        while True:
            ln = lsb_ref_file.readline()
            if ln == "":
                break
            lnsplt = ln.split(":")
            script_file = script_dir.joinpath(lnsplt[0])
            line_number = int(lnsplt[1])

            if not Path(script_file).exists():
                if ignore_missing:
                    print("Warning: script file {} is missing, skipped.".format(script_file))
                    continue
                else:
                    sys.exit("Script file is missing: {}".format(script_file))

            with open(script_file, "rb") as f:
                script = f.read().decode(encoding)
            try:
                cc = LNSCompiler()
                new_body = cc.compile(script)
            except LiveMakerException as e:
                sys.exit("Could not compile script file: {}".format(e))

            for index, name, scenario in lsb.text_scenarios():
                if index == line_number:
                    print("Scenario {} at line {} will be replaced.".format(name, index))
                    scenario.replace_body(new_body, ruby_text=cc.ruby_text)
                    break

    try:
        new_lsb_data = lsb.to_lsb()
        with open(lsb_file, "wb") as f:
            f.write(new_lsb_data)
        print("Wrote new LSB.")
    except LiveMakerException as e:
        sys.exit("Could not generate new LSB file: {}".format(e))


# Known property data types
EDITABLE_PROPERTY_TYPES = {
    # PR_NONE = 0x00
    # PR_NAME = 0x01
    # PR_PARENT = 0x02
    # PR_SOURCE = 0x03
    # PR_LEFT = 0x04
    # PR_TOP = 0x05
    # PR_WIDTH = 0x06
    # PR_HEIGHT = 0x07
    # PR_ZOOMX = 0x08
    # PR_COLOR = 0x09
    # PR_BORDERWIDTH = 0x0a
    # PR_BORDERCOLOR = 0x0b
    # PR_ALPHA = 0x0c
    "PR_PRIORITY": ParamType.Int,
    # PR_OFFSETX = 0x0e
    # PR_OFFSETY = 0x0f
    # PR_FONTNAME = 0x10
    "PR_FONTHEIGHT": ParamType.Int,
    # PR_FONTSTYLE = 0x12
    "PR_LINESPACE": ParamType.Int,
    "PR_FONTCOLOR": ParamType.Int,
    "PR_FONTLINKCOLOR": ParamType.Int,
    "PR_FONTBORDERCOLOR": ParamType.Int,
    "PR_FONTHOVERCOLOR": ParamType.Int,
    # PR_FONTHOVERSTYLE = 0x18
    # PR_HOVERCOLOR = 0x19
    "PR_ANTIALIAS": ParamType.Flag,
    # PR_DELAY = 0x1b
    "PR_PAUSED": ParamType.Flag,
    # PR_VOLUME = 0x1d
    # PR_REPEAT = 0x1e
    # PR_BALANCE = 0x1f
    # PR_ANGLE = 0x20
    # PR_ONPLAYING = 0x21
    # PR_ONNOTIFY = 0x22
    # PR_ONMOUSEMOVE = 0x23
    # PR_ONMOUSEOUT = 0x24
    # PR_ONLBTNDOWN = 0x25
    # PR_ONLBTNUP = 0x26
    # PR_ONRBTNDOWN = 0x27
    # PR_ONRBTNUP = 0x28
    # PR_ONWHEELDOWN = 0x29
    # PR_ONWHEELUP = 0x2a
    # PR_BRIGHTNESS = 0x2b
    # PR_ONPLAYEND = 0x2c
    # PR_INDEX = 0x2d
    # PR_COUNT = 0x2e
    # PR_ONLINK = 0x2f
    "PR_VISIBLE": ParamType.Flag,
    # PR_COLCOUNT = 0x31
    # PR_ROWCOUNT = 0x32
    # PR_TEXT = 0x33
    # PR_MARGINX = 0x34
    # PR_MARGINY = 0x35
    # PR_HALIGN = 0x36
    # PR_BORDERSOURCETL = 0x37
    # PR_BORDERSOURCETC = 0x38
    # PR_BORDERSOURCETR = 0x39
    # PR_BORDERSOURCECL = 0x3a
    # PR_BORDERSOURCECC = 0x3b
    # PR_BORDERSOURCECR = 0x3c
    # PR_BORDERSOURCEBL = 0x3d
    # PR_BORDERSOURCEBC = 0x3e
    # PR_BORDERSOURCEBR = 0x3f
    # PR_BORDERHALIGNT = 0x40
    # PR_BORDERHALIGNC = 0x41
    # PR_BORDERHALIGNB = 0x42
    # PR_BORDERVALIGNL = 0x43
    # PR_BORDERVALIGNC = 0x44
    # PR_BORDERVALIGNR = 0x45
    # PR_SCROLLSOURCE = 0x46
    # PR_CHECKSOURCE = 0x47
    # PR_AUTOSCRAP = 0x48
    # PR_ONSELECT = 0x49
    # PR_RCLICKSCRAP = 0x4a
    # PR_ONOPENING = 0x4b
    # PR_ONOPENED = 0x4c
    # PR_ONCLOSING = 0x4d
    # PR_ONCLOSED = 0x4e
    # PR_CARETX = 0x4f
    # PR_CARETY = 0x50
    "PR_IGNOREMOUSE": ParamType.Int,
    "PR_TEXTPAUSED": ParamType.Flag,
    # PR_TEXTDELAY = 0x53
    # PR_HOVERSOURCE = 0x54
    # PR_PRESSEDSOURCE = 0x55
    # PR_GROUPINDEX = 0x56
    # PR_ALLOWALLUP = 0x57
    # PR_SELECTED = 0x58
    # PR_CAPTUREMASK = 0x59
    # PR_POWER = 0x5a
    # PR_ORIGWIDTH = 0x5b
    # PR_ORIGHEIGHT = 0x5c
    # PR_APPEARX = 0x5d
    # PR_APPEARY = 0x5e
    # PR_PARTMOTION = 0x5f
    # PR_PARAM = 0x60
    # PR_PARAM2 = 0x61
    # PR_TOPINDEX = 0x62
    # PR_READONLY = 0x63
    # PR_CURSOR = 0x64
    # PR_POSZOOMED = 0x65
    # PR_ONPLAYSTART = 0x66
    # PR_PARAM3 = 0x67
    # PR_ONMOUSEIN = 0x68
    # PR_ONMAPIN = 0x69
    # PR_ONMAPOUT = 0x6a
    # PR_MAPSOURCE = 0x6b
    # PR_AMP = 0x6c
    # PR_WAVELEN = 0x6d
    # PR_SCROLLX = 0x6e
    # PR_SCROLLY = 0x6f
    # PR_FLIPH = 0x70
    # PR_FLIPV = 0x71
    # PR_ONIDLE = 0x72
    # PR_DISTANCEX = 0x73
    # PR_DISTANCEY = 0x74
    # PR_CLIPLEFT = 0x75
    # PR_CLIPTOP = 0x76
    # PR_CLIPWIDTH = 0x77
    # PR_CLIPHEIGHT = 0x78
    # PR_DURATION = 0x79
    # PR_THUMBSOURCE = 0x7a
    # PR_BUTTONSOURCE = 0x7b
    # PR_MIN = 0x7c
    # PR_MAX = 0x7d
    # PR_VALUE = 0x7e
    # PR_ORIENTATION = 0x7f
    # PR_SMALLCHANGE = 0x80
    # PR_LARGECHANGE = 0x81
    # PR_MAPTEXT = 0x82
    # PR_GLYPHWIDTH = 0x83
    # PR_GLYPHHEIGHT = 0x84
    # PR_ZOOMY = 0x85
    # PR_CLICKEDSOURCE = 0x86
    # PR_ANIPAUSED = 0x87
    # PR_ONHOLD = 0x88
    # PR_ONRELEASE = 0x89
    # PR_REVERSE = 0x8a
    # PR_PLAYING = 0x8b
    # PR_REWINDONLOAD = 0x8c
    # PR_COMPOTYPE = 0x8d
    "PR_FONTSHADOWCOLOR": ParamType.Int,
    "PR_FONTBORDER": ParamType.Int,
    "PR_FONTSHADOW": ParamType.Int,
    # PR_ONKEYDOWN = 0x91
    # PR_ONKEYUP = 0x92
    # PR_ONKEYREPEAT = 0x93
    "PR_HANDLEKEY": ParamType.Flag,
    # PR_ONFOCUSIN = 0x95
    # PR_ONFOCUSOUT = 0x96
    # PR_OVERLAY = 0x97
    # PR_TAG = 0x98
    "PR_CAPTURELINK": ParamType.Flag,
    # PR_FONTHOVERBORDER = 0x9a
    # PR_FONTHOVERBORDERCOLOR = 0x9b
    # PR_FONTHOVERSHADOW = 0x9c
    # PR_FONTHOVERSHADOWCOLOR = 0x9d
    # PR_BARSIZE = 0x9e
    # PR_MUTEONLOAD = 0x9f
    # PR_PLUSX = 0xa0
    # PR_PLUSY = 0xa1
    # PR_CARETHEIGHT = 0xa2
    # PR_REPEATPOS = 0xa3
    # PR_BLURSPAN = 0xa4
    # PR_BLURDELAY = 0xa5
    "PR_FONTCHANGEABLED": ParamType.Flag,
    # PR_IMEMODE = 0xa7
    # PR_FLOATANGLE = 0xa8
    # PR_FLOATZOOMX = 0xa9
    # PR_FLOATZOOMY = 0xaa
    # PR_CAPMASKLEVEL = 0xab
    # PR_PADDINGLEFT = 0xac
    # PR_PADDING_RIGHT = 0xad
}


def _check_string_literal(value):
    if value.startswith('"'):
        value = value[1:]
    else:
        print(
            'Warning: String literals should be entered as double quoted (") strings, '
            'assuming you meant to enter "{}"'.format(value)
        )
    if value.endswith('"'):
        value = value[:-1]
    else:
        print(
            'Warning: String literals should be entered as double quoted (") strings, '
            'assuming you meant to enter "{}"'.format(value)
        )
    return value


def _edit_parser_op(op, prompt="Operand"):
    if op.type == ParamType.Str:
        orig = '"{}"'.format(op.value)
    else:
        orig = op.value
    value = click.prompt(prompt, default=orig)
    if value != orig:
        if op.type == ParamType.Str:
            value = _check_string_literal(value)
        elif op.type in (ParamType.Flag, ParamType.Int):
            try:
                value = int(value)
            except ValueError:
                print("Expected an integer value, skipping field")
                return
        elif op.type == ParamType.Float:
            try:
                value = float(value)
            except ValueError:
                print("Expected a floating point value, skipping field")
                return
        elif op.type == ParamType.Var and value.startswith('"'):
            print('Expected a variable name, var names cannot start with ", skipping field')
            return
        op.value = value


def _edit_delimited_string_op(str_op, sep_op, prompt="String"):
    """Edit delimited string str_op (delimited by sep_op)."""
    if str_op.type != ParamType.Str or str_op.type != ParamType.Str:
        print("Expected a delimited string and separator, skipping field.")
        return
    new_strs = []
    sep = sep_op.value
    for i, s in enumerate(str_op.value.split(sep)):
        while True:
            value = click.prompt("{} {}".format(prompt, i), default='"{}"'.format(s))
            if sep in value:
                print('  Entry strings cannot contain the delimiter string ("{}")')
            else:
                break
        new_strs.append(_check_string_literal(value))
    str_op.value = sep.join(new_strs)
    value = click.prompt("{} separator".format(prompt), default='"{}"'.format(sep))
    sep_op.value = _check_string_literal(value)


def _edit_parser(parser):
    """Edit fields in a TLiveParser."""
    # map ____<arg> variables to the appropriate entry index for this parser
    print("  {}".format(parser))
    entry_index = {}
    for i, entry in enumerate(parser.entries):
        if entry.type == OpeDataType.To and entry.name.startswith("____"):
            if len(entry.operands) != 1:
                print("Got unexpected OpeDataType.To entry")
                continue
            entry_index[entry.name] = i
        elif entry.type == OpeDataType.Func:
            if entry.func == OpeFuncType.AddArray:
                # Format should be AddArray(<array_variable>, <value>)
                if len(entry.operands) != 2:
                    print("Skipping complex AddArray entry")
                    continue
                array_var_op = entry.operands[0]
                if array_var_op.type != ParamType.Var:
                    print("AddArray operand 0 is not a variable name: {}".format(entry))
                    continue
                value_entry_index = entry_index.get(entry.operands[1].value)
                if value_entry_index is None:
                    print("AddArray operand 1 does not point to a valid parser ____<arg> entry: {}".format(entry))
                    continue
                value_entry_op = parser.entries[value_entry_index].operands[0]
                _edit_parser_op(array_var_op, "  Array variable")
                _edit_parser_op(value_entry_op, "  Array entry")
            elif entry.func == OpeFuncType.StringToArray:
                # Format should be StringToArray(<delimited_string>,
                #   <array_variable>, <separator>)
                # where array entries are delimited by <separator>.
                #
                # i.e. StringToArray("foo,bar", my_array, ",") sets
                # my_array = ["foo", "bar"]
                #
                # NOTE: we allow editing of array entry strings for translation
                # purposes, but do not allow adding or removing entire entries
                # since modifying the array length would most likely break LM
                # core engine scripts.
                if len(entry.operands) != 3 or (
                    entry.operands[0].type != ParamType.Str
                    or entry.operands[1].type != ParamType.Var
                    or entry.operands[2].type != ParamType.Var
                ):
                    print("Skipping unexpected StringToArray entry")
                    continue
                sep_entry_index = entry_index.get(entry.operands[2].value)
                if sep_entry_index is None:
                    print("StringToArray operand 2 does not point to a valid parser ____<arg> entry: {}".format(entry))
                    continue
                sep_entry_op = parser.entries[sep_entry_index].operands[0]
                _edit_parser_op(entry.operands[1], "  Array variable")
                _edit_delimited_string_op(entry.operands[0], sep_entry_op, "  Array entry")
            else:
                print("Skipping uneditable parser func type: {}".format(entry))
        elif entry.type == OpeDataType.To:
            if len(entry.operands) > 1:
                print("Skipping complex assignment")
                continue
            value = click.prompt("  Destination variable", entry.name)
            if value != entry.name:
                entry.name = value
            _edit_parser_op(entry.operands[0], "  Value")
        elif entry.type in (
            OpeDataType.Equal,
            OpeDataType.Big,
            OpeDataType.Small,
            OpeDataType.EBig,
            OpeDataType.ESmall,
            OpeDataType.NEqual,
        ):
            # boolean comparison
            lhs_op = entry.operands[0]
            if lhs_op.type == ParamType.Var:
                if lhs_op.value.startswith("____"):
                    index = entry_index.get(lhs_op.value)
                    if index is None:
                        print("Comparison operand 0 does not point to a valid parser ____<arg> entry")
                        continue
                    lhs_op = parser.entries[index].operands[0]
            _edit_parser_op(lhs_op, "  Left hand side")
            rhs_op = entry.operands[1]
            if rhs_op.type == ParamType.Var:
                if rhs_op.value.startswith("____"):
                    index = entry_index.get(rhs_op.value)
                    if index is None:
                        print("Comparison operand 1 does not point to a valid parser ____<arg> entry")
                        continue
                    rhs_op = parser.entries[index].operands[0]
            _edit_parser_op(rhs_op, "  Right hand side")
        else:
            print("Skipping uneditable parser entry: {}".format(entry))


def _edit_calc(cmd):
    """Edit a Calc command.

    Note:
        Only a limited set of OpeFuncType calc types can be edited.

    """
    parser = cmd.get("Calc")
    if not parser:
        print("Skipping empty Calc() command.")
        return
    print()
    print("Editing Calc expression")
    _edit_parser(parser)


def _edit_component(cmd):
    """Edit a BaseComponent (or subclass) command."""
    print()
    print("Enter new value for each field (or keep existing value)")
    for key in cmd._component_keys:
        parser = cmd[key]
        # TODO: editing complex fields and adding values for empty fields will
        # require full LiveParser expression parsing, for now we can only edit
        # simple scalar values.
        if (
            len(parser.entries) > 1
            or (len(parser.entries) == 1 and parser.entries[0].type != OpeDataType.To)
            or (len(parser.entries) == 0 and key not in EDITABLE_PROPERTY_TYPES)
        ):
            print("{} [{}]: <skipping uneditable field>".format(key, parser))
            continue
        if parser.entries:
            e = parser.entries[0]
            op = e.operands[-1]
            if op:
                value = click.prompt(key, default=op.value)
                if value != op.value:
                    if op.type == ParamType.Int or op.type == ParamType.Flag:
                        op.value = int(value)
                    elif op.type == ParamType.Float:
                        op.value = numpy.longdouble(value)
                    else:
                        op.value = value
        else:
            value = click.prompt(key, default="")
            if value:
                param_type = EDITABLE_PROPERTY_TYPES[key]
                try:
                    if param_type == ParamType.Int or param_type == ParamType.Flag:
                        value = int(value)
                    elif param_type == ParamType.Float:
                        value = numpy.longdouble(value)
                    op = Param(value, param_type)
                    e = OpeData(type=OpeDataType.To, name="____arg", operands=[op])
                    parser.entries.append(e)
                except ValueError:
                    print("Invalid datatype for {}, skipping.".format(key))


def _edit_jump(cmd):
    """Edit a jump command."""
    page = cmd.get("Page")
    if not page:
        print("Skipping Jump() command with no jump target")
    print()
    value = click.prompt("Jump target page", page.Page)
    if value != page.Page:
        page.Page = value
    value = click.prompt("Jump target label ID", page.Label)
    if value != page.Label:
        page.Label = value
    parser = cmd.get("Calc")
    if not parser:
        # conditional calc optional
        return
    print("Editing jump condition expression")
    _edit_parser(parser)


@lmlsb.command()
@click.argument("lsb_file", required=True, type=click.Path(exists=True, dir_okay=False))
@click.argument("line_number", required=True, type=int)
def edit(lsb_file, line_number):
    """Edit the specified command within an LSB file.

    Only specific command types and specific fields can be edited.

    The original LSB file will be backed up to <lsb_file>.bak

    WARNING: This command should only be used by advanced users familiar with the LiveMaker engine.
    Improper use of this command may cause undefined behavior (or a complete crash)
    in the LiveMaker engine during runtime.

    Note: Setting empty fields to improper data types may cause
    undefined behavior in the LiveMaker engine. When editing a field,
    the data type of the new value is assumed to be the same as the
    original data type.

    """
    with open(lsb_file, "rb") as f:
        try:
            lsb = LMScript.from_file(f)
        except LiveMakerException as e:
            sys.exit("Could not open LSB file: {}".format(e))

    cmd = None
    for c in lsb.commands:
        if c.LineNo == line_number:
            cmd = c
            break
    else:
        sys.exit("Command {} does not exist in the specified LSB".format(line_number))

    print("{}: {}".format(line_number, str(cmd).replace("\r", "\\r").replace("\n", "\\n")))
    if isinstance(cmd, BaseComponentCommand):
        _edit_component(cmd)
    elif isinstance(cmd, Calc):
        _edit_calc(cmd)
    elif isinstance(cmd, Jump):
        _edit_jump(cmd)
    else:
        sys.exit("Cannot edit {} commands.".format(cmd.type.name))

    print("Backing up original LSB.")
    shutil.copyfile(str(lsb_file), "{}.bak".format(str(lsb_file)))
    try:
        new_lsb_data = lsb.to_lsb()
        with open(lsb_file, "wb") as f:
            f.write(new_lsb_data)
        print("Wrote new LSB.")
    except LiveMakerException as e:
        sys.exit("Could not generate new LSB file: {}".format(e))


def insert_lns(encoding, lsb_file, script_file, line_number, no_backup):
    """Compile specified LNS script and insert it into the specified LSB file.

    The LSB command at line_number must be a TextIns command. The existing text
    block of the specified TextIns command will be replaced with the new one from
    script_file.

    script_file should be an LNS script which was initially generated by lmlsb extract.

    The original LSB file will be backed up to <lsb_file>.bak unless the
    --no-backup option is specified.

    """
    # TODO: modify the function so that it doesn't write new file for each script during batch insert
    with open(script_file, "rb") as f:
        script = f.read().decode(encoding)
    try:
        cc = LNSCompiler()
        new_body = cc.compile(script)
    except LiveMakerException as e:
        sys.exit("Could not compile script file: {}".format(e))

    with open(lsb_file, "rb") as f:
        try:
            lsb = LMScript.from_file(f)
        except LiveMakerException as e:
            sys.exit("Could not open LSB file: {}".format(e))

    for index, name, scenario in lsb.text_scenarios():
        if index == line_number:
            print("Scenario {} at line {} will be replaced.".format(name, index))
            scenario.replace_body(new_body, ruby_text=cc.ruby_text)
            break
    else:
        sys.exit("No matching TextIns command in the specified LSB.")

    if not no_backup:
        print("Backing up original LSB.")
        shutil.copyfile(str(lsb_file), "{}.bak".format(str(lsb_file)))
    try:
        new_lsb_data = lsb.to_lsb()
        with open(lsb_file, "wb") as f:
            f.write(new_lsb_data)
        print("Wrote new LSB.")
    except LiveMakerException as e:
        sys.exit("Could not generate new LSB file: {}".format(e))


CSV_HEADER = ["ID", "Label", "Context", "Original text", "Translated text"]


@lmlsb.command()
@click.argument("lsb_file", required=True, type=click.Path(exists=True, dir_okay="False"))
@click.argument("csv_file", required=True, type=click.Path(exists=False, dir_okay="False"))
@click.option(
    "-e",
    "--encoding",
    type=click.Choice(["cp932", "utf-8", "utf-8-sig"]),
    default="utf-8",
    help="Output text encoding (defaults to utf-8).",
)
@click.option("--lpm", is_flag=True, default=False, help="Include LPM (image) based menus in the extracted output.")
@click.option("--overwrite", is_flag=True, default=False, help="Overwrite existing csv file.")
@click.option("--append", is_flag=True, default=False, help="Append menu data to existing csv file.")
def extractmenu(lsb_file, csv_file, encoding, lpm, overwrite, append):
    """Extract menu choices from the given LSB file to a CSV file.

    You can open this CSV file for translation in most spreadsheet programs (Excel, Open/Libre Office Calc, etc).
    Just remember to choose comma as delimiter and " as quotechar.

    NOTE: If you are using Excel and UTF-8 text, you must also specify --encoding=utf-8-sig, since Excel requires
    UTF-8 with BOM to handle UTF-8 properly.

    You can use the --append option to add the text data from this lsb file to a existing csv.
    With the --overwrite option an existing csv will be overwritten without warning.

    """
    print("Extracting {} ...".format(lsb_file))

    try:
        pylm = PylmProject(lsb_file)
        call_name = pylm.call_name(lsb_file)
    except LiveMakerException:
        pylm = None
        call_name = None

    try:
        with open(lsb_file, "rb") as f:
            lsb = LMScript.from_file(f, call_name=call_name, pylm=pylm)
    except BadLsbError as e:
        sys.exit("Failed to parse file: {}".format(e))

    if pylm:
        pylm.update_labels(lsb)

    csv_data = []
    names = set()
    for id_, choice in lsb.get_menu_choices():
        if isinstance(choice, LPMSelectionChoice):
            if not lpm:
                continue
            text = f"{choice.name} (Image: {choice.src_file})"
        else:
            text = choice.text
        name = id_.name
        if name in names:
            name = ""
        else:
            names.add(name)
        if pylm:
            _, target_name = pylm.resolve_label(choice.target)
        else:
            target_name = None
        target_name = f" ({target_name})" if target_name else ""
        context = [f"Target: {choice.target}{target_name}"]
        csv_data.append([str(id_), name, "\n".join(context), text, None])

    if len(csv_data) == 0:
        sys.exit("No menu data found.")

    if Path(csv_file).exists():
        if not overwrite and not append:
            sys.exit("File {} already exists. Please use --overwrite or --append option.".format(csv_file))
    elif append:
        print("File {} does not exist, but --append specified. A new file will be created.".format(csv_file))
        append = False

    with open(csv_file, ("a" if append else "w"), encoding=encoding, newline="\n") as csvfile:
        csv_writer = csv.writer(csvfile, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        if not append:
            csv_writer.writerow(CSV_HEADER)
        for row in csv_data:
            csv_writer.writerow(row)

    print("{} Menu entries extracted.".format(len(csv_data)))


@lmlsb.command()
@click.argument("lsb_file", required=True, type=click.Path(exists=True, dir_okay="False"))
@click.argument("csv_file", required=True, type=click.Path(exists=False, dir_okay="False"))
@click.option(
    "-e",
    "--encoding",
    type=click.Choice(["cp932", "utf-8", "utf-8-sig"]),
    default="utf-8",
    help="Output text encoding (defaults to utf-8).",
)
@click.option("--no-backup", is_flag=True, default=False, help="Do not generate backup of original lsb file.")
@click.option("-v", "--verbose", is_flag=True, default=False)
def insertmenu(lsb_file, csv_file, encoding, no_backup, verbose):
    """Apply translated menu choices from the given CSV file to given LSB file.

    CSV_FILE should be a file previously created by the extractmenu command, with added translations.
    --encoding option must match the values were used for extractmenu.

    LPM image menus cannot be edited, to translate LPM menus, replace the relevant GAL image files.

    The original LSB file will be backed up to <lsb_file>.bak unless the --no-backup option is specified.
    """
    lsb_file = Path(lsb_file)
    print("Patching {} ...".format(lsb_file))

    try:
        pylm = PylmProject(lsb_file)
        call_name = pylm.call_name(lsb_file)
    except LiveMakerException:
        pylm = None
        call_name = None

    try:
        with open(lsb_file, "rb") as f:
            lsb = LMScript.from_file(f, pylm=pylm, call_name=call_name)
    except BadLsbError as e:
        sys.exit("Failed to parse file: {}".format(e))

    csv_data = []

    with open(csv_file, newline="\n", encoding=encoding) as csvfile:
        csv_reader = csv.reader(csvfile, delimiter=",", quotechar='"')
        for row in csv_reader:
            csv_data.append(row)

    translated, failed, untranslated = _patch_csv_menus(lsb, lsb_file, csv_data, verbose)

    print(f"  Translated {translated} choices")
    print(f"  Failed to translate {failed} choices")
    print(f"  Ignored {untranslated} untranslated choices")
    if not translated:
        return

    if not no_backup:
        print("Backing up original LSB.")
        shutil.copyfile(str(lsb_file), "{}.bak".format(str(lsb_file)))
    try:
        new_lsb_data = lsb.to_lsb()
        with open(lsb_file, "wb") as f:
            f.write(new_lsb_data)
        print("Wrote new LSB.")
    except LiveMakerException as e:
        sys.exit("Could not generate new LSB file: {}".format(e))


def _patch_csv_menus(lsb, lsb_file, csv_data, verbose=False):
    """Patch text menus in lsb using csv_data."""
    text_objects = []
    untranslated = 0

    for row, (id_str, name, context, orig_text, translated_text) in enumerate(csv_data):
        try:
            id_ = make_identifier(id_str)
        except BadTextIdentifierError as e:
            if row > 0:
                # ignore possible header row
                print(f"Ignoring invalid text ID: {e}")
            continue

        if not isinstance(id_, TextMenuIdentifier):
            continue

        if id_.filename == lsb_file.name:
            if translated_text:
                if verbose:
                    print(f"{id_}: '{orig_text}' -> '{translated_text}'")
                text_objects.append((id_, translated_text))
            else:
                if verbose:
                    print(f"{id_} Ignoring untranslated text '{orig_text}'")
                untranslated += 1

    translated, failed = lsb.replace_text(text_objects)

    return translated, failed, untranslated


@lmlsb.command()
@click.argument("lsb_file", required=True, type=click.Path(exists=True, dir_okay="False"))
@click.argument("csv_file", required=True, type=click.Path(exists=False, dir_okay="False"))
@click.option(
    "-e",
    "--encoding",
    type=click.Choice(["cp932", "utf-8", "utf-8-sig"]),
    default="utf-8",
    help="Output text encoding (defaults to utf-8).",
)
@click.option("--overwrite", is_flag=True, default=False, help="Overwrite existing csv file.")
@click.option("--append", is_flag=True, default=False, help="Append text data to existing csv file.")
def extractcsv(lsb_file, csv_file, encoding, overwrite, append):
    """Extract text from the given LSB file to a CSV file.

    You can open this CSV file for translation in most spreadsheet programs (Excel, Open/Libre Office Calc, etc).
    Just remember to choose comma as delimiter and " as quotechar.

    NOTE: If you are using Excel and UTF-8 text, you must also specify --encoding=utf-8-sig, since Excel requires
    UTF-8 with BOM to handle UTF-8 properly.

    You can use the --append option to add the text data from this lsb file to a existing csv.
    With the --overwrite option an existing csv will be overwritten without warning.

    NOTE: Formatting tags will be lost when using this command in conjunction with insertcsv.
    For translating games which use formatting tags, you may need to work directly with LNS scripts
    using the extract and insert/batchinsert commands.
    """
    lsb_file = Path(lsb_file)
    print("Extracting {} ...".format(lsb_file))

    try:
        pylm = PylmProject(lsb_file)
        call_name = pylm.call_name(lsb_file)
    except LiveMakerException:
        pylm = None
        call_name = None

    try:
        with open(lsb_file, "rb") as f:
            lsb = LMScript.from_file(f, call_name=call_name, pylm=pylm)
    except BadLsbError as e:
        sys.exit("Failed to parse file: {}".format(e))

    csv_data = []
    for id_, block in lsb.get_text_blocks():
        csv_data.append([str(id_), id_.name, block.name_label, block.text, None])

    if len(csv_data) == 0:
        sys.exit("No text data found.")

    if Path(csv_file).exists():
        if not overwrite and not append:
            sys.exit("File {} already exists. Please use --overwrite or --append option.".format(csv_file))
    elif append:
        print("File {} does not exist, but --append specified. A new file will be created.".format(csv_file))
        append = False

    with open(csv_file, ("a" if append else "w"), newline="\n", encoding=encoding) as csvfile:
        csv_writer = csv.writer(csvfile, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        if not append:
            csv_writer.writerow(CSV_HEADER)
        for row in csv_data:
            csv_writer.writerow(row)

    print(f"Extracted {len(csv_data)} text blocks.")


def _patch_csv_text(lsb, lsb_file, csv_data, verbose=False):
    """Patch text lines in the given lsb file using csv_data."""
    text_objects = []
    untranslated = 0

    for row, (id_str, name, context, orig_text, translated_text) in enumerate(csv_data):
        try:
            id_ = make_identifier(id_str)
        except BadTextIdentifierError as e:
            if row > 0:
                # ignore possible header row
                print(f"Ignoring invalid text ID: {e}")
            continue

        if not isinstance(id_, TextBlockIdentifier):
            continue

        if id_.filename == lsb_file.name:
            if translated_text:
                if verbose:
                    print(f"{id_}: '{orig_text}' -> '{translated_text}'")
                text_objects.append((id_, translated_text))
            else:
                if verbose:
                    print(f"{id_} Ignoring untranslated text '{orig_text}'")
                untranslated += 1

    translated, failed = lsb.replace_text(text_objects)

    return translated, failed, untranslated


@lmlsb.command()
@click.argument("lsb_file", required=True, type=click.Path(exists=True, dir_okay="False"))
@click.argument("csv_file", required=True, type=click.Path(exists=False, dir_okay="False"))
@click.option(
    "-e",
    "--encoding",
    type=click.Choice(["cp932", "utf-8", "utf-8-sig"]),
    default="utf-8",
    help="Output text encoding (defaults to utf-8).",
)
@click.option("--no-backup", is_flag=True, default=False, help="Do not generate backup of original lsb file.")
@click.option("-v", "--verbose", is_flag=True, default=False)
def insertcsv(lsb_file, csv_file, encoding, no_backup, verbose):
    """Apply translated text lines from the given CSV file to given LSB file.

    CSV_FILE should be a file previously created by the extractcsv command, with added translations.
    --encoding option must match the values were used for extractcsv.

    The original LSB file will be backed up to <lsb_file>.bak unless the --no-backup option is specified.
    """
    lsb_file = Path(lsb_file)
    print("Patching {} ...".format(lsb_file))

    try:
        pylm = PylmProject(lsb_file)
        call_name = pylm.call_name(lsb_file)
    except LiveMakerException:
        pylm = None
        call_name = None

    try:
        with open(lsb_file, "rb") as f:
            lsb = LMScript.from_file(f, call_name=call_name, pylm=pylm)
    except BadLsbError as e:
        sys.exit("Failed to parse file: {}".format(e))

    csv_data = []

    with open(csv_file, newline="\n", encoding=encoding) as csvfile:
        csv_reader = csv.reader(csvfile, delimiter=",", quotechar='"')
        for row in csv_reader:
            csv_data.append(row)

    translated, failed, untranslated = _patch_csv_text(lsb, lsb_file, csv_data, verbose)
    print(f"  Translated {translated} lines")
    print(f"  Failed to translate {failed} lines")
    print(f"  Ignored {untranslated} untranslated lines")
    if not translated:
        return

    if not no_backup:
        print("Backing up original LSB.")
        shutil.copyfile(str(lsb_file), "{}.bak".format(str(lsb_file)))
    try:
        new_lsb_data = lsb.to_lsb()
        with open(lsb_file, "wb") as f:
            f.write(new_lsb_data)
        print("Wrote new LSB.")
    except LiveMakerException as e:
        sys.exit("Could not generate new LSB file: {}".format(e))

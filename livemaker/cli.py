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
# -*- coding: utf-8 -*-
"""pylivemaker cli."""

import hashlib
import shutil
import sys
from pathlib import Path

import click

from lxml import etree

from .archive import LMArchive
from .exceptions import LiveMakerException, BadLsbError
from .lsb import LMScript
from .lsb.command import CommandType
from .lsb.novel import LNSDecompiler, LNSCompiler, TWdChar, TWdOpeReturn

_version = """%(prog)s, version %(version)s

Copyright (C) 2019 Peter Rowlands <peter@pmrowla.com>
Copyright (C) 2014 tinfoil <https://bitbucket.org/tinfoil/>

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""


@click.group()
@click.version_option(message=_version)
def lmar():
    """Command-line tool for manipulating LiveMaker archives and EXEs."""
    pass


@lmar.command()
@click.option('-n', '--dry-run', is_flag=True, default=False,
              help='Show what would be done without extracting any files.')
@click.option('-o', '--output-dir', nargs=1, help='Output directory, defaults to current working directory.')
@click.option('-v', '--verbose', is_flag=True, default=False)
@click.argument('input_file', metavar='file', required=True, type=click.Path(exists=True, dir_okay=False))
def x(dry_run, output_dir, verbose, input_file):
    """Extract the specified archive."""
    if not output_dir:
        output_dir = Path.cwd()
    with LMArchive(input_file) as lm:
        for info in lm.infolist():
            if not dry_run:
                lm.extract(info, output_dir)
            if verbose or dry_run:
                print(info.path)


@lmar.command()
@click.argument('input_file', required=True, type=click.Path(exists=True, dir_okay=False))
def l(input_file):
    """List the contents of the specified archive."""
    with LMArchive(input_file) as lm:
        lm.list()


@lmar.command()
@click.argument('input_file', required=True, type=click.Path(exists=True, dir_okay=False))
@click.argument('output_file', required=True, type=click.Path(dir_okay=False, writable=True))
def strip(input_file, output_file):
    """Copy the specified LiveMaker EXE but remove the LiveMaker archive.

    The resulting program cannot be run, but may be useful for reverse engineering or patching reasons.

    """
    with LMArchive(input_file) as lm:
        if lm.is_exe:
            path = Path(output_file)
            if path.exists():
                print('{} already exists and will be overwritten.'.format(path))
            with open('output_file', 'wb') as f:
                f.write(lm.read_exe())
        else:
            print('The specified file is not a LiveMaker executable.')


@click.group()
@click.version_option(message=_version)
def lmlsb():
    """Command-line tool for manipulating LSB scripts."""
    pass


@lmlsb.command()
@click.argument('input_file', metavar='file', required=True, type=click.Path(exists=True, dir_okay=False))
def probe(input_file):
    """Output information about the specified LSB file in human-readable form.

    Novel script scenario character and line count are estimates. Depending
    on how a script was originally created, actual char/line counts may vary.

    """
    print(input_file)
    with open(input_file, 'rb') as f:
        try:
            lm = LMScript.from_file(f)
        except BadLsbError as e:
            sys.exit('Could not read file: {}'.format(e))
    if lm._parsed_from == 'lsc':
        print('LiveMaker LSC script file:')
    elif lm._parsed_from == 'lsc-xml':
        print('LiveMaker XML LSC script file:')
    elif lm._parsed_from == 'lsb':
        print('LiveMaker compiled LSB script file:')
    else:
        print('LiveMaker script file:')
    print('  Version: {} (LiveMaker{})'.format(lm.version, lm.lm_version))
    print('  Total commands: {}'.format(len(lm)))
    cmd_types = set()
    for cmd in lm.commands:
        cmd_types.add(cmd.type)
    print('    Command types: {}'.format(', '.join([x.name for x in sorted(cmd_types)])))
    scenarios = lm.text_scenarios()
    print('  Total text scenarios: {}'.format(len(scenarios)))
    for index, name, scenario in scenarios:
        if not name:
            name = 'Unlabeled scenario'
        print('    {}'.format(name))
        tpwd_types = set()
        char_count = 0
        line_count = 0
        for wd in scenario.body:
            tpwd_types.add(wd.type)
            if isinstance(wd, TWdChar):
                char_count += 1
            elif isinstance(wd, TWdOpeReturn):
                line_count += 1
        print('      LiveNovel scenario version: {}'.format(scenario.version))
        print('      TpWd types: {}'.format(', '.join([x.name for x in sorted(tpwd_types)])))
        print('      Approx. character count: {}'.format(char_count))
        if char_count:
            # don't count line breaks in event-only scenarios
            print('      Approx. line count: {}'.format(line_count))


@lmlsb.command()
@click.argument('input_file', metavar='file', required=True, nargs=-1, type=click.Path(exists=True))
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
        with open(path, 'rb') as f:
            data = f.read()
        try:
            lsb = LMScript.from_lsb(data)
            orig = hashlib.sha256(data).hexdigest()
        except BadLsbError as e:
            print('  Failed to parse file: {}'.format(e))
            continue
        try:
            built_data = lsb.to_lsb()
            reassembled = hashlib.sha256(built_data).hexdigest()
        except BadLsbError as e:
            print('  Failed to reassemble file: {}'.format(e))
            continue
        print('  Orig: {} ({} bytes)'.format(orig, len(data)))
        print('   New: {} ({} bytes)'.format(reassembled, len(built_data)))
        if orig == reassembled:
            print('  SHA256 digest validation passed')
        if orig != reassembled:
            print('  SHA256 digest validation failed')
        for line, name, scenario in lsb.text_scenarios():
            print('  {}'.format(name))
            orig_bytes = scenario._struct().build(scenario)
            dec = LNSDecompiler()
            script = dec.decompile(scenario)
            cc = LNSCompiler()
            new_body = cc.compile(script)
            scenario.replace_body(new_body)
            new_bytes = scenario._struct().build(scenario)
            if new_bytes == orig_bytes:
                print('  script passed')
            else:
                print('  script mismatch, {} {}'.format(len(orig_bytes), len(new_bytes)))


@lmlsb.command()
@click.option('-m', '--mode', type=click.Choice(['text', 'xml', 'lines']), default='text',
              help='Output mode (defaults to text)')
@click.option('-e', '--encoding', type=click.Choice(['cp932', 'utf-8']), default='utf-8',
              help='Output text encoding (defaults to utf-8).')
@click.argument('input_file', required=True, nargs=-1, type=click.Path(exists=True, dir_okay='False'))
def dump(mode, encoding, input_file):
    """Dump the contents of the specified LSB file(s) to stdout in a human-readable format.

    For text mode, the full LSB will be output as human-readable text.

    For xml mode, the full LSB file will be output as an XML document.

    For lines mode, only text lines will be output.
    """
    for path in input_file:
        with open(path, 'rb') as f:
            data = f.read()
        try:
            lsb = LMScript.from_lsb(data)
        except BadLsbError as e:
            sys.stderr.write('  Failed to parse file: {}'.format(e))
            continue
        if mode == 'xml':
            root = lsb.to_xml()
            print(etree.tostring(root, encoding=encoding, pretty_print=True, xml_declaration=True).decode(encoding))
        elif mode == 'lines':
            lsb_path = Path(path)
            for line, name, scenario in lsb.text_scenarios():
                if name:
                    name = '{}-{}.lns'.format(lsb_path.stem, name)
                if not name:
                    name = '{}-line{}.lns'.format(lsb_path.stem, line)
                print(name)
                print('------')
                dec = LNSDecompiler(text_only=True)
                print(dec.decompile(scenario))
                print()
        else:
            for c in lsb.commands:
                if c.Mute:
                    mute = ';'
                else:
                    mute = ''
                s = ['{}{:4}: {}'.format(mute, c.LineNo, '    ' * c.Indent)]
                s.append(str(c).replace('\r', '\\r').replace('\n', '\\n'))
                print(''.join(s))
                if c.type == CommandType.TextIns:
                    dec = LNSDecompiler()
                    print(dec.decompile(c.get('Text')))


@lmlsb.command()
@click.option('-e', '--encoding', type=click.Choice(['cp932', 'utf-8']), default='utf-8',
              help='Output text encoding (defaults to utf-8).')
@click.option('-o', '--output-dir', type=click.Path(file_okay=False),
              help='Output directory. Defaults to the current working directory if not specified.'
                   ' If directory does not exist it will be created.')
@click.argument('input_file', required=True, nargs=-1, type=click.Path(exists=True, dir_okay=False))
def extract(encoding, output_dir, input_file):
    """Extract decompiled LiveNovel scripts from the specified input file(s).

    By default, extracted scripts will be encoded as utf-8, but if you intend
    to patch a script back into an LSB, you will still be limited to cp932
    characters only.

    Output files will be named <LSB name>-<scenario name>.lns

    """
    if output_dir:
        output_dir = Path(output_dir)
        if not output_dir.exists:
            output_dir.mkdir(parents=True)
    else:
        output_dir = Path.cwd()
    for path in input_file:
        print('Extracting scripts from {}'.format(path))
        lsb_path = Path(path)
        lsb = LMScript.from_file(path)
        for line, name, scenario in lsb.text_scenarios():
            if name:
                name = '{}-{}.lns'.format(lsb_path.stem, name)
            if not name:
                name = '{}-line{}.lns'.format(lsb_path.stem, line)
            output_path = output_dir.joinpath(name)
            dec = LNSDecompiler()
            with open(output_path, 'w', encoding=encoding) as f:
                f.write(dec.decompile(scenario))
            print('  wrote {}'.format(output_path))


@lmlsb.command()
@click.option('-e', '--encoding', type=click.Choice(['cp932', 'utf-8']), default='utf-8',
              help='The text encoding of script_file (defaults to utf-8).')
@click.argument('lsb_file', required=True, type=click.Path(exists=True, dir_okay=False))
@click.argument('script_file', required=True, type=click.Path(exists=True, dir_okay=False))
# TODO: make this optional and parse label/line number from script filename
@click.argument('line_number', required=True, type=int)
def insert(encoding, lsb_file, script_file, line_number):
    """Compile specified LNS script and insert it into the specified LSB file.

    The LSB command at line_number must be a TextIns command. The existing text
    block of the specified TextIns command will be replaced with the new one from
    script_file.

    script_file should be an LNS script which was initially generated by lmlsb extract.

    The original LSB file will be backed up to <lsb_file>.bak

    """
    with open(script_file, 'rb') as f:
        script = f.read().decode(encoding)
    try:
        cc = LNSCompiler()
        new_body = cc.compile(script)
    except LiveMakerException as e:
        sys.exit('Could not compile script file: {}'.format(e))

    with open(lsb_file, 'rb') as f:
        try:
            lsb = LMScript.from_file(f)
        except LiveMakerException as e:
            sys.exit('Could not open LSB file: {}'.format(e))

    for index, name, scenario in lsb.text_scenarios():
        if index == line_number:
            print('Scenario {} at line {} will be replaced.'.format(name, index))
            scenario.replace_body(new_body)
            break
    else:
        sys.exit('No matching TextIns command in the specified LSB.')

    print('Backing up original LSB.')
    shutil.copyfile(str(lsb_file), '{}.bak'.format(str(lsb_file)))
    try:
        new_lsb_data = lsb.to_lsb()
        with open(lsb_file, 'wb') as f:
            f.write(new_lsb_data)
        print('Wrote new LSB.')
    except LiveMakerException as e:
        sys.exit('Could not generate new LSB file: {}'.format(e))


def main():
    pass


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover

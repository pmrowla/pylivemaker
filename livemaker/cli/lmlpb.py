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
# -*- coding: utf-8 -*-
"""LiveMaker LPB project settings CLI tool."""

import shutil
import sys

import click

from livemaker.exceptions import LiveMakerException, BadLpbError
from livemaker.lpb import LMProject
from livemaker.lsb.core import Param, ParamType

from .cli import _version, __version__
from .lmlsb import _edit_parser_op


@click.group()
@click.version_option(version=__version__, message=_version)
def lmlpb():
    """Command-line tool for manipulating LPB project settings."""
    pass


@lmlpb.command()
@click.argument("input_file", metavar="file", required=True, type=click.Path(exists=True, dir_okay=False))
def probe(input_file):
    """Output information about the specified LPB file in human-readable form."""
    print(input_file)
    with open(input_file, "rb") as f:
        try:
            lpb = LMProject.from_file(f)
        except BadLpbError as e:
            sys.exit("Could not read file: {}".format(e))
    print("LiveMaker project settings file:")
    print("  Version: {} (LiveMaker{})".format(lpb.version, lpb.lm_version))
    print("  Project Name: {}".format(lpb.project_name))
    print("  Project dir: {}".format(lpb.project_dir))
    print("  Init LSB: {}".format(lpb.init_lsb))
    print("  Exit LSB: {}".format(lpb.exit_lsb))
    print("  Settings:")
    for setting in lpb.system_settings:
        print("    {}: {}".format(setting["name"], setting["value"]))


EDITABLE_STRINGS = {
    "project_name": "Project Name",
    "project_dir": "Project Directory",
    "init_lsb": "Initial LSB (run at startup)",
    "exit_lsb": "Exit LSB (run at exit)",
}


@lmlpb.command()
@click.argument("lpb_file", required=True, type=click.Path(exists=True, dir_okay=False))
def edit(lpb_file):
    """Edit the specified LPB file.

    Only specific settings can be edited.

    The original LPB file will be backed up to <lpb_file>.bak

    Note: Setting empty fields to improper data types may cause
    undefined behavior in the LiveMaker engine. When editing a field,
    the data type of the new value is assumed to be the same as the
    original data type.

    """
    with open(lpb_file, "rb") as f:
        try:
            lpb = LMProject.from_file(f)
        except LiveMakerException as e:
            sys.exit("Could not open LPB file: {}".format(e))

    print("Editing LM project {}".format(lpb_file))
    for key in lpb.keys():
        orig = getattr(lpb, key)
        if key in EDITABLE_STRINGS:
            name = EDITABLE_STRINGS[key]
            value = click.prompt(name, orig)
            if value != orig:
                setattr(lpb, key, value)
        elif key != "system_settings":
            print("{} [{}]: <skipping uneditable field>".format(key, orig))
    print("System settings:")
    for setting in lpb.system_settings:
        name = setting["name"]
        orig = setting["value"]
        param_type = setting["type"]
        param = Param(value=orig, type=ParamType[param_type])
        _edit_parser_op(param, prompt="  {}".format(name))
        if param.value != orig:
            setting["value"] = param.value
        print(lpb.system_settings)

    print("Backing up original LPB.")
    shutil.copyfile(str(lpb_file), "{}.bak".format(str(lpb_file)))
    try:
        new_lpb_data = lpb.to_lpb()
        with open(lpb_file, "wb") as f:
            f.write(new_lpb_data)
        print("Wrote new LPB.")
    except LiveMakerException as e:
        sys.exit("Could not generate new LPB file: {}".format(e))

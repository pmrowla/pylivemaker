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
"""LiveMaker archive CLI tool."""

from io import BytesIO
from pathlib import Path

import click

from PIL import Image

from livemaker import GalImagePlugin
from livemaker.archive import LMArchive
from livemaker.exceptions import UnsupportedLiveMakerCompression

from .cli import __version__, _version


@click.group()
@click.version_option(version=__version__, message=_version)
def lmar():
    """Command-line tool for manipulating LiveMaker archives and EXEs."""
    pass


@lmar.command()
@click.option('-n', '--dry-run', is_flag=True, default=False,
              help='Show what would be done without extracting any files.')
@click.option('-i', '--image-format', type=click.Choice(['gal', 'png', 'both']), default='gal',
              help='Format for extracted images, defaults to GAL (original) format. If set to png, images will be'
                   ' converted before extraction. If set to both, both the original GAL and converted PNG images will'
                   ' be extracted')
@click.option('-o', '--output-dir', nargs=1, help='Output directory, defaults to current working directory.')
@click.option('-v', '--verbose', is_flag=True, default=False)
@click.argument('input_file', metavar='file', required=True, type=click.Path(exists=True, dir_okay=False))
def x(dry_run, image_format, output_dir, verbose, input_file):
    """Extract the specified archive."""
    if output_dir:
        output_dir = Path(output_dir)
    else:
        output_dir = Path.cwd()
    with LMArchive(input_file) as lm:
        for info in lm.infolist():
            if str(info.path).lower().endswith('.gal'):
                if not dry_run:
                    try:
                        data = lm.read(info)
                    except UnsupportedLiveMakerCompression as e:
                        print('  Error extracting {}: {}'.format(info.path, e))
                        continue
                if image_format in ('gal', 'both'):
                    if not dry_run:
                        path = Path.joinpath(output_dir, info.path).expanduser().resolve()
                        path.parent.mkdir(parents=True, exist_ok=True)
                        with path.open('wb') as f:
                            f.write(data)
                    if verbose or dry_run:
                        print(info.path)
                if image_format in ('png', 'both'):
                    try:
                        png_path = info.path.parent.joinpath('{}.png'.format(info.path.stem))
                        if not dry_run:
                            path = output_dir.joinpath(png_path).expanduser().resolve()
                            im = Image.open(BytesIO(data))
                            path.parent.mkdir(parents=True, exist_ok=True)
                            im.save(path)
                        if verbose or dry_run:
                            print(png_path)
                    except IOError as e:
                        print('Error: Failed to convert image to PNG: {}'.format(e))
                        if image_format == 'png':
                            print('  Original GAL image will be used as fallback.')
                            if not dry_run:
                                lm.extract(info, output_dir)
                            if verbose or dry_run:
                                print(info.path)
            else:
                if not dry_run:
                    try:
                        lm.extract(info, output_dir)
                    except UnsupportedLiveMakerCompression as e:
                        print('  Error extracting {}: {}'.format(info.path, e))
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

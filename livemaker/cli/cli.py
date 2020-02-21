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

import sys
from pathlib import Path

import click

from PIL import Image
from livemaker import __version__, GalImagePlugin

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


@click.command()
@click.version_option(version=__version__, message=_version)
@click.option('-f', '--force', is_flag=True, default=False,
              help='Overwrite output file if it exists.')
@click.argument('input_file', required=True, type=click.Path(exists=True, dir_okay=False))
@click.argument('output_file', required=True, type=click.Path(dir_okay=False))
def galconvert(force, input_file, output_file):
    """Convert the image to another format.

    GAL(X) images can only be read (for conversion to JPEG/PNG/etc) at this time.

    Output format will be determined based on file extension.

    """
    try:
        im = Image.open(input_file)
    except IOError as e:
        raise e
        # sys.exit('Error opening {}: {}'.format(input_file, e))
    if Path(output_file).exists() and not force:
        sys.exit('{} already exists'.format(output_file))
    print('Converting {} to {}'.format(input_file, output_file))
    im.load()
    im.save(output_file)

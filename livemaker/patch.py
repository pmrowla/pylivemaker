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
"""pylivemaker patcher."""

import logging
import os
import sys
import tempfile
from pathlib import Path, PureWindowsPath

import click

from livemaker import LMArchive
from livemaker.exceptions import LiveMakerException


log = logging.getLogger(__name__)
fh = logging.FileHandler('patch.log')
fh.setLevel(logging.INFO)
log.addHandler(fh)


@click.command()
# @lmlsb.option('-r', '--recursive', is_flag=True, default=False)
@click.argument('exe_file', required=True, type=click.Path(exists=True, dir_okay=False))
@click.argument('patched_lsb', required=True, type=click.Path(exists=True, dir_okay=False))
def lmpatch(exe_file, patched_lsb):
    """Patch a LiveMaker game.

    Any existing version of patched_lsb will be replaced in the specified
    LiveMaker executable. If a file with the same name as patched_lsb does
    not already exist, this will do nothing.

    A backup copy of the old exe will also be created.

    """
    exe_path = Path(exe_file)
    backup_path = Path('{}.bak'.format(exe_path))
    if backup_path.exists():
        sys.exit('{} already exists'.format(backup_path))

    try:
        orig_lm = LMArchive(exe_path)
    except LiveMakerException as e:
        log.error(e)
        return

    if orig_lm.is_exe:
        fd, tmp_exe = tempfile.mkstemp()
        fp = os.fdopen(fd, 'wb')
        fp.write(orig_lm.read_exe())
        fp.close()
    else:
        tmp_exe = None

    lsb_path = PureWindowsPath(patched_lsb)
    try:
        fd, tmpfile_path = tempfile.mkstemp()
        tmpfile_path = Path(tmpfile_path)
        tmpfp = os.fdopen(fd, 'wb')
        log.info('opened {}'.format(tmpfile_path))
        print('Writing archive contents')
        with LMArchive(exe_path, 'w', fp=tmpfp, version=orig_lm.version, exe=tmp_exe) as new_lm:
            def bar_show(item):
                width, _ = click.get_terminal_size()
                width //= 4
                name = item.name if item is not None else ''
                if len(name) > width:
                    name = ''.join(['...', name[-width:]])
                return name
            # patch
            with click.progressbar(orig_lm.infolist(), item_show_func=bar_show) as bar:
                for info in bar:
                    # data = orig_lm.read(info, decompress=False)
                    # new_lm.writebytes(info, data)
                    if info.path == lsb_path:
                        # replace existing with patch version, use original
                        # compress type
                        new_lm.write(lsb_path, compress_type=info.compress_type)
                        log.info('patched {}'.format(lsb_path))
                        # print('patched')
                    else:
                        # copy original version
                        data = orig_lm.read(info, decompress=False)
                        new_lm.writebytes(info, data)
                        log.info('copied {}'.format(lsb_path))
                    # print(info.name)
        orig_lm.close()
        tmpfp.close()

        # backup original file
        exe_path.rename(backup_path)
        # mv tmpfile
        tmpfile_path.rename(exe_path)
    except Exception as e:
        log.error(e)
        # remove
        tmpfile_path.unlink()
        raise e
    finally:
        if tmp_exe is not None:
            Path(tmp_exe).unlink()


if __name__ == '__main__':
    lmpatch()

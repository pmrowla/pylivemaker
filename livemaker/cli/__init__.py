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
"""pylivemaker cli."""

import os
import sys

from loguru import logger

from .cli import galconvert, lmbmp
from .lmar import lmar
from .lmgraph import lmgraph
from .lmlpb import lmlpb
from .lmlsb import lmlsb
from .lmpatch import lmpatch

__all__ = ["galconvert", "lmar", "lmbmp", "lmgraph", "lmlpb", "lmlsb", "lmpatch"]


logger.remove()

if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

logger.add(sys.stderr, level="WARNING")
logger.enable("livemaker")

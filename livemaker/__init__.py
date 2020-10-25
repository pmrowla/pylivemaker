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
"""Top-level package for pylivemaker."""

__author__ = """Peter Rowlands"""
__email__ = "peter@pmrowla.com"
__license__ = "GPLv3"
__version__ = "1.0.1"


from loguru import logger

from .archive import LMArchive, LMArchiveInfo, LMCompressType
from .lsb import LMScript, LNSCompiler, LNSDecompiler

__all__ = ["LMArchive", "LMArchiveInfo", "LMCompressType", "LMScript", "LNSCompiler", "LNSDecompiler"]


logger.disable("livemaker")

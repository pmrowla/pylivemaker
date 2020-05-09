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
"""pylivemaker exceptions."""


class LiveMakerException(Exception):
    """Base pylivemaker exception."""


class BadLiveMakerArchive(LiveMakerException):
    """Error raised for bad/invalid archive files."""


class UnsupportedLiveMakerVersion(LiveMakerException):
    pass


class UnsupportedLiveMakerCompression(LiveMakerException):
    pass


class BadLsbError(LiveMakerException):
    """Error raised for bad/invalid LSB script files."""


class BadLpbError(LiveMakerException):
    """Error raised for bad/invalid LPB project settings files."""


class BadLnsError(LiveMakerException):
    """Error raised for bad/invalid LNS novel scripts."""


class InvalidCharError(BadLnsError):
    def __init__(self, ch, encoding="cp932"):
        self.ch = ch
        self.encoding = encoding
        super().__init__(f"'{ch}' is not a valid {encoding.upper()} character.")


class BadTextIdentifierError(LiveMakerException):
    """Error raised for bad/invalid translatable text IDs."""

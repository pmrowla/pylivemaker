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
"""pylivemaker project management module."""

import os
from collections import defaultdict
from pathlib import Path, PureWindowsPath

from .exceptions import LiveMakerException
from .lsb.command import CommandType
from .lsb.lmscript import LMScript


class PylmProject:
    def __init__(self, path):
        self.root = self.find_root(path)
        if not self.root:
            raise LiveMakerException(f"{path} is not inside a LM project")
        self._label_cache = defaultdict(dict)

    @staticmethod
    def find_root(path):
        """Return root LM project dir for the specified path."""
        path = Path(path).resolve()
        if not path.exists():
            return None
        if path.is_file():
            path = path.parent
        search_names = {"live.lpb", "ゲームメイン.lsb", "ノベルシステム"}
        for search_dir in [path] + list(reversed(path.parents)):
            if set(os.listdir(search_dir)) & search_names:
                return search_dir
        return None

    def call_name(self, path):
        path = Path(path).resolve()
        if path.suffix not in (".lsb", ".lsc"):
            raise LiveMakerException(f"{path} is not an LSB")
        try:
            relpath = PureWindowsPath(path.relative_to(self.root))
            name = f"{relpath.stem}.lsb"
            return str(relpath.parent / name)
        except ValueError:
            raise LiveMakerException(f"{path} is outside this project")

    def update_labels(self, lsb):
        """Update labels from the specified lsb."""
        if not lsb.call_name:
            raise LiveMakerException("Cannot update labels for lsb without call_name")
        names = {}
        lines = {}
        for cmd in lsb.commands:
            if cmd.type == CommandType.Label:
                name = cmd["Name"]
                names[name] = cmd.LineNo
                lines[cmd.LineNo] = name
        cache = self._label_cache[lsb.call_name]
        if "names" in cache:
            cache["names"].update(names)
        else:
            cache["names"] = names
        if "lines" in cache:
            cache["lines"].update(lines)
        else:
            cache["lines"] = lines

    def resolve_label(self, ref):
        """Return tuple(line_no, name) for the specified label reference."""
        # Page is a rel path with windows slash, we need to convert it to
        # system path on posix
        if isinstance(ref.Label, int) and ref.Label == 0:
            # start of script is not labeled
            return None, None

        path = Path(PureWindowsPath(ref.Page))
        call_name = self.call_name(path)
        if call_name not in self._label_cache:
            path = self.root / PureWindowsPath(call_name)
            try:
                lsb = LMScript.from_file(path, call_name=call_name)
                self.update_labels(lsb)
            except LiveMakerException:
                raise LiveMakerException(f"Could not update labels from {call_name}")
        cache = self._label_cache[call_name]
        if isinstance(ref.Label, int):
            name = cache["lines"].get(ref.Label)
            if name:
                return (ref.Label, name)
        else:
            line_no = cache["names"].get(ref.Label)
            if line_no is not None:
                return (line_no, ref.Label)
        return None, None

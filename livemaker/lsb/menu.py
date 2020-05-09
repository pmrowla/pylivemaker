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
"""LiveMaker LiveNovel selection menu classes."""

import re
from pathlib import PurePath, PureWindowsPath

from .command import CommandType
from ..exceptions import LiveMakerException
from ..lpm import LMLivePrevMenu


class NotSelectionMenuError(LiveMakerException):
    pass


class BaseSelectionMenu:
    """Base selection menu class."""

    CHOICE_RE = re.compile(r"^AddArray\(_tmp, \"(?P<text>.*)\"\)$")
    SELECT_RE = re.compile(r"選択値 == \"(?P<text>.*)\"")
    END_SELECTION_CALCS = ["選択実行中 = 0"]
    EXECUTE_LSB = None

    def __init__(self, label=None, choices=[]):
        self.label = label
        self._choices = []
        for choice in choices:
            self.add_choice(choice)

    @property
    def choices(self):
        return self._choices[:]

    def __len__(self):
        return len(self.choices)

    def __iter__(self):
        return iter(self.choices)

    def add_choice(self, choice):
        self._choices.append(choice)

    @classmethod
    def is_menu_start(cls, cmd):
        # Selection process starts with
        #   Calc 選択実行中 = 1
        if cmd.type == CommandType.Calc and str(cmd["Calc"]) == "選択実行中 = 1":
            return True
        return False

    @classmethod
    def is_menu_end(cls, cmd):
        # Selection process ends with
        #   Calc 選択実行中 = 0
        if cmd.type == CommandType.Calc and str(cmd["Calc"]) == "選択実行中 = 0":
            return True

    @classmethod
    def from_lsb_command(cls, lsb, start):
        """Return a selection menu constructed from the LSB commands
        starting at index.

        Args:
            lsb (:class:`LMScript`): LSB script instance
            start (int): Command index for the start of the menu

        """
        raise NotImplementedError

    @classmethod
    def _find_execute_params(cls, lsb, index):
        if not cls.EXECUTE_LSB:
            raise NotImplementedError
        for index in range(index, len(lsb)):
            cmd = lsb.commands[index]
            if cls.is_menu_end(cmd):
                break
            if cmd.type == CommandType.Call and cmd["Page"]["Page"] == cls.EXECUTE_LSB:
                return cmd["Params"], index + 1
        return None, index + 1

    @classmethod
    def _choice_from_cmd(cls, cmd):
        # menu array populated with
        #   Calc AddArray(_tmp, "foo")
        if cmd.type != CommandType.Calc:
            return None
        calc = cmd["Calc"]
        m = cls.CHOICE_RE.match(str(calc))
        if m:
            return m.group("text")
        return None

    @classmethod
    def _end_choices(cls, cmd):
        # menu array population finishes with
        #   Calc StringToArray(_tmp, _tmp)
        if cmd.type != CommandType.Calc:
            return None
        calc = cmd["Calc"]
        if str(calc) in cls.END_SELECTION_CALCS + ["StringToArray(_tmp, _tmp)"]:
            return True
        return False

    @classmethod
    def _find_choices(cls, lsb, index):
        choices = []
        for index in range(index, len(lsb)):
            cmd = lsb.commands[index]
            if cls._end_choices(cmd):
                break
            choice = cls._choice_from_cmd(cmd)
            if choice:
                choices.append((choice, index))
        return choices, index + 1

    @staticmethod
    def _end_int_jumps(cmd):
        if cmd.type == CommandType.Wait:
            return True
        return False

    @classmethod
    def _int_jump_from_cmd(cls, cmd):
        # intermediate jump after selection
        #   Jump 00000000.lsb:123 選択値 == "foo"
        if cmd.type != CommandType.Jump:
            return None, None
        page = cmd["Page"]
        calc = cmd["Calc"]
        m = cls.SELECT_RE.match(str(calc))
        if m:
            return m.group("text"), page
        return None, None

    @classmethod
    def _find_int_jumps(cls, lsb, index):
        jumps = {}
        indent = lsb.commands[index]["Indent"]
        for index in range(index, len(lsb)):
            cmd = lsb.commands[index]
            if cmd["Indent"] > indent:
                continue
            if cls._end_int_jumps(cmd):
                break
            text, jump = cls._int_jump_from_cmd(cmd)
            if jump:
                jumps[text] = (jump, index)
        return jumps, index + 1

    @classmethod
    def _resolve_int_jump(cls, int_target, index, lsb):
        # if intermediate jump is followed by a branch (jump or call)
        # to an external LSB script, use external target
        resolved = int_target
        if int_target["Page"] == lsb.call_name:
            # skip intermediate target label
            start = int_target["Label"] + 1
            for index in range(start, len(lsb)):
                cmd = lsb.commands[index]
                if cmd.type in (CommandType.Call, CommandType.Jump):
                    target = cmd["Page"]
                    if target["Page"] != lsb.call_name:
                        # branch to external LSB script
                        resolved = target
                        break
                    if cmd.type == CommandType.Jump:
                        # internal branch, use intermediate target
                        break
                else:
                    break
        return resolved, index


class TextSelectionChoice:
    def __init__(self, text, text_index, target, index):
        self.text = text
        self.text_index = text_index
        self.target = target
        self.index = index

    def __str__(self):
        return f'"{self.text}" -> {self.target}'


class TextSelectionMenu(BaseSelectionMenu):
    """Text selection menu."""

    def __init__(self, **kwargs):
        self._texts = set()
        super().__init__(**kwargs)

    def __str__(self):
        return f"<TextSelectionMenu at {self.label}>"

    def add_choice(self, choice):
        if choice.text in self._texts:
            raise ValueError("Cannot add duplicate choices")
        self._choices.append(choice)
        self._texts.add(choice.text)

    @classmethod
    def from_lsb_command(cls, lsb, start):
        try:
            cmd = lsb.commands[start]
            if not cls.is_menu_start(cmd):
                raise NotSelectionMenuError
        except IndexError:
            raise NotSelectionMenuError
        label = None
        try:
            cmd = lsb.commands[start - 2]
            if cmd.type == CommandType.Label:
                label = cmd
        except IndexError:
            pass
        choices, next_cmd = cls._find_choices(lsb, start + 1)
        if not choices:
            raise NotSelectionMenuError
        jumps, next_cmd = cls._find_int_jumps(lsb, next_cmd)
        if not jumps:
            raise NotSelectionMenuError
        for text in jumps:
            target, index = jumps[text]
            jumps[text] = cls._resolve_int_jump(target, index, lsb)

        menu = cls(label=label)
        for text, text_index in choices:
            try:
                target, target_index = jumps[text]
            except KeyError:
                raise KeyError(f"No matching jump for menu choice {text}")
            choice = TextSelectionChoice(text, text_index, target, target_index)
            menu.add_choice(choice)
        return menu


class LPMSelectionChoice:
    def __init__(self, src_file, name, target, index):
        self.src_file = src_file
        self.name = name
        self.target = target
        self.index = index

    def __str__(self):
        return f'"{self.src_file}" -> {self.target}'


class LPMSelectionMenu(BaseSelectionMenu):
    """Live Preview (image) selection menu."""

    # NovelSystem/PreviewMenu/*SelectExecute.lsb
    EXECUTE_LSB = r"ノベルシステム\プレビューメニュー\■選択実行.lsb"

    def __init__(self, lpm_file, **kwargs):
        self.lpm_file = lpm_file
        self._names = set()
        super().__init__(**kwargs)

    def __str__(self):
        return f"<LPMSelectionMenu({self.lpm_file}) at {self.label}>"

    def add_choice(self, choice):
        if choice.name in self._names:
            raise ValueError("Cannot add duplicate choices")
        self._choices.append(choice)
        self._names.add(choice.name)

    @classmethod
    def _parse_params(cls, params):
        params = params.parsers
        return {
            "parent": str(params[0]),  # parent menu
            "menu_file": str(params[1]),  # source LPM file
            "in_time": int(str(params[2])),  # fade-in time
            "out_time": int(str(params[3])),  # fade-out duration
            "hover_sound": str(params[4]),  # hover sound effect
            "select_sound": str(params[5]),  # select sound effect
            "disable_rclick": int(str(params[6])),  # disable right click
            "enabled_var": str(params[7]),  # choice enabled array var
            "visible_var": str(params[8]),  # choice visible array var
            "selection_time": int(str(params[9])),  # time before selection expires (countdown timer)
            "selected_var": str(params[10]),  # choice (pre-)selected var
        }

    @classmethod
    def _choices_from_lpm(cls, filename):
        try:
            path = PurePath(PureWindowsPath(filename.strip('"')))
            lpm = LMLivePrevMenu.from_file(path)
            choices = []
            for button in lpm["buttons"]:
                choices.append((button.get("src"), button.get("name")))
            return choices
        except LiveMakerException:
            return []

    @classmethod
    def from_lsb_command(cls, lsb, start):
        try:
            cmd = lsb.commands[start]
            if not cls.is_menu_start(cmd):
                raise NotSelectionMenuError
        except IndexError:
            raise NotSelectionMenuError
        try:
            label = lsb.commands[start - 2]
        except IndexError:
            label = None
        params, next_cmd = cls._find_execute_params(lsb, start + 1)
        if not params:
            raise NotSelectionMenuError
        params = cls._parse_params(params)
        lpm_file = params["menu_file"].strip('"')
        choices = cls._choices_from_lpm(lpm_file)
        if not choices:
            raise NotSelectionMenuError

        jumps, next_cmd = cls._find_int_jumps(lsb, next_cmd)
        if not jumps:
            raise NotSelectionMenuError
        for text in jumps:
            target, index = jumps[text]
            jumps[text] = cls._resolve_int_jump(target, index, lsb)

        menu = cls(lpm_file, label=label)
        for src_file, name in choices:
            try:
                target, target_index = jumps[name]
            except KeyError:
                raise KeyError(f"No matching jump for menu choice {text}")
            choice = LPMSelectionChoice(src_file, name, target, target_index)
            menu.add_choice(choice)
        return menu


def make_menu(lsb, index):
    for cls in [TextSelectionMenu, LPMSelectionMenu]:
        try:
            return cls.from_lsb_command(lsb, index)
        except NotSelectionMenuError:
            pass
    raise NotSelectionMenuError

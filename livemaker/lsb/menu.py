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

from .command import CommandType
from ..exceptions import LiveMakerException


class NotSelectionMenuError(LiveMakerException):
    pass


class BaseSelectionMenu:
    """Base selection menu class."""

    CHOICE_RE = re.compile(r"^AddArray\(_tmp, \"(?P<text>.*)\"\)$")
    SELECT_RE = re.compile(r"選択値 == \"(?P<text>.*)\"")
    END_SELECTION_CALCS = ["選択実行中 = 0"]

    @classmethod
    def is_menu_start(cls, cmd):
        # All selection menus start with
        #   Calc 選択実行中 = 1
        if cmd.type == CommandType.Calc and str(cmd["Calc"]) == "選択実行中 = 1":
            return True
        return False

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
            return None
        page = cmd["Page"]
        calc = cmd["Calc"]
        m = cls.SELECT_RE.match(str(calc))
        if m:
            return page
        return None

    @classmethod
    def _find_int_jumps(cls, lsb, index):
        jumps = []
        indent = lsb.commands[index]["Indent"]
        for index in range(index, len(lsb)):
            cmd = lsb.commands[index]
            if cmd["Indent"] > indent:
                continue
            if cls._end_int_jumps(cmd):
                break
            jump = cls._int_jump_from_cmd(cmd)
            if jump:
                jumps.append((jump, index))
        return jumps, index + 1

    @classmethod
    def _resolve_int_jumps(cls, jumps, lsb):
        # if intermediate jump is followed by a branch (jump or call)
        # to an external LSB script, use external target
        final_jumps = []
        for int_target, index in jumps:
            resolved = int_target
            if int_target["Page"] == lsb.call_name:
                # skip intermediate target label
                start = int_target["Label"] + 1
                for index in range(start, len(lsb)):
                    cmd = lsb.commands[index]
                    print(index, cmd)
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
            final_jumps.append((resolved, index))
        return final_jumps


class LPMSelectionMenu(BaseSelectionMenu):
    """LPM graphical selection menu."""

    @classmethod
    def from_lsb_command(cls, lsb, start):
        pass


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

    def __init__(self, choices=[]):
        self._choices = []
        self._texts = set()
        for choice in choices:
            self.add_choice(choice)

    @property
    def choices(self):
        return self._choices[:]

    def __len__(self):
        return len(self.choices)

    def __iter__(self):
        return iter(self.choices)

    def __str__(self):
        return str([str(choice) for choice in self.choices])

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
        choices, next_cmd = cls._find_choices(lsb, start + 1)
        if not choices:
            raise NotSelectionMenuError
        jumps, next_cmd = cls._find_int_jumps(lsb, next_cmd)
        if not jumps:
            raise NotSelectionMenuError
        jumps = cls._resolve_int_jumps(jumps, lsb)

        menu = cls()
        for (text, text_index), (target, target_index) in zip(choices, jumps):
            choice = TextSelectionChoice(text, text_index, target, target_index)
            menu.add_choice(choice)
        return menu


def make_menu(lsb, index):
    for cls in [TextSelectionMenu]:
        try:
            return cls.from_lsb_command(lsb, index)
        except NotSelectionMenuError:
            pass
    raise NotSelectionMenuError

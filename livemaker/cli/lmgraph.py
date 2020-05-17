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
"""pylivemaker lsb call graph tool."""

import sys
from collections import deque
from pathlib import Path

import click

import pydot

from livemaker.exceptions import LiveMakerException
from livemaker.lsb import LMScript
from livemaker.lsb.command import CommandType
from livemaker.lsb.graph import make_graph, nx_to_dot

from .cli import _version, __version__


@click.group()
@click.version_option(version=__version__, message=_version)
def lmgraph():
    """Experimental command-line tool for generating DOT syntax graphs."""


IGNORED_SCRIPTS = [
    "メッセージボックス作成.lsb",
    "メッセージボックス座標.lsb",
]


visited = set()
lsbs_to_visit = deque()
graph = pydot.Dot(graph_type="digraph")


def parse_lsb(lsb_file, root_dir=None):
    """Parse one LSB into the graph."""
    if root_dir:
        path = root_dir.joinpath(lsb_file)
    else:
        path = lsb_file
    if path in visited:
        return
    visited.add(path)
    print("processing {}...".format(path))
    with open(path, "rb") as f:
        try:
            lsb = LMScript.from_file(f)
        except LiveMakerException as e:
            sys.exit("Could not open LSB file: {}".format(e))
    graph.add_node(pydot.Node(str(lsb_file), label=str(lsb_file)))
    remaining_cmds = set(range(1, len(lsb.commands)))

    # very naive attempt at determining condition for jumping to a new script
    cmds_to_visit = deque([(0, None)])
    while cmds_to_visit:
        pc, last_calc = cmds_to_visit.popleft()
        cmd = lsb.commands[pc]
        if cmd.type == CommandType.Jump:
            ref = cmd.get("Page")
            calc = str(cmd.get("Calc"))

            if ref.Page == lsb_file:
                if calc != "1":
                    # branch not taken
                    next_pc = pc + 1
                    if next_pc in remaining_cmds:
                        remaining_cmds.remove(next_pc)
                        cmds_to_visit.append((next_pc, last_calc))
                if calc != "0":
                    # branch taken
                    if calc == "1":
                        calc = last_calc
                    next_pc = ref.Label
                    if next_pc in remaining_cmds:
                        remaining_cmds.remove(next_pc)
                        cmds_to_visit.append((next_pc, calc))
            elif not ref.Page.startswith("ノベルシステム"):
                if last_calc:
                    edge = pydot.Edge(lsb_file, ref.Page, label=last_calc)
                else:
                    edge = pydot.Edge(lsb_file, ref.Page)
                graph.add_edge(edge)
                lsbs_to_visit.append(ref.Page)
        elif cmd.type == CommandType.Call:
            ref = cmd.get("Page")
            calc = str(cmd.get("Calc"))

            if ref.Page != lsb_file and not ref.Page.startswith("ノベルシステム") and ref.Page not in IGNORED_SCRIPTS:
                # ignore calls to self (used for cleanup sometimes) and
                # novel system calls
                if last_calc:
                    edge = pydot.Edge(lsb_file, ref.Page, label=last_calc)
                else:
                    edge = pydot.Edge(lsb_file, ref.Page)
                graph.add_edge(edge)
                lsbs_to_visit.append(ref.Page)

            next_pc = pc + 1
            if next_pc in remaining_cmds:
                remaining_cmds.remove(next_pc)
                cmds_to_visit.append((next_pc, last_calc))
        elif cmd.type not in (CommandType.Exit, CommandType.Terminate, CommandType.PCReset):
            next_pc = pc + 1
            if next_pc in remaining_cmds:
                remaining_cmds.remove(next_pc)
                cmds_to_visit.append((next_pc, last_calc))


@lmgraph.command()
@click.argument("lsb_file", required=True, type=click.Path(exists=True, dir_okay=False))
@click.argument("out_file", required=False)
def game(lsb_file, out_file):
    """Generate a DOT syntax call graph for a full LiveNovel game.

    lsb_file should be a path to the root script node - this should always be ゲームメイン.lsb (game_main.lsb)
    for LiveMaker games.
    If output file is not specified, it defaults to <lsb_file>.dot

    The output graph will start with game_main as the root node and follow branches to all scenario
    scripts, which should give a general approximation of the original LiveMaker scenario chart.
    """
    path = Path(lsb_file)
    print("Generating graph for {}".format(path))
    if path.name != "ゲームメイン.lsb":
        print("Warning: input filename is not ゲームメイン.lsb")
    root_dir = path.parent
    lsbs_to_visit.append(path.name)
    while lsbs_to_visit:
        parse_lsb(lsbs_to_visit.popleft(), root_dir=root_dir)
    if not out_file:
        out_file = "{}.dot".format(lsb_file)
    with open(out_file, "w") as f:
        f.write(graph.to_string())
    print("Wrote {}".format(out_file))


@lmgraph.command()
@click.argument("lsb_file", required=True, type=click.Path(exists=True, dir_okay=False))
@click.argument("out_file", required=False)
def lsb(lsb_file, out_file):
    """Generate a DOT syntax execution graph for an LSB script.

    lsb_file should be an LSB file.
    If output file is not specified, it defaults to <lsb_file>.dot

    The output graph will contain blocks of LSB commands as nodes
    and branch points as edges.
    """
    path = Path(lsb_file)
    print("Generating execution graph for {}".format(path))

    if not out_file:
        out_file = "{}.dot".format(lsb_file)

    lsb = LMScript.from_file(path)
    dot = nx_to_dot(make_graph(lsb))

    with open(out_file, "w") as f:
        f.write(dot.to_string())
    print("Wrote {}".format(out_file))

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
"""LiveMaker LSB/LSC command execution tree/graph module."""

from collections import deque

import networkx as nx
from loguru import logger

from .command import CommandType
from ..exceptions import LiveMakerException


END_COMMANDS = [
    CommandType.Exit,
    CommandType.GameLoad,
    CommandType.PCReset,
    CommandType.Reset,
    CommandType.Terminate,
]


def _jump_edges(lsb, pc, cmd):
    ref = cmd.get("Page")
    calc = str(cmd.get("Calc"))
    logger.info(f"{pc}: {cmd}")

    if ref.Page == lsb.call_name:
        next_pc = ref.Label
        if calc == "0":
            # branch never taken
            yield (pc, pc + 1), None
        elif calc == "1":
            # branch always taken
            yield (pc, next_pc), None
        else:
            yield (pc, next_pc), f"If {calc}"
            yield (pc, pc + 1), "Else"


def handle_jump(graph, unvisited, lsb, pc, cmd, **kwargs):
    for edge, cond in _jump_edges(lsb, pc, cmd):
        graph.add_edge(*edge, branch=True, cond=cond)


def _if_edge(if_pc, case_pc, cmd):
    return (if_pc, case_pc + 1), str(cmd)


def handle_if(graph, unvisited, lsb, if_pc, if_cmd, return_pc=None):
    logger.info(f"{if_pc}: {if_cmd}")
    # find if/elseif/else
    if_indent = if_cmd.Indent
    if_cases = [(if_pc, if_cmd)]
    else_case = []
    for pc in range(if_pc + 1, len(lsb.commands)):
        cmd = lsb.commands[pc]
        if cmd.Indent > if_indent:
            continue
        if cmd.Indent == if_indent:
            if cmd.type == CommandType.Elseif:
                if_cases.append((pc, cmd))
                unvisited.remove(pc)
                graph.remove_node(pc)
                continue
            if cmd.type == CommandType.Else:
                else_case.append((pc, cmd))
                unvisited.remove(pc)
                graph.remove_node(pc)
                continue
            end_pc = pc
        else:
            end_pc = return_pc
        break
    if end_pc is None:
        raise LiveMakerException("invalid If/Elseif/Else sequence")

    # add edges and visit if/elseif/else cases
    for pc, cmd in if_cases + else_case:
        edge, cond = _if_edge(if_pc, pc, cmd)
        graph.add_edge(*edge, branch=True, cond=cond)
        nested = deque()
        for nested_pc in range(pc + 1, len(lsb.commands)):
            nested_cmd = lsb.commands[nested_pc]
            if nested_cmd.Indent == cmd.Indent + 1:
                nested.append(nested_pc)
                continue
            elif nested_cmd.Indent > cmd.Indent + 1:
                continue
            break
        visit(graph, nested, lsb, return_pc=end_pc)
    if not else_case:
        graph.add_edge(if_pc, end_pc, branch=True, cond="Else")


def handle_while(graph, unvisited, lsb, init_pc, init_cmd, return_pc=None):
    logger.info(f"{init_pc}: {init_cmd}")
    # find end of loop
    while_pc = None
    while_cmd = None
    loop_pc = None
    while_indent = init_cmd.Indent
    for pc in range(init_pc + 1, len(lsb.commands)):
        cmd = lsb.commands[pc]
        if cmd.Indent > while_indent:
            continue
        if cmd.Indent == while_indent:
            if cmd.type == CommandType.While:
                while_pc = pc
                while_cmd = cmd
                unvisited.remove(pc)
                graph.remove_node(pc)
                continue
            elif cmd.type == CommandType.WhileLoop:
                loop_pc = pc
                unvisited.remove(pc)
                graph.remove_node(pc)
                break
        raise LiveMakerException("invalid While loop sequence")

    if loop_pc + 1 in unvisited:
        end_pc = loop_pc + 1
    else:
        end_pc = return_pc
    if not end_pc:
        raise LiveMakerException("invalid While loop sequence")

    # add edges
    graph.add_edge(init_pc, while_pc, branch=False)
    calc = str(while_cmd.get("Calc"))
    graph.add_edge(while_pc, while_pc + 1, branch=True, cond=f"While {calc}")
    graph.add_edge(while_pc, end_pc, branch=True, cond="Done")
    graph.add_edge(loop_pc, while_pc, branch=False)

    # visit loop
    nested = deque(range(while_pc + 1, loop_pc))
    visit(graph, nested, lsb, return_pc=loop_pc)


HANDLERS = {CommandType.Jump: handle_jump, CommandType.If: handle_if, CommandType.WhileInit: handle_while}


def visit(graph, unvisited, lsb, return_pc=None):
    while unvisited:
        pc = unvisited.popleft()
        cmd = lsb.commands[pc]
        if cmd.Mute:
            continue
        if cmd.type in HANDLERS:
            HANDLERS[cmd.type](graph, unvisited, lsb, pc, cmd, return_pc=return_pc)
        elif cmd.type not in END_COMMANDS:
            if pc + 1 in unvisited:
                graph.add_edge(pc, pc + 1, branch=False)
            elif return_pc is not None:
                graph.add_edge(pc, return_pc, branch=True)


def make_graph(lsb):
    graph = nx.DiGraph()

    # populate nodes
    for i, cmd in enumerate(lsb.commands):
        graph.add_node(i, cmd=cmd)

    # find edges
    unvisited = deque([i for i in range(len(lsb.commands)) if lsb.commands[i].Indent == 0])
    visit(graph, unvisited, lsb)
    return graph


def nx_to_dot(graph):
    import pydot

    dot = pydot.Dot(graph_type="digraph")
    block_nodes = []
    for n in reversed(list(nx.dfs_postorder_nodes(graph))):
        block_nodes.append(n)
        adjacent = list(graph.adj[n].items())
        if len(adjacent) == 1:
            nbr, edge_data = adjacent[0]
            cmd = graph.nodes[nbr]["cmd"]
            if not (cmd.type == CommandType.Label or edge_data.get("branch")):
                continue

        lines = []
        for node in block_nodes:
            cmd = graph.nodes[node]["cmd"]
            s = str(cmd).replace("\r", "\\r").replace("\n", "\\n")
            lines.append(f"{cmd.LineNo:4}: {s}\\l")
            if cmd.type == CommandType.TextIns:
                blocks = cmd["Text"].get_text_blocks()
                if blocks:
                    for line in blocks[0].text.splitlines():
                        lines.append(f"    {line}\\l")
                    lines.append("    ...\\l")

        block_start = block_nodes[0]
        dot_node = pydot.Node(block_start, label="".join(lines), shape="box")
        dot.add_node(dot_node)
        block_nodes.clear()

        for nbr, edge_data in adjacent:
            cond = edge_data.get("cond")
            if cond:
                dot_edge = pydot.Edge(block_start, nbr, label=cond)
            else:
                dot_edge = pydot.Edge(block_start, nbr)
            dot.add_edge(dot_edge)

    return dot

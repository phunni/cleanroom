#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


import cleanroom

from enum import Enum, auto
import importlib.util
import inspect
import os


class ExecObject:
    def __init__(self, command, *args):
        self._command = command
        self._args = args

    def execute(self):
        self._command.execute(*self._args)


class Parser:
    ''' Parse a container.conf file '''

    _commands = {}
    ''' A list of known commands '''

    class State(Enum):
        START = auto()
        PARSING = auto()
        IN_MULTILINE = auto()

    @staticmethod
    def find_commands(ctx):
        ctx.printer.trace('Checking for commands.')
        checked_dirs = []
        for path in ( ctx.systemsCommandsDirectory(), ctx.commandsDirectory()):
            if path in checked_dirs:
                continue
            checked_dirs.append(path)
            ctx.printer.trace('Checking "{}" for command files.'.format(path))
            if not os.path.isdir(path):
                continue # skip non-existing directories

            for f in os.listdir(path):
                if not f.endswith('.py'):
                   continue

                f_path = os.path.join(path, f)
                ctx.printer.trace('Found file: {}'.format(f_path))

                cmd = f[:-3]
                name = 'cr_cmd_' + cmd + '.py'

                spec = importlib.util.spec_from_file_location(name, f_path)
                cmd_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(cmd_module)

                predicate = lambda x : inspect.isclass(x) and \
                                       x.__name__.endswith('Command') and \
                                       x.__module__ == name
                klass = inspect.getmembers(cmd_module, predicate)
                instance = klass[0][1](ctx)
                Parser._commands[cmd] = ( instance, f_path )

        ctx.printer.debug('Commands found:')
        for (name, value) in Parser._commands.items():
            path = value[1]
            location = '<GLOBAL>' if path.startswith(ctx.commandsDirectory() + '/') else '<LOCAL>'
            ctx.printer.debug('  {}: {}'.format(name, location))

    def __init__(self, ctx):
        self._ctx = ctx
        self._reset_parsing_state()

    def parse(self, input_file):
        _reset_parsing_state(self)

        with open(input_file, 'r') as f:
            for line in f:
                obj = self._parse_line(line)
                if obj:
                    yield obj

        if self._state == Parser.State.IN_MULTILINE:
            raise cleanroom.ParseError(line, 'In multiline string at EOF.')

    def _reset_parsing_state(self):
        self._state = Parser.State.START
        self._line = 0

    def _parse_line(self, line):
        if self._state == Parser.State.START:
            self._state = Parser.State.PARSING

        if self._state == Parser.State.PARSING:
            pass


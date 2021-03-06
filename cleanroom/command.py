# -*- coding: utf-8 -*-
"""Base class for commands usable in the system definition files.

The Command class will be used to derive all system definition file commands
from.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from __future__ import annotations

from .binarymanager import Binaries
from .exceptions import GenerateError, ParseError
from .execobject import ExecObject
from .location import Location
from .printer import fail, h3, success, verbose
from .systemcontext import SystemContext

import os
import os.path
from string import Template
import typing


def stringify(
    command: str,
    args: typing.Tuple[typing.Any, ...],
    kwargs: typing.Mapping[str, typing.Any],
):
    args_str = ' "' + '" "'.join(map(lambda a: str(a), args)) + '"' if args else ""
    kwargs_str = (
        " ".join(map(lambda kv: kv[0] + '="' + str(kv[1]) + '"', kwargs.items()))
        if kwargs
        else ""
    )
    separator = " " if args_str and kwargs_str else ""
    return '"{}"'.format(command) + args_str + separator + kwargs_str


def _expand_arg(system_context: SystemContext, arg: typing.Any) -> typing.Any:
    return (
        Template(arg).substitute(system_context.substitutions)
        if isinstance(arg, str)
        else arg
    )


def process_args(
    system_context: SystemContext, *args: typing.Any
) -> typing.Tuple[str, ...]:
    result: typing.Tuple[str, ...] = ()
    for a in args:
        result = (*result, _expand_arg(system_context, str(a)))
    return result


def process_kwargs(
    system_context: SystemContext, **kwargs: typing.Any
) -> typing.Dict[str, typing.Any]:
    result: typing.Dict[str, typing.Any] = {}
    for k, v in kwargs.items():
        result[k] = _expand_arg(system_context, v)
    return result


class Command:
    """A command that can be used in to set up a machines."""

    def __init__(
        self,
        name: str,
        *,
        file: str,
        syntax: str = "",
        help_string: str,
        **services: typing.Any
    ) -> None:
        """Constructor."""
        self._name = name
        self._syntax_string = syntax
        self._help_string = help_string
        helper_directory = os.path.join(
            os.path.dirname(os.path.realpath(file)), "helper", self._name
        )
        self.__helper_directory = (
            helper_directory if os.path.isdir(helper_directory) else None
        )
        self._services = services

    @property
    def syntax_string(self) -> str:
        """Return syntax description."""
        if self._syntax_string:
            return "{} {}".format(self._name, self._syntax_string)
        return self._name

    @property
    def name(self) -> str:
        return self._name

    @property
    def help_string(self) -> str:
        """Print help string."""
        return self._help_string

    def validate(
        self, location: Location, *args: typing.Any, **kwargs: typing.Any
    ) -> None:
        """Implement this!

        Validate all arguments.
        """
        fail('Command "{}" called validate illegally!'.format(self.name))
        return None

    def dependency(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Optional[str]:
        """Maybe implement this, but this default should be ok."""
        return None

    def __call__(
        self,
        location: Location,
        system_context: SystemContext,
        *args: typing.Any,
        **kwargs: typing.Any
    ) -> None:
        """Implement this!"""
        fail('Command "{}"() triggered illegally!'.format(self.name))

    def _execute(
        self,
        location: Location,
        system_context: SystemContext,
        command: str,
        *args: typing.Any,
        **kwargs: typing.Any
    ) -> None:
        command_info = self._service("command_manager").command(command)
        if not command_info:
            raise GenerateError('Command "{}" not found.'.format(command))
        command_info.validate_func(location, *args, **kwargs)
        command_info.execute_func(location, system_context, *args, **kwargs)

    def _add_hook(
        self,
        location: Location,
        system_context: SystemContext,
        hook_name: str,
        command: str,
        *args: typing.Any,
        **kwargs: typing.Any
    ) -> None:
        """Add a hook."""
        command_info = self._service("command_manager").command(command)
        if not command_info:
            raise ParseError('Command "{}" not found.'.format(command))
        command_info.validate_func(location, *args, **kwargs)

        system_context.add_hook(
            hook_name,
            ExecObject(location=location, command=command, args=args, kwargs=kwargs),
        )

    def _run_hooks(self, system_context: SystemContext, hook_name: str) -> None:
        if system_context.hooks_were_run(hook_name):
            verbose('Already ran "{}", skipping.'.format(hook_name))
            return

        h3('Running "{}" hooks.'.format(hook_name))

        for hook in system_context.hooks(hook_name):
            command_info = self._service("command_manager").command(hook.command)
            if not command_info:
                raise GenerateError('Command "{}" not found.'.format(hook.command))
            command_info.execute_func(
                hook.location, system_context, *hook.args, **hook.kwargs
            )

        success('Hooks "{}" were run successfully.'.format(hook_name), verbosity=1)

    def _service(self, service_name: str) -> typing.Any:
        return self._services.get(service_name, None)

    @property
    def _helper_directory(self) -> typing.Optional[str]:
        """Return the helper directory."""
        return self.__helper_directory

    def _config_directory(self, system_context) -> str:
        return os.path.join(
            system_context.systems_definition_directory, "config", self.name
        )

    # Validation of args and kwargs:
    def _validate_no_arguments(
        self, location: Location, *args: typing.Any, **kwargs: typing.Any
    ) -> None:
        self._validate_no_args(location, *args)
        self._validate_kwargs(location, (), **kwargs)

    def _validate_arguments_exact(
        self,
        location: Location,
        arg_count: int,
        message: str,
        *args: typing.Any,
        **kwargs: typing.Any
    ) -> None:
        self._validate_args_exact(location, arg_count, message, *args)
        self._validate_kwargs(location, (), **kwargs)

    def _validate_arguments_at_least(
        self,
        location: Location,
        arg_count: int,
        message: str,
        *args: typing.Any,
        **kwargs: typing.Any
    ) -> None:
        self._validate_args_at_least(location, arg_count, message, *args)
        self._validate_kwargs(location, (), **kwargs)

    def _validate_no_args(self, location: Location, *args: typing.Any) -> None:
        self._validate_args_exact(location, 0, '"{}" does not take arguments.', *args)

    def _validate_args_exact(
        self, location: Location, arg_count: int, message: str, *args: typing.Any
    ) -> None:
        if len(args) != arg_count:
            raise ParseError(message.format(self.name), location=location)

    def _validate_args_at_least(
        self, location: Location, arg_count: int, message: str, *args: typing.Any
    ) -> None:
        if len(args) < arg_count:
            raise ParseError(message.format(self.name), location=location)

    def _validate_kwargs(
        self,
        location: Location,
        known_kwargs: typing.Tuple[str, ...],
        **kwargs: typing.Any
    ) -> None:
        if not known_kwargs:
            if kwargs:
                raise ParseError(
                    '"{}" does not accept keyword arguments.'.format(self.name),
                    location=location,
                )
        else:
            for key in kwargs.keys():
                if key not in known_kwargs:
                    raise ParseError(
                        '"{}" does not accept the keyword '
                        'arguments "{}".'.format(self.name, key),
                        location=location,
                    )

    def _require_kwargs(
        self,
        location: Location,
        required_kwargs: typing.Tuple[str, ...],
        **kwargs: typing.Any
    ) -> None:
        for key in required_kwargs:
            if key not in kwargs:
                raise ParseError(
                    '"{}" requires the keyword '
                    'arguments "{}" to be passed.'.format(self.name, key),
                    location=location,
                )

    def _binary(self, binary: Binaries):
        return self._service("binary_manager").binary(binary)

# -*- coding: utf-8 -*-
"""create_os_release command.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from cleanroom.command import Command
from cleanroom.location import Location
from cleanroom.systemcontext import SystemContext

import typing


class CreateOsReleaseCommand(Command):
    """The create_os_release command."""

    def __init__(self, **services) -> None:
        """Constructor."""
        super().__init__(
            "create_os_release",
            syntax="",
            help_string="Create os release file.",
            file=__file__,
            **services
        )

    def validate(
        self, location: Location, *args: typing.Any, **kwargs: typing.Any
    ) -> None:
        """Validate arguments."""
        self._validate_no_arguments(location, *args, **kwargs)

    def __call__(
        self,
        location: Location,
        system_context: SystemContext,
        *args: typing.Any,
        **kwargs: typing.Any
    ) -> None:
        """Execute command."""
        os_release = 'NAME="{}"\n'.format(
            system_context.substitution("DISTRO_NAME", "Arch Linux")
        )
        os_release += 'PRETTY_NAME="{}"\n'.format(
            system_context.substitution("DISTRO_PRETTY_NAME", "Arch Linux")
        )
        os_release += 'ID="{}"\n'.format(
            system_context.substitution("DISTRO_ID", "arch")
        )
        os_release += 'ID_LIKE="arch"\n'
        os_release += 'ANSI_COLOR="0;36"\n'
        os_release += 'HOME_URL="{}"\n'.format(
            system_context.substitution("DISTRO_HOME_URL", "https://www.archlinux.org/")
        )
        os_release += 'SUPPORT_URL="{}"\n'.format(
            system_context.substitution(
                "DISTRO_SUPPORT_URL", "https://bbs.archlinux.org/"
            )
        )
        os_release += 'BUG_REPORT_URL="{}"\n'.format(
            system_context.substitution("DISTRO_BUG_URL", "https://bugs.archlinux.org/")
        )
        os_release += 'VERSION="{}"\n'.format(
            system_context.substitution("DISTRO_VERSION", "unknown")
        )
        os_release += 'VERSION_ID="{}"\n'.format(
            system_context.substitution("DISTRO_VERSION_ID", "unknown")
        )

        self._execute(
            location,
            system_context,
            "create",
            "/usr/lib/os-release",
            os_release,
            force=True,
            mode=0o644,
        )

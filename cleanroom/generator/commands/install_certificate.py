# -*- coding: utf-8 -*-
"""install_certificate command.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from cleanroom.generator.command import Command

import os
import os.path
import stat


class InstallCertificatesCommand(Command):
    """The install_certificate command."""

    def __init__(self):
        """Constructor."""
        super().__init__('install_certificate', syntax='<CA_CERT>+',
                         help='Install CA certificates.', file=__file__)

    def validate_arguments(self, location, *args, **kwargs):
        """Validate the arguments."""
        self._validate_arguments_at_least(location, 1,
                                          '"{}" needs at least one '
                                          'ca certificate to add',
                                          *args, **kwargs)

    def __call__(self, location, system_context, *args, **kwargs):
        """Execute command."""
        for f in args:
            source = f if os.path.isabs(f) \
                else os.path.join(system_context.ctx.systems_directory(), f)
            dest = os.path.join('/etc/ca-certificates/trust-source/anchors',
                                os.path.basename(f))
            system_context.execute(location, 'copy',
                                   source, dest, from_outside=True)
            system_context.execute(location, 'chmod',
                                   stat.S_IRUSR | stat.S_IWUSR
                                   | stat.S_IRGRP | stat.S_IROTH, dest)

        system_context.run('/usr/bin/trust', 'extract-compat')
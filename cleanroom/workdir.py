#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


import os
import os.path
import tempfile


class WorkDir:
    ''' Parse a container.conf file '''

    def __init__(self, ctx, work_dir):
        self._path = work_dir
        self._tempDir = None

        if work_dir:
            if not os.path.exists(work_dir):
                ctx.printer.trace('Creating permanent work directory in "{}".'.format(work_dir))
                os.makedirs(work_dir, 0o700)
            else:
                ctx.printer.trace('Using existing work directory in "{}".'.format(work_dir))
        else:
            ctx.printer.trace('Creating temporary work directory.')
            self._tempDir = tempfile.TemporaryDirectory(prefix='clrm-', dir='/var/tmp')
            self._path = self._tempDir.name;

    def __del__(self):
        self.cleanup()

    def __enter__(self):
        if self._tempDir:
            return self._tempDir.__enter__()
        else:
            return self._path

    def __exit__(self, exc_type, exc_val, exc_tb):
        if (self._tempDir):
            tmpDir = self._tempDir
            self._tempDir = None
            return tmpDir.__exit__(exc_type, exc_val, exc_tb)
        return False

    def name(self):
        return self._path

    def cleanup(self):
        if not self._tempDir:
            return

        self._tempDir.cleanup()
        self._tempDir = None


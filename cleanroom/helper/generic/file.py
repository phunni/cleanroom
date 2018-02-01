#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helpers for file system actions.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from ... import exceptions as ex

import os
import os.path


def file_name(run_context, f):
    """Return the full (outside) file path to a absolute (inside) file."""
    if not os.path.isabs(f):
        raise ex.GenerateError('Filepath "{}" is not absolute.'.format(f))

    full_path = run_context.fs_directory() + f
    return full_path


def create_file(run_context, f, contents):
    """Create a new file with the given contents."""
    os.path.join(run_context.system_directory(), f)
    pass


def replace_file(run_context, f, contents):
    """Replace an existing file with the given contents."""
    pass


def append_file(run_context, f, contents):
    """Append contents to an existing file."""
    pass


def prepend_file(run_context, f, contents):
    """Prepend contents to an existing file."""
    pass


if __name__ == '__main__':
    pass
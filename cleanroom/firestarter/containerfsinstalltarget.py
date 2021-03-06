#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Container-as-basic-filesystem installation target

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from cleanroom.firestarter.installtarget import InstallTarget
import cleanroom.firestarter.tools as tool
from cleanroom.helper.btrfs import BtrfsHelper

import os
import typing


def _extract_into_snapshot(_, rootfs: str, *, import_snapshot: str) -> None:

    # Extract data
    tool.run(
        "/usr/bin/bash",
        "-c",
        "( cd {} ; tar -cf - . ) | ( cd {} ; tar -xf - )".format(
            rootfs, import_snapshot
        ),
    )


class ContainerFilesystemInstallTarget(InstallTarget):
    def __init__(self) -> None:
        super().__init__("container_fs", "Install a container filesystem.")

    def __call__(self, parse_result: typing.Any) -> None:
        container_name = parse_result.override_system_name
        if not container_name:
            container_name = parse_result.system_name
            if container_name.startswith("system-"):
                container_name = container_name[7:]

        container_dir = os.path.join("/var/lib/machines", container_name)
        import_dir = container_dir + "_import"

        try:
            btrfs = BtrfsHelper("/usr/bin/btrfs")
            btrfs.create_subvolume(import_dir)

            # Mount filessystems and copy the rootfs into import_dir:
            tool.execute_with_system_mounted(
                lambda e, r: _extract_into_snapshot(e, r, import_snapshot=import_dir),
                repository=parse_result.repository,
                system_name=parse_result.system_name,
                system_version=parse_result.system_version,
            )

            # Delete *old* container-name:
            if btrfs.is_subvolume(container_dir):
                btrfs.delete_subvolume(container_dir)

            # Copy over container filesystem:
            btrfs.create_snapshot(import_dir, container_dir, read_only=True)

        finally:
            btrfs.delete_subvolume(import_dir)

    def setup_subparser(self, parser: typing.Any) -> None:
        parser.add_argument(
            "--container-name",
            dest="override_system_name",
            action="store",
            nargs="?",
            default="",
            help="Container name to use "
            "[default: system-name without "
            '"system-" prefix]',
        )

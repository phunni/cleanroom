# -*- coding: utf-8 -*-
"""create_clrm_config_initrd command.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""

from cleanroom.binarymanager import Binaries
from cleanroom.command import Command
from cleanroom.helper.run import run
from cleanroom.location import Location
from cleanroom.systemcontext import SystemContext
from cleanroom.printer import debug, info, trace

from hashlib import sha512
import os
import shutil
from tempfile import TemporaryDirectory
import textwrap
import typing


def _device_ify(device: str) -> str:
    if not device:
        return ""
    if device.startswith("PARTLABEL="):
        device = "/dev/disk/by-partlabel/" + device[10:]
    elif device.startswith("LABEL="):
        device = "/dev/disk/by-label/" + device[6:]
    elif device.startswith("PARTUUID="):
        device = "/dev/disk/by-partuuid/" + device[9:]
    elif device.startswith("UUID="):
        device = "/dev/disk/by-uuid/" + device[5:]
    elif device.startswith("ID="):
        device = "/dev/disk/by-id/" + device[3:]
    elif device.startswith("PATH="):
        device = "/dev/disk/by-path/" + device[5:]
    assert device.startswith("/dev/")
    return device


def _escape_device(device: str) -> str:
    device = _device_ify(device)

    device = device.replace("-", "\\x2d")
    device = device.replace("=", "\\x3d")
    device = device.replace(";", "\\x3b")
    device = device.replace("/", "-")

    return device[1:]


def write_file(path: str, contents: bytes, *, mode: int = 0o644):
    assert not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "wb") as fd_out:
        fd_out.write(contents)
    os.chmod(path, mode)


def symlink(path: str, target: str):
    assert not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    os.symlink(target, path)


def _install_image_file_support(
    staging_area: str,
    image_fs: typing.Optional[str],
    image_device: typing.Optional[str],
    image_options: str,
    image_name: str,
) -> typing.List[str]:
    if not image_device:
        assert not image_fs
        assert not image_options
        return []

    assert image_fs

    if image_options:
        image_options = f"{image_options},"
    image_options += "nodev,noexec,nosuid,ro"

    escaped_image_device = _escape_device(image_device)

    write_file(
        os.path.join(staging_area, "usr/lib/systemd/system/images.mount"),
        textwrap.dedent(
            f"""\
                [Unit]
                Description=Mount /images in initrd
                DefaultDependencies=no
                
                [Mount]
                What={image_device}
                Where=/images
                Type={image_fs}
                Options={image_options}
                """
        ).encode("utf-8"),
        mode=0o644,
    )
    trace(
        f"Wrote images.mount (Where={image_device}, Type={image_fs}, Options={image_options})"
    )
    symlink(
        os.path.join(
            staging_area,
            f"usr/lib/systemd/system/{escaped_image_device}.device.wants/images.mount",
        ),
        "../images.mount",
    )

    write_file(
        os.path.join(
            staging_area, "usr/lib/systemd/system/initrd-find-image-partitions.service"
        ),
        textwrap.dedent(
            f"""\
                [Unit]
                Description=Find partitions in image files
                DefaultDependencies=no
                ConditionFileNotEmpty=/images/{image_name}
                After=images.mount
                BindsTo=images.mount
                Requisite=images.mount
                
                [Service]
                WorkingDirectory=/
                Type=oneshot
                RemainAfterExit=yes
                ExecStart=/usr/bin/losetup -P /dev/loop7 /images/{image_name}
                ExecStop=/usr/bin/losetup -d /dev/loop7
                
                [Install]
                WantedBy=images.mount
                """
        ).encode("utf-8"),
        mode=0o644,
    )
    trace("Wrote initrd-find-image-partitions (/images/{image_name}).")
    symlink(
        os.path.join(
            staging_area,
            "usr/lib/systemd/system/images.mount.wants/initrd-find-image-partitions.service",
        ),
        "../initrd-find-image-partitions.service",
    )

    return [
        "loop",
    ]


def _install_lvm_support(
    staging_area: str, vg: typing.Optional[str], image_name: str
) -> typing.List[str]:
    if not vg:
        return []

    device_name = f"dev-{vg}-{image_name}"
    write_file(
        os.path.join(
            staging_area,
            "usr/lib/systemd/system/initrd-find-root-lv-partitions.service",
        ),
        textwrap.dedent(
            f"""\
                [Unit]
                Description=Find partitions in root LV
                DefaultDependencies=no
                ConditionPathExists=/dev/{vg}/{image_name}
                After={device_name}.device
                BindsTo={device_name}.device
                Requisite={device_name}.device
                
                [Service]
                WorkingDirectory=/
                Type=oneshot
                RemainAfterExit=yes
                ExecStart=/usr/bin/partprobe /dev/{vg}/{image_name}
                
                [Install]
                WantedBy={device_name}.device
                """
        ).encode("utf-8"),
        mode=0o644,
    )
    trace("Wrote initrd-find-root-lv-partitions.service")
    symlink(
        os.path.join(
            staging_area,
            f"usr/lib/systemd/system/dev-{vg}-{image_name}.device.wants/initrd-find-root-lv-partitions.service",
        ),
        "../initrd-find-root-lv-partitions.service",
    )

    return []


def _install_sysroot_setup_support(staging_area: str) -> typing.List[str]:
    write_file(
        os.path.join(
            staging_area, "usr/lib/systemd/system/initrd-sysroot-setup.service"
        ),
        textwrap.dedent(
            """\
                [Unit]
                Description=Set up root fs in /sysroot
                DefaultDependencies=no
                ConditionPathExists=/sysroot/usr/lib/boot/root-fs.tar
                Requires=sysroot.mount
                After=sysroot.mount systemd-volatile-root.service
                Before=initrd-root-fs.target shutdown.target
                Conflicts=shutdown.target
                AssertPathExists=/etc/initrd-release
                
                [Service]
                Type=oneshot
                RemainAfterExit=yes
                ExecStart=/usr/bin/tar -C /sysroot -xf /sysroot/usr/lib/boot/root-fs.tar
            """
        ).encode("utf-8"),
        mode=0o644,
    )
    trace("Wrote initrd-sysroot-setup.service")
    symlink(
        os.path.join(
            staging_area,
            "usr/lib/systemd/system/initrd.target.wants/initrd-sysroot-setup.service",
        ),
        "../initrd-sysroot-setup.service",
    )

    return []


def _install_verity_support(
    staging_area: str,
    system_context: SystemContext,
    root_hash: str,
) -> typing.List[str]:
    if not root_hash:
        return []

    assert len(root_hash) == 64

    data_id = f"PARTUUID={root_hash[:8]}-{root_hash[8:12]}-{root_hash[12:16]}-{root_hash[16:20]}-{root_hash[20:32]}"
    data_dev = _device_ify(data_id)
    data_dev_esc = _escape_device(data_dev)

    hash_id = f"PARTUUID={root_hash[32:40]}-{root_hash[40:44]}-{root_hash[44:48]}-{root_hash[48:52]}-{root_hash[52:]}"
    hash_dev = _device_ify(hash_id)
    hash_dev_esc = _escape_device(hash_dev)

    trace(f"root: {root_hash}.")
    trace(f"Data: {data_id} ({data_dev} = {data_dev_esc}.")
    trace(f"Hash: {hash_id} ({hash_dev} = {hash_dev_esc}.")

    os.makedirs(os.path.join(staging_area, "/usr/lib/systemd"), exist_ok=True)

    # Installing binaries is not a good idea in general, as dependencies are not handled!
    # These binaries are probably safe: systemd binaries tend to have few dependencies and those
    # that are included are most likely already in the image due to other systemd binaries!
    shutil.copyfile(
        system_context.file_name("/usr/lib/systemd/systemd-veritysetup"),
        os.path.join(staging_area, "usr/lib/systemd/systemd-veritysetup"),
    )
    os.chmod(os.path.join(staging_area, "usr/lib/systemd/systemd-veritysetup"), 0o755)
    write_file(
        os.path.join(
            staging_area, "usr/lib/systemd/system/systemd-veritysetup-root.service"
        ),
        textwrap.dedent(
            f"""\
                [Unit]
                Description=veritysetup for root partition
                DefaultDependencies=no
                Conflicts=umount.target
                BindsTo={data_dev_esc}.device {hash_dev_esc}.device
                IgnoreOnIsolate=true
                After=cryptsetup-pre.target {data_dev_esc}.device {hash_dev_esc}.device
                Before=cryptsetup.target umount.target

                [Service]
                Type=oneshot
                RemainAfterExit=yes
                ExecStart=/usr/lib/systemd/systemd-veritysetup attach root '{data_dev}' '{hash_dev}' '{root_hash}'
                ExecStop=/usr/lib/systemd/systemd-veritysetup detach root
            """
        ).encode("utf-8"),
        mode=0o644,
    )
    trace("Wrote systemd-veritysetup-root.service")
    crypt_requires = os.path.join(
        staging_area, "usr/lib/systemd/system/cryptsetup.target.requires"
    )
    os.makedirs(crypt_requires)
    symlink(
        os.path.join(
            crypt_requires,
            "systemd-veritysetup-root.service",
        ),
        "../systemd-veritysetup-root.service",
    )

    return [
        "dm-verity",
    ]


def _install_volatile_support(
    staging_area: str, system_context: SystemContext
) -> typing.List[str]:
    shutil.copyfile(
        system_context.file_name(
            "/usr/lib/systemd/system/systemd-volatile-root.service"
        ),
        os.path.join(
            staging_area, "usr/lib/systemd/system/systemd-volatile-root.service"
        ),
    )
    trace("Installed systemd-volatile-root.service")
    symlink(
        os.path.join(
            staging_area,
            "usr/lib/systemd/system/initrd.target.wants/systemd-volatile-root.service",
        ),
        "../systemd-volatile-root.service",
    )
    # Installing binaries is not a good idea in general, as dependencies are not handled!
    # These binaries are probably safe: systemd binaries tend to have few dependencies and those
    # that are included are most likely already in the image due to other systemd binaries!
    shutil.copyfile(
        system_context.file_name("/usr/lib/systemd/systemd-volatile-root"),
        os.path.join(staging_area, "usr/lib/systemd/systemd-volatile-root"),
    )
    os.chmod(os.path.join(staging_area, "usr/lib/systemd/systemd-volatile-root"), 0o755)
    trace("Installed systemd-volatile-root binary.")

    return []


def _install_var_mount_support(
    staging_area: str, system_context: SystemContext
) -> typing.List[str]:
    var_mount = system_context.file_name("/usr/lib/systemd/system/sysroot-var.mount")
    if not os.path.exists(var_mount):
        return []

    shutil.copyfile(
        var_mount,
        os.path.join(
            staging_area,
            "usr/lib/systemd/system/sysroot-var.mount",
        ),
    )
    trace("Installed sysroot-var.mount")
    symlink(
        os.path.join(
            staging_area,
            "usr/lib/systemd/system/initrd-fs.target.wants/sysroot-var.mount",
        ),
        "../sysroot-var.mount",
    )

    return []


def _install_etc_shadow(
    staging_area: str, system_context: SystemContext
) -> typing.List[str]:
    shadow_file = system_context.file_name("/etc/shadow.initramfs")
    if os.path.exists(shadow_file):
        os.makedirs(os.path.join(staging_area, "etc"), exist_ok=True)

        shutil.copyfile(
            shadow_file,
            os.path.join(
                staging_area,
                "etc/shadow",
            ),
        )
        os.chmod(os.path.join(staging_area, "etc/shadow"), 0o600)
        trace("Installed /etc/shadow.initramfs as /etc/shadow into initrd.")
    return []


def _hash_file(path: str) -> bytes:
    hash = sha512()

    with open(path, "rb") as fd:
        while True:
            data = fd.read(1024 * 1024)
            if not data:
                break
            hash.update(data)

    return hash.digest()


def _hash_directory(dir: str) -> typing.Dict[str, bytes]:
    hashes: typing.Dict[str, bytes] = {}
    for root, _, files in os.walk(dir):
        for file in files:
            path = os.path.join(root, file)
            key = os.path.relpath(path, dir)
            hash = _hash_file(path)

            trace(f'Hashed "{path} as "{key}": "{hash}".')

            hashes[key] = hash

    return hashes


def _copy_modules(
    system_context: SystemContext,
    modules: typing.List[str],
    modules_dir: str,
    *,
    kernel_version: str,
):
    known_modules: typing.Dict[str, str] = {}
    src_top = os.path.join(system_context.file_name("/usr/lib/modules"), kernel_version)
    for root, _, files in os.walk(src_top):
        for f in files:
            if "modules." in f:
                continue

            module_name = os.path.splitext(f)[0]
            module_path = os.path.relpath(os.path.join(root, f), src_top)
            assert module_name not in known_modules
            trace(f'Found "{module_name}" at "{os.path.join(root, f)}" ({module_path})')
            known_modules[module_name] = module_path

    target_top = os.path.join(modules_dir, kernel_version)

    debug(f'Installing modules from "{src_top}" into "{target_top}"')
    for m in modules:
        if m not in known_modules:
            info(f"Module {m} not found. Was it built into the kernel?")
            continue
        p = known_modules[m]

        os.makedirs(os.path.dirname(os.path.join(target_top, p)), exist_ok=True)
        trace(f"Copying extra module {m} ({p}).")
        trace(f'    "{os.path.join(src_top, p)}" => "{os.path.join(target_top, p)}".')
        shutil.copyfile(os.path.join(src_top, p), os.path.join(target_top, p))


def _depmod_all(module_dir: str, *, kernel_version: str, depmod_command: str):
    run(
        depmod_command,
        "-a",
        "-b",
        module_dir,
        kernel_version,
    )


def _install_extra_modules(
    staging_area: str,
    system_context: SystemContext,
    modules: typing.List[str],
    *,
    kernel_version: str,
    cpio_command: str,
    depmod_command: str,
):
    if not modules:
        return

    # Extract all initrds:
    with TemporaryDirectory(prefix="clrm_cpio") as tmp:
        initrd_parts = system_context.initrd_parts_directory
        cpio_modules: typing.Dict[str, bytes] = {}

        for p in [
            os.path.join(initrd_parts, f)
            for f in os.listdir(initrd_parts)
            if os.path.isfile(os.path.join(initrd_parts, f))
        ]:
            # extract one initrd:
            run(
                "/usr/bin/bash",
                "-c",
                f'/usr/bin/cat "{p}" | "{cpio_command}" -id',
                work_directory=tmp,
            )

        modules_dir = os.path.join(tmp, "usr/lib/modules")
        os.makedirs(modules_dir, exist_ok=True)
        cpio_modules = _hash_directory(os.path.join(modules_dir, kernel_version))

        _copy_modules(
            system_context, modules, modules_dir, kernel_version=kernel_version
        )
        _depmod_all(
            tmp,
            kernel_version=kernel_version,
            depmod_command=depmod_command,
        )
        new_modules = _hash_directory(os.path.join(modules_dir, kernel_version))

        for t in [
            k
            for k, v in new_modules.items()
            if k not in cpio_modules or cpio_modules[k] != v
        ]:
            target = os.path.join(staging_area, "usr/lib/modules", kernel_version, t)
            src = os.path.join(modules_dir, kernel_version, t)
            trace(f'   Installing module-related file: "{src}" => "{target}".')
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(src, target)
            trace(f"Copied {target} into {staging_area}.")


class CreateClrmConfigInitrdCommand(Command):
    """The _create_clrm_config_initrd command."""

    def __init__(self, **services: typing.Any) -> None:
        """Constructor."""
        super().__init__(
            "_create_clrm_config_initrd",
            syntax="<INITRD_FILE> [root_hash=<ROOT_HASH>]",
            help_string="Create an initrd with extra cleanroom config.",
            file=__file__,
            **services,
        )

    def validate(
        self, location: Location, *args: typing.Any, **kwargs: typing.Any
    ) -> None:
        """Validate the arguments."""
        self._validate_args_exact(
            location,
            1,
            '"{}" takes an initrd to create.',
            *args,
        )
        self._validate_kwargs(location, ("root_hash",), **kwargs)

    def register_substitutions(self) -> typing.List[typing.Tuple[str, str, str]]:
        return [
            (
                "IMAGE_FS",
                "ext2",
                "The filesystem type to load clrm-images from",
            ),
            (
                "IMAGE_DEVICE",
                "",
                "The device to load clrm-images from",
            ),
            (
                "IMAGE_OPTIONS",
                "rw",
                "The filesystem options to mount the IMAGE_DEVICE with",
            ),
            (
                "DEFAULT_VG",
                "",
                "The volume group to look for clrm rootfs/verity partitions on",
            ),
        ]

    def __call__(
        self,
        location: Location,
        system_context: SystemContext,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        """Execute command."""
        if not os.path.exists(os.path.join(system_context.boot_directory, "vmlinuz")):
            info("Skipping initrd generation: No vmlinuz in boot directory.")
            return

        root_hash = kwargs.get("root_hash", "")
        vg = system_context.substitution_expanded("DEFAULT_VG", None)
        image_fs = system_context.substitution_expanded("IMAGE_FS", None)
        image_device = _device_ify(
            system_context.substitution_expanded("IMAGE_DEVICE", None)
        )
        image_options = system_context.substitution_expanded("IMAGE_OPTIONS", "")
        image_name = system_context.substitution_expanded("CLRM_IMAGE_FILENAME", "")

        kver = system_context.substitution("KERNEL_VERSION", "")
        assert kver

        initrd = args[0]

        assert not os.path.exists(initrd)

        staging_area = os.path.join(system_context.cache_directory, "clrm_extra")
        os.makedirs(staging_area)

        cpio_command = self._binary(Binaries.CPIO)

        modules: typing.List[str] = [
            *system_context.substitution_expanded("INITRD_EXTRA_MODULES", "").split(
                ","
            ),
            "squashfs",
            *_install_image_file_support(
                staging_area, image_fs, image_device, image_options, image_name
            ),
            *_install_lvm_support(staging_area, vg, image_name),
            *_install_sysroot_setup_support(staging_area),
            *_install_verity_support(staging_area, system_context, root_hash),
            *_install_volatile_support(staging_area, system_context),
            *_install_var_mount_support(staging_area, system_context),
            *_install_etc_shadow(staging_area, system_context),
        ]
        modules = [
            m for m in modules if m
        ]  # Trim empty modules (e.g. added by the substitution)

        _install_extra_modules(
            staging_area,
            system_context,
            modules,
            kernel_version=kver,
            cpio_command=cpio_command,
            depmod_command=self._binary(Binaries.DEPMOD),
        )

        # Create Initrd:
        run(
            "/bin/sh",
            "-c",
            f'"{self._binary(Binaries.FIND)}" . | "{cpio_command}" -o -H newc > "{initrd}"',
            work_directory=staging_area,
        )

        assert os.path.exists(initrd)

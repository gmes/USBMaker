#   Copyright © 2017 Joaquim Monteiro
#
#   This file is part of USBMaker.
#
#   USBMaker is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   USBMaker is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with USBMaker.  If not, see <https://www.gnu.org/licenses/>.

import os
import distutils.dir_util
import subprocess

# os.symlink raises a PermissionError when creating symlinks
# on filesystems that don't support them (FAT32, for example).
#
# This function is overriden so the program continues executing
# when this exception is raised. This is preferred to setting
# preserve_symlinks=0 in the distutils.dir_util.copy_tree function
# because it also avoids recursive symlinks.
orig_symlink = os.symlink


def _symlink(source, link_name, target_is_directory=False, dir_fd=None):
    try:
        orig_symlink(source, link_name, target_is_directory=target_is_directory, dir_fd=dir_fd)
    except PermissionError:
        pass

# This makes any function (distutils.dir_util.copy_tree in particular)
# that uses os.symlink use the _symlink function instead:
# os.symlink = _symlink


def get_bios_bootloader_name(iso_mountpoint):
    if os.path.exists(iso_mountpoint + '/boot/isolinux') or os.path.exists(iso_mountpoint + '/boot/syslinux') or \
       os.path.exists(iso_mountpoint + '/syslinux') or os.path.exists(iso_mountpoint + '/isolinux') or \
       os.path.exists(iso_mountpoint + '/syslinux.cfg') or os.path.exists(iso_mountpoint + '/isolinux.cfg'):
        return 'syslinux'
    elif os.path.exists(iso_mountpoint + '/grub/grldr'):
        return 'grub4dos'
    else:
        return 'unknown'


def get_uefi_bootloader_name(iso_mountpoint):
    if os.path.exists(iso_mountpoint + '/boot/grub/grub.cfg') or \
            os.path.exists(iso_mountpoint + '/efi/boot/grub.cfg'):
        return 'grub2'
    elif os.path.exists(iso_mountpoint + '/loader/loader.conf'):
        return 'systemd-boot'
    else:
        return 'unknown'


def copy_iso_contents(iso_mountpoint, device_mountpoint):
    os.symlink = _symlink
    distutils.dir_util.copy_tree(iso_mountpoint, device_mountpoint, preserve_symlinks=1)
    os.sync()


def create_bootable_usb(device, device_mountpoint, bootloader, target, partition_table,
                        syslinux_mbr='/usr/lib/syslinux/bios'):
    if target.lower() != 'uefi':
        if bootloader[1] == 'syslinux':
            install_syslinux(device, device_mountpoint, partition_table, syslinux_mbr)


def install_syslinux(device, device_mountpoint, partition_table, syslinux_mbr):
    # Change the config files from ISOLINUX to SYSLINUX.
    # SYSLINUX searches for its config file in "/boot/syslinux", "/syslinux" and "/",
    # by this order.
    # The only config file changed should be the first one detected,
    # in order to reduce the modifications made to the iso file's content.

    # /boot/syslinux
    if os.path.exists(device_mountpoint + '/boot/isolinux') and not \
            os.path.exists(device_mountpoint + '/boot/syslinux'):
        os.rename(device_mountpoint + '/boot/isolinux', device_mountpoint + '/boot/syslinux')

    if os.path.exists(device_mountpoint + '/boot/syslinux/isolinux.cfg') and not \
            os.path.exists(device_mountpoint + '/boot/syslinux/syslinux.cfg'):
        os.rename(device_mountpoint + '/boot/syslinux/isolinux.cfg', device_mountpoint + '/boot/syslinux/syslinux.cfg')

    # /syslinux
    if not os.path.exists(device_mountpoint + '/boot/syslinux/syslinux.cfg'):
        if os.path.exists(device_mountpoint + '/isolinux') and not os.path.exists(device_mountpoint + '/syslinux'):
            os.rename(device_mountpoint + '/isolinux', device_mountpoint + '/syslinux')

        if os.path.exists(device_mountpoint + '/syslinux/isolinux.cfg') and not \
                os.path.exists(device_mountpoint + '/syslinux/syslinux.cfg'):
            os.rename(device_mountpoint + '/syslinux/isolinux.cfg', device_mountpoint + '/syslinux/syslinux.cfg')

        # /
        if not os.path.exists(device_mountpoint + '/syslinux/syslinux.cfg'):
            if os.path.exists(device_mountpoint + '/isolinux.cfg') and \
                    not os.path.exists(device_mountpoint + '/syslinux.cfg'):
                os.rename(device_mountpoint + '/isolinux.cfg', device_mountpoint + '/syslinux.cfg')

    # Install SYSLINUX to the partition.
    subprocess.run(['extlinux', '--install', device_mountpoint])

    # Install SYSLINUX to the MBR.
    if partition_table == 'gpt':
        subprocess.run(['dd', 'bs=440', 'count=1', 'if=' + syslinux_mbr + '/gptmbr.bin', 'of=/dev/' + device])
    else:
        subprocess.run(['dd', 'bs=440', 'count=1', 'if=' + syslinux_mbr + '/mbr.bin', 'of=/dev/' + device])

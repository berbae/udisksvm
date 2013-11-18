#!/usr/bin/python
########################################
# Name of the script : udisksvm
# Author : Bernard Baeyens (berbae) 2013
########################################
import os
import sys
import argparse
import subprocess

from gi.repository import UDisks, GLib, Gio

_version = '2.4.2'

BLOCK_DEVICES_PATH = '/org/freedesktop/UDisks2/block_devices/'
OPTICAL_DISK_DEVICE = '/org/freedesktop/UDisks2/block_devices/sr0'
MULTI_MEDIA_CARD_DEVICE = '/org/freedesktop/UDisks2/block_devices/mmcblk0'
JOBS_PATH = '/org/freedesktop/UDisks2/jobs/'

# Used for parameter builder on method call
G_VARIANT_TYPE_VARDICT = GLib.VariantType.new('a{sv}')

parser = argparse.ArgumentParser(description='A GUI UDisks wrapper',
                                 prog='udisksvm')
parser.add_argument('-v', '--version', action='version',
                    version='%(prog)s ' + _version)
parser.add_argument('-a', '--auto',
                    help='enable automounting for non optical disks',
                    action='store_true')
parser.add_argument('-n', '--noauto',
                    help='not used as no automounting is the default',
                    action='store_true')
parser.add_argument('-s', '--silent',
                    help='disable notification popup messages',
                    action='store_true')
parser.add_argument('-d', '--debug',
                    help='show internal infos',
                    action='store_true')

args = parser.parse_args()

# Set verbosity
debug = args.debug
if debug:
    F_OUT = sys.stdout
    F_ERR = sys.stderr
else:
    F_OUT = F_ERR = subprocess.DEVNULL

automount = args.auto
print('-' * 50)
if automount:
    print('Automounting for non optical devices enabled')
else:
    print('Automounting disabled')
print('-' * 50)

popup = not args.silent
if popup:
    print('notifications enabled')
else:
    print('notifications disabled')
print('-' * 50)

# Check traydvm availability
try:
    traydvm_script = subprocess.check_output(['which', 'traydvm'],
                                             stderr=F_ERR)
except subprocess.CalledProcessError:
    print("The 'traydvm' utility is not found...")
    print('-' * 50)
    sys.exit(1)
else:
    # Need to decode the byte string output
    traydvm_script = traydvm_script[:-1].decode()
    if debug:
        print('Found ', traydvm_script)
        print('-' * 50)
    if popup:
        traydvm_cmd = traydvm_script + ' '
    else:
        traydvm_cmd = traydvm_script + ' --silent '

loop = GLib.MainLoop()


def run_traydvm(obj_path):
    if subprocess.call(['pgrep', '-f', traydvm_cmd + obj_path],
                       stdout=F_OUT, stderr=F_ERR):
        if popup:
            traydvm_seq = [traydvm_script, obj_path]
        else:
            traydvm_seq = [traydvm_script, '--silent', obj_path]

        try:
            trayd = subprocess.Popen(traydvm_seq, stdout=F_OUT, stderr=F_ERR)
        except OSError as err:
            print('Launching traydvm for', obj_path, 'failed with error :')
            print(err.strerror, '(errno :', str(err.errno) + ')')
        else:
            print('traydvm for', obj_path, 'now running with pid :', trayd.pid)
        print('-' * 50)
    elif debug:
        print('traydvm for', obj_path, 'is already running...')
        print('-' * 50)


def kill_traydvm(obj_path):
    if subprocess.call(['pgrep', '-f', traydvm_cmd + obj_path],
                       stdout=F_OUT, stderr=F_ERR):
        if debug:
            print('traydvm for', obj_path, 'is not running...')
            print('-' * 50)
    else:
        try:
            subprocess.call(['pkill', '-SIGINT', '-f', traydvm_cmd + obj_path],
                            stdout=F_OUT, stderr=F_ERR)
        except OSError as err:
            print('Killing traydvm for', obj_path, 'failed with error :')
            print(err.strerror, '(errno :', str(err.errno) + ')')
        else:
            print('traydvm for', obj_path, 'now killed')
        print('-' * 50)


def action_on_object(on_object, interface_added):
    obj_path = on_object.get_object_path()
    if not obj_path.startswith(JOBS_PATH):
        if interface_added is None:
            print('Added object : ' + obj_path)
        else:
            print('Added interface on object : ' + obj_path)
        print('-' * 50)
    # Act only on non optical disk block devices
    if (not obj_path.startswith(BLOCK_DEVICES_PATH) or
            obj_path == OPTICAL_DISK_DEVICE):
        return

    iblock = on_object.get_block()
    if iblock is not None:
        devicefile = iblock.get_cached_property('Device')
        devicefile = devicefile.get_bytestring()
        devicefile = devicefile.decode()
        idtype = iblock.get_cached_property('IdType')
        idtype = idtype.get_string()
        hintsystem = iblock.get_cached_property('HintSystem')
        hintsystem = hintsystem.get_boolean()
        if debug:
            print('devicefile =', devicefile)
            print('idtype =', idtype)
            print('-' * 50)
        if hintsystem and not obj_path.startswith(MULTI_MEDIA_CARD_DEVICE):
            print('System device is not managed here')
            print('-' * 50)
            return

    ifilesystem = on_object.get_filesystem()
    if ifilesystem is not None:
        # Don't act if an added interface is not a Filesystem interface
        if (interface_added is not None) and (interface_added != ifilesystem):
            print('No action')
            print('-' * 50)
            return

        if automount:
            print('Automounting', devicefile + '...')
            # default value when there is no Partition interface
            iscontainer = iscontained = False

            ipartition = on_object.get_partition()
            if ipartition is not None:
                iscontainer = ipartition.get_cached_property('IsContainer')
                iscontainer = iscontainer.get_boolean()
                iscontained = ipartition.get_cached_property('IsContained')
                iscontained = iscontained.get_boolean()
                if debug:
                    print('iscontainer =', iscontainer)
                    print('iscontained =', iscontained)
                    print('-' * 50)

            if not (iscontainer or iscontained):
                fstype = idtype
                list_options = ''
                if fstype == 'vfat':
                    list_options = 'flush'
                elif fstype == 'ext2':
                    list_options = 'sync'

                # Used to build the parameter GVariant of type a{sv}
                # for call_mount_sync()
                param_builder = GLib.VariantBuilder.new(G_VARIANT_TYPE_VARDICT)

                optname = GLib.Variant.new_string('fstype')             # s
                value = GLib.Variant.new_string(fstype)
                vvalue = GLib.Variant.new_variant(value)                # v
                newsv = GLib.Variant.new_dict_entry(optname, vvalue)    # {sv}
                param_builder.add_value(newsv)

                optname = GLib.Variant.new_string('options')
                value = GLib.Variant.new_string(list_options)
                vvalue = GLib.Variant.new_variant(value)
                newsv = GLib.Variant.new_dict_entry(optname, vvalue)
                param_builder.add_value(newsv)

                vparam = param_builder.end()                            # a{sv}

                try:
                    mountpath = ifilesystem.call_mount_sync(vparam, None)
                except GLib.GError:
                    value = sys.exc_info()[1]
                    print('Mounting failed with error:')
                    print(value)
                else:
                    print('Mounting done at mountpath:', mountpath)
            else:
                print('Failed:not mounting a container or contained partition')

            print('-' * 50)
        run_traydvm(obj_path)


def handler_on_object_added(manager, object_added, udata):
    action_on_object(object_added, None)


def handler_on_interface_added(manager, on_object, interface_added, udata):
    action_on_object(on_object, interface_added)


def handler_on_object_removed(manager, object_removed, udata):
    obj_path = object_removed.get_object_path()
    if not obj_path.startswith(JOBS_PATH):
        print('Removed : ', obj_path)
        print('-' * 50)
    if obj_path.startswith(BLOCK_DEVICES_PATH):
        kill_traydvm(obj_path)


def handler_on_changed(client, udata):
    # Called on every changes but look only at optical disks
    global hasmedia, opticaldisk, numaudio

    hasmedia_now = idrive_optical.get_cached_property('MediaAvailable')
    hasmedia_now = hasmedia_now.get_boolean()
    opticaldisk_now = idrive_optical.get_cached_property('Optical')
    opticaldisk_now = opticaldisk_now.get_boolean()
    numaudio_now = idrive_optical.get_cached_property('OpticalNumAudioTracks')
    numaudio_now = numaudio_now.get_uint32()

    if ((hasmedia != hasmedia_now) or (opticaldisk != opticaldisk_now) or
            (numaudio != numaudio_now)):
        hasmedia = hasmedia_now
        opticaldisk = opticaldisk_now
        numaudio = numaudio_now
        if debug:
            print('hasmedia =', hasmedia)
            print('opticaldisk =', opticaldisk)
            print('numaudio =', numaudio)
            print('-' * 50)

        if hasmedia:
            if opticaldisk and not numaudio:
                run_traydvm(OPTICAL_DISK_DEVICE)
        else:
            kill_traydvm(OPTICAL_DISK_DEVICE)

#############################################################
# Connect to UDisks
client = UDisks.Client.new_sync(None)

# Central communication with DBus
manager = client.get_object_manager()

# Invariable channels for optical disk
proxy = manager.get_object(OPTICAL_DISK_DEVICE)
if proxy is not None:
    iblock_optical = proxy.get_block()

    drive = iblock_optical.get_cached_property('Drive')
    drive = drive.get_string()
    if debug:
        print('optical drive =', drive)
        print('-' * 50)

    proxy = manager.get_object(drive)
    idrive_optical = proxy.get_drive()

    hasmedia = idrive_optical.get_cached_property('MediaAvailable')
    hasmedia = hasmedia.get_boolean()
    opticaldisk = idrive_optical.get_cached_property('Optical')
    opticaldisk = opticaldisk.get_boolean()
    numaudio = idrive_optical.get_cached_property('OpticalNumAudioTracks')
    numaudio = numaudio.get_uint32()

    # Detect disk insertion/removal
    client.connect("changed", handler_on_changed, None)

# Connect to signals
manager.connect("object-added", handler_on_object_added, None)
manager.connect("object-removed", handler_on_object_removed, None)
manager.connect("interface-added", handler_on_interface_added, None)
# The "interface-added" signal is needed if the Filesystem interface appears
# on an already added object.

#############################################################
try:
    loop.run()
except KeyboardInterrupt:
    print('-' * 22, 'Bye!', '-' * 22)
    loop.quit()

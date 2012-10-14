#!/usr/bin/python
########################################
# Name of the script : udisksvm
# Author : Bernard Baeyens (berbae) 2012
########################################
import os, sys, signal
import argparse
import subprocess
from gi.repository import UDisks, GLib, Gio
import gi

_version = '2.2'

optical_disk_device = '/org/freedesktop/UDisks2/block_devices/sr0'

# Used for parameter builder on method call
G_VARIANT_TYPE_VARDICT = GLib.VariantType.new('a{sv}')

parser = argparse.ArgumentParser(description='A GUI UDisks wrapper', prog='udisksvm')
parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + _version)
parser.add_argument('-n', '--noauto', help='do not automount',
                    action='store_true')
parser.add_argument('-d', '--debug', help='show internal infos',
                    action='store_true')

args = parser.parse_args()

# Set verbosity
devnull = os.open(os.devnull, os.O_WRONLY)

debug = args.debug
if debug:
    F_OUT = sys.stdout
    F_ERR = sys.stderr
else:
    F_OUT = F_ERR = devnull

# Check traydvm availability
try:
    traydvm_script = subprocess.check_output(['which', 'traydvm'], stderr=F_ERR)
except subprocess.CalledProcessError:
    print("The 'traydvm' utility is not found...")
    sys.exit(1)
else:
    # Need to decode the byte string output
    traydvm_script = traydvm_script[:-1].decode()

automount = not args.noauto
print('-'*50)
if automount:
    print('Automounting for non optical devices enabled')
else:
    print('Automounting disabled')
print('-'*50)

loop = GLib.MainLoop()

def signal_handler(signum, frame):
    print('*'*5, 'signal', signum, 'received', '*'*5)
    print('-'*22, 'Bye!', '-'*22)
    loop.quit()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGQUIT, signal_handler)

#############################################################
def run_traydvm(obj_path):
    if subprocess.call(['pgrep', '-f', traydvm_script + ' ' + obj_path], stdout=F_OUT, stderr=F_ERR):
        try:
            trayd = subprocess.Popen([traydvm_script, obj_path], stdout=F_OUT, stderr=F_ERR)
        except OSError as err:
            print('Launching traydvm for', obj_path, 'failed with error :')
            print(err.strerror, '(errno :', str(err.errno) + ')')
        else:
            print('traydvm for', obj_path, 'now running with pid :', trayd.pid)
        print('-'*50)
    elif debug:
        print('traydvm for', obj_path, 'is already running...')
        print('-'*50)

#############################################################
def kill_traydvm(obj_path):
    if subprocess.call(['pgrep', '-f', traydvm_script + ' ' + obj_path], stdout=F_OUT, stderr=F_ERR):
        if debug:
            print('traydvm for', obj_path, 'is not running...')
            print('-'*50)
    else:
        try:
            subprocess.call(['pkill', '-f', traydvm_script + ' ' + obj_path], stdout=F_OUT, stderr=F_ERR)
        except OSError as err:
            print('Killing traydvm for', obj_path, 'failed with error :')
            print(err.strerror, '(errno :', str(err.errno) + ')')
        else:
            print('traydvm for', obj_path, 'now killed')
        print('-'*50)

#############################################################
def action_on_object(on_object, interface_added):
    obj_path = on_object.get_object_path()
    print(obj_path)
    print('-'*50)

    # optical disk is not managed here
    if obj_path == optical_disk_device:
        return

    iblock = on_object.get_interface('org.freedesktop.UDisks2.Block')

    if iblock:

        devicefile = iblock.get_cached_property('Device').get_bytestring()
        devicefile = devicefile.decode()
        idtype = iblock.get_cached_property('IdType').get_string()

        if debug:
            print('devicefile =', devicefile)
            print('idtype =', idtype)
            print('-'*50)

    ifilesystem = on_object.get_interface('org.freedesktop.UDisks2.Filesystem')

    if ifilesystem:

        # Don't act if an added interface is not a Filesystem interface
        if interface_added and not (interface_added == ifilesystem):
            print('No action')
            print('-'*50)
            return

        if automount:
            print('Automounting', devicefile + '...')

            # default value when there is no Partition interface
            iscontainer = iscontained = False

            ipartition = on_object.get_interface('org.freedesktop.UDisks2.Partition')

            if ipartition:

                iscontainer = ipartition.get_cached_property('IsContainer').get_boolean()
                iscontained = ipartition.get_cached_property('IsContained').get_boolean()

                if debug:
                    print('iscontainer =', iscontainer)
                    print('iscontained =', iscontained)
                    print('-'*50)

            if not (iscontainer or iscontained):

                if idtype == "vfat":
                    fstype = idtype
                    #list_options = 'flush, utf8=0'
                    list_options = 'flush'
                elif idtype == "ntfs":
                    fstype = "ntfs-3g"
                    list_options = ''
                else:
                    fstype = idtype
                    list_options = ''

                # Used to build the parameter GVariant of type (a{sv}) for call_sync
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
                vtparam = GLib.Variant.new_tuple(vparam)                # (a{sv})

                try:
                    mountpath = ifilesystem.call_sync('Mount', vtparam, Gio.DBusCallFlags.NONE, -1, None)
                    mountpath = mountpath.unpack()[0]
                except gi._glib.GError:
                    value = sys.exc_info()[1]
                    print('Mounting failed with error:')
                    print(value)
                else:
                    print('Mounting done at mountpath:', mountpath)

            else:
                print('Failed: not mounting a container or contained partition')

            print('-'*50)

        run_traydvm(obj_path)

#############################################################
def handler_on_object_added(manager, object_added, udata):
    print('Added object : ', end='')

    action_on_object(object_added, None)

#############################################################
def handler_on_interface_added(manager, on_object, interface_added, udata):
    print('Added interface on object : ', end='')

    action_on_object(on_object, interface_added)

#############################################################
def handler_on_object_removed(manager, object_removed, udata):
    obj_path = object_removed.get_object_path()
    print('Removed : ', obj_path)
    print('-'*50)

    kill_traydvm(obj_path)

#############################################################
def handler_on_changed(client, udata):
    # Called on every changes but look only at optical disks 
    global hasmedia, opticaldisk, audiotracks

    hasmedia_now = idrive_optical.get_cached_property('MediaAvailable').get_boolean()
    opticaldisk_now = idrive_optical.get_cached_property('Optical').get_boolean()
    audiotracks_now = idrive_optical.get_cached_property('OpticalNumAudioTracks').get_uint32()

    if (hasmedia != hasmedia_now) or (opticaldisk != opticaldisk_now) or (audiotracks != audiotracks_now):
        hasmedia = hasmedia_now
        opticaldisk = opticaldisk_now
        audiotracks = audiotracks_now

        if debug:
            print('hasmedia =', hasmedia)
            print('opticaldisk =', opticaldisk)
            print('audiotracks =', audiotracks)
            print('-'*50)

        if hasmedia:
            if opticaldisk and not audiotracks:
                run_traydvm(optical_disk_device)
        else:
            kill_traydvm(optical_disk_device)

#############################################################
# Connect to UDisks
client = UDisks.Client.new_sync(None)

# Central communication with DBus
manager = client.get_object_manager()

# Invariable channels for optical disk
proxy = manager.get_object(optical_disk_device)
if proxy:
    iblock_optical = proxy.get_interface('org.freedesktop.UDisks2.Block')

    drive = iblock_optical.get_cached_property('Drive').get_string()
    if debug:
        print('optical drive =', drive)
        print('-'*50)

    proxy = manager.get_object(drive)
    idrive_optical = proxy.get_interface('org.freedesktop.UDisks2.Drive')

    hasmedia = idrive_optical.get_cached_property('MediaAvailable').get_boolean()
    opticaldisk = idrive_optical.get_cached_property('Optical').get_boolean()
    audiotracks = idrive_optical.get_cached_property('OpticalNumAudioTracks').get_uint32()

    # Detect disk insertion/removal
    client.connect("changed", handler_on_changed, None)
    # The "interface-proxy-properties-changed" signal is not used
    # because it causes a memory error in python

# Connect to signals
manager.connect("object-added", handler_on_object_added, None)
manager.connect("object-removed", handler_on_object_removed, None)
manager.connect("interface-added", handler_on_interface_added, None)
# The "interface-added" signal is needed if the Filesystem interface appears on an already added object

loop.run()

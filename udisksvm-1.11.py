#!/usr/bin/python
########################################
# Name of the script : udisksvm
# Author : Bernard Baeyens (berbae) 2012
########################################
import sys, os
import argparse
import signal
import subprocess
from gi.repository import Gio, GLib
import gi


_version = '1.11'

optical_disk_device = '/org/freedesktop/UDisks/devices/sr0'

parser = argparse.ArgumentParser(description='A GUI UDisks wrapper', prog='udisksvm')
parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + _version)
parser.add_argument('-n', '--noauto', help='do not automount',
                    action='store_true')
parser.add_argument('-d', '--debug', help='show internal infos',
                    action='store_true')

args = parser.parse_args()

devnull = os.open(os.devnull, os.O_WRONLY)

# Set verbosity
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

def dbus_handler(connexion, sender, pobject, interface, signal, gparam, udata):
    device = gparam.unpack()[0]
    print(signal, 'received from', device)
    print('-'*50)
    if signal in ['DeviceAdded', 'DeviceChanged']:
        # Connect to UDisks DBus API and fetch device properties
        proproxy = Gio.DBusProxy.new_sync(bus, 0, None, 'org.freedesktop.UDisks',
                                          device, 'org.freedesktop.DBus.Properties', None)
        props = proproxy.GetAll('(s)', 'org.freedesktop.UDisks.Device')

        systeminternal = props['DeviceIsSystemInternal']
        devicefile = props['DeviceFile']
        usage = props['IdUsage']
        ismounted = props['DeviceIsMounted']
        hasmedia = props['DeviceIsMediaAvailable']
        opticaldisk = props['DeviceIsOpticalDisc']
        numaudiotracks = props['OpticalDiscNumAudioTracks']
        isclosed = props['OpticalDiscIsClosed']
        idtype = props['IdType']
        partition = props['DeviceIsPartition']

        if debug:
            print('systeminternal =', systeminternal)
            print('devicefile =', devicefile)
            print('usage =', usage)
            print('ismounted =', ismounted)
            print('hasmedia =', hasmedia)
            print('opticaldisk =', opticaldisk)
            print('numaudiotracks =', numaudiotracks)
            print('isclosed =', isclosed)
            print('idtype =', idtype)
            print('partition =', partition)
            print('-'*50)

    def run_traydvm():
        if subprocess.call(['pgrep', '-f', traydvm_script + ' ' + device], stdout=F_OUT, stderr=F_ERR):
            try:
                trayd = subprocess.Popen([traydvm_script, device], stdout=F_OUT, stderr=F_ERR)
            except OSError as err:
                print('Launching traydvm for', device, 'failed with error :')
                print(err.strerror, '(errno :', str(err.errno) + ')')
            else:
                print('traydvm for', device, 'now running with pid :', trayd.pid)
        else:
            print('traydvm for', device, 'is already running...')

        print('-'*50)

    def kill_traydvm():
        if subprocess.call(['pgrep', '-f', traydvm_script + ' ' + device], stdout=F_OUT, stderr=F_ERR):
            print('traydvm for', device, 'is not running...')
            print('-'*50)
        elif not subprocess.call(['pkill', '-f', traydvm_script + ' ' + device], stdout=F_OUT, stderr=F_ERR):
            print('traydvm for', device, 'now killed')
            print('-'*50)

    if signal == 'DeviceAdded':
        if not systeminternal and (usage == "filesystem") and partition:
            if automount:
                print('Automounting', devicefile + '...')

                if idtype == "vfat":
                    fstype = idtype
                    options = ["flush", "noatime", "nodiratime", "noexec", "nodev", "utf8=0"]
                elif idtype == "ntfs":
                    fstype = "ntfs-3g"
                    options = ["noatime", "nodiratime", "exec"]
                else:
                    fstype = idtype
                    options = ["sync", "noatime", "nodiratime", "noexec", "nodev"]

                try:
                    devproxy = Gio.DBusProxy.new_sync(bus, 0, None, 'org.freedesktop.UDisks',
                                                      device, 'org.freedesktop.UDisks.Device', None)
                    mountpath = devproxy.FilesystemMount('(sas)', fstype, options)
                    # mountpath is a dbus.String
                except gi._glib.GError:
                    value = sys.exc_info()[1]
                    print('failed with error :')
                    print(value)
                else:
                    print('done at mountpath :', mountpath)

                print('-'*50)

            run_traydvm()

    elif signal == 'DeviceChanged':
        if not systeminternal:
            if opticaldisk and hasmedia and not numaudiotracks:
                run_traydvm()
            elif (opticaldisk and not isclosed) or not hasmedia:
                kill_traydvm() 

    elif signal == 'DeviceRemoved':
        kill_traydvm()

# Connect to DBus system instance
bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

# Creating the proxy for optical disk device is required to start the necessary polling for optical disk events
optproxy = Gio.DBusProxy.new_sync(bus, 0, None, 'org.freedesktop.UDisks', optical_disk_device,
                                  'org.freedesktop.UDisks.Device', None)

bus.signal_subscribe(None, 'org.freedesktop.UDisks', None, None, None, Gio.DBusSignalFlags.NONE, dbus_handler, None)

loop.run()


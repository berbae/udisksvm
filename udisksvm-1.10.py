#!/usr/bin/python
########################################
# Name of the script : udisksvm
# Author : Bernard Baeyens (berbae) 2012
########################################
import sys, os
import argparse

_version = '1.10'

default_traydconf = '/usr/share/udisksvm/udisksvm.xml'
optical_disk_device = '/org/freedesktop/UDisks/devices/sr0'

parser = argparse.ArgumentParser(description='A GUI UDisks wrapper', prog='udisksvm',
                                 formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + _version)
parser.add_argument('-n', '--noauto', help='do not automount',
                    action='store_true')
parser.add_argument('-d', '--debug', help='show internal infos',
                    action='store_true')
parser.add_argument('traydconf', nargs='?', default=default_traydconf,
                    help='''\
configuration file for traydevice
(default: %(default)s)''')

args = parser.parse_args()

# configuration file for traydevice
TRAYCONF = args.traydconf
if not os.path.exists(TRAYCONF):
    print("The traydevice configuration file '" + TRAYCONF + "' is not found...")
    sys.exit(1)

showinfos = args.debug
automount = not args.noauto
print('-'*50)
if automount:
    print('Automounting for non optical devices enabled')
else:
    print('Automounting disabled')
print('-'*50)

import signal
import subprocess
from gi.repository import Gio, GLib

loop = GLib.MainLoop()

devnull = os.open(os.devnull, os.O_WRONLY)

def signal_handler(signum, frame):
    print('*'*5, 'signal', signum, 'received', '*'*5)
    print('-'*22, 'Bye!', '-'*22)
    loop.quit()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGQUIT, signal_handler)
signal.signal(signal.SIGHUP, signal.SIG_IGN)

def dbus_handler(connexion, sender, pobject, interface, signal, gparam, udata):
    device = gparam.unpack()[0]
    print(signal, 'received from', device)
    print('-'*50)
    if signal in ['DeviceAdded', 'DeviceChanged']:
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
        idtype = props['IdType']
        partition = props['DeviceIsPartition']
        if showinfos:
            print('systeminternal =', systeminternal)
            print('devicefile =', devicefile)
            print('usage =', usage)
            print('ismounted =', ismounted)
            print('hasmedia =', hasmedia)
            print('opticaldisk =', opticaldisk)
            print('numaudiotracks =', numaudiotracks)
            print('idtype =', idtype)
            print('partition =', partition)
            print('-'*50)

    if signal == 'DeviceAdded':
        if  not systeminternal and (usage == "filesystem") and partition:
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
                except dbus.exceptions.DBusException:
                    value = sys.exc_info()[1]
                    print('failed with error :', value)
                else:
                    print('done at mountpath :', mountpath)

                print('-'*50)

            if subprocess.call(['pgrep', '-f', 'traydevice -c ' + TRAYCONF + ' ' + devicefile], stdout=devnull, stderr=devnull):
                try:
                    trayd = subprocess.Popen(["traydevice", "-c", TRAYCONF, devicefile], stdout=devnull, stderr=devnull)
                except OSError as err:
                    print('Launching traydevice for', devicefile, 'failed with error :')
                    print(err.strerror, '(errno :', str(err.errno) + ')')
                else:
                    print('traydevice for', devicefile, 'now running with pid :', trayd.pid)
            else:
                print('traydevice for', devicefile, 'is already running...')

            print('-'*50)

    elif signal == 'DeviceChanged':
        if  not systeminternal and opticaldisk and hasmedia and not numaudiotracks:
            if subprocess.call(['pgrep', '-f', 'traydevice -c ' + TRAYCONF + ' ' + devicefile], stdout=devnull, stderr=devnull):
                try:
                    trayd = subprocess.Popen(["traydevice", "-c", TRAYCONF, devicefile], stdout=devnull, stderr=devnull)
                except OSError as err:
                    print('Launching traydevice for', devicefile, 'failed with error :')
                    print(err.strerror, '(errno :', str(err.errno) + ')')
                else:
                    print('traydevice for', devicefile, 'now running with pid :', trayd.pid)
            else:
                print('traydevice for', devicefile, 'is already running...')

            print('-'*50)
    elif signal == 'DeviceRemoved':
        pass

bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

# Creating the proxy for sr0 is required to launch the necessary polling
optproxy = Gio.DBusProxy.new_sync(bus, 0, None, 'org.freedesktop.UDisks', optical_disk_device,
                                  'org.freedesktop.UDisks.Device', None)

isubsc = bus.signal_subscribe(None, 'org.freedesktop.UDisks', None, None, None, Gio.DBusSignalFlags.NONE, dbus_handler, None)

loop.run()


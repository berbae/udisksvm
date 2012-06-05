#!/usr/bin/python2
########################################
# Name of the script : udisksvm
# Author : Bernard Baeyens (berbae) 2012
########################################
import sys
import signal
import subprocess
import dbus
import gobject

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

# configuration file for traydevice
TRAYCONF = "/usr/share/udisksvm/udisksvm.xml"

def signal_handler(signum, frame):
    print '*'*5, 'signal', signum, 'received', '*'*5
    print '-'*22, 'Bye!', '-'*22
    loop.quit()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGQUIT, signal_handler)
signal.signal(signal.SIGHUP, signal.SIG_IGN)

def dbus_handler(device, *args, **kwargs):
    signal = kwargs['member']
    print '-'*50
    print signal, 'received from', device
    print '-'*50
    if signal in ['DeviceAdded', 'DeviceChanged']:
	devproxy = bus.get_object('org.freedesktop.UDisks', device)

	props = devproxy.GetAll('org.freedesktop.UDisks.Device', dbus_interface='org.freedesktop.DBus.Properties')

	systeminternal = props['DeviceIsSystemInternal']
	devicefile = props['DeviceFile']
	usage = props['IdUsage']
	ismounted = props['DeviceIsMounted']
	hasmedia = props['DeviceIsMediaAvailable']
	opticaldisk = props['DeviceIsOpticalDisc']
	numaudiotracks = props['OpticalDiscNumAudioTracks']
	idtype = props['IdType']
	partition = props['DeviceIsPartition']

#	print '-'*50
#	print 'systeminternal =', systeminternal
#	print 'devicefile =', devicefile
#	print 'usage =', usage
#	print 'ismounted =', ismounted
#	print 'hasmedia =', hasmedia
#	print 'opticaldisk =', opticaldisk
#	print 'numaudiotracks =', numaudiotracks
#	print 'idtype =', idtype
#	print 'partition =', partition
#	print '-'*50

    if signal == 'DeviceAdded':
	if  not systeminternal and (usage == "filesystem") and partition:
	    if subprocess.call(['pgrep', '-f', 'traydevice -c ' + TRAYCONF + ' ' + devicefile]):
		print 'automounting', devicefile + '...'
		if idtype == "vfat":
		    fstype = idtype
		    options = ["flush", "noatime", "nodiratime", "noexec", "nodev", "utf8=0"]
		elif idtype == "ntfs":
		    fstype = "ntfs-3g"
		    options = ["noatime", "nodiratime", "exec"]
		else:
		    fstype = idtype
		    options = ["sync", "noatime", "nodiratime", "noexec", "nodev"]
		mountpath = devproxy.FilesystemMount(fstype, options, dbus_interface='org.freedesktop.UDisks.Device')
		# mountpath is a dbus.String
		print 'done at mountpath :', mountpath
		traydfs = subprocess.Popen(["/usr/bin/traydevice", "-c", TRAYCONF, devicefile])
		print 'traydevice for', devicefile, 'now running with pid :', traydfs.pid
		print '-'*50
    elif signal == 'DeviceChanged':
	if  not systeminternal and opticaldisk and hasmedia and not numaudiotracks:
	    if subprocess.call(['pgrep', '-f', 'traydevice -c ' + TRAYCONF + ' ' + devicefile]):
		traydoptic = subprocess.Popen(["/usr/bin/traydevice", "-c", TRAYCONF, devicefile])
		print 'traydevice for', devicefile, 'now running with pid :', traydoptic.pid
		print '-'*50
    elif signal == 'DeviceRemoved':
	pass

bus = dbus.SystemBus()

bus.add_signal_receiver(dbus_handler, dbus_interface='org.freedesktop.UDisks', member_keyword='member')

loop = gobject.MainLoop()
loop.run()


#!/usr/bin/python
########################################
# Name of the script : traydvm
# Author : Bernard Baeyens (berbae) 2012
########################################
import sys, os, re
import argparse
import signal
from gi.repository import Gio, GLib, Gtk
import gi

parser = argparse.ArgumentParser(description='A systray utility for udisksvm')

parser.add_argument('device', help='The device to use')

args = parser.parse_args()

device = args.device

# Use GLib MainLoop for signal_handler to quit after signal detection
loop = GLib.MainLoop()

def signal_handler(signum, frame):
    print('*'*5, 'signal', signum, 'received', '*'*5)
    print('-'*22, 'Bye!', '-'*22)
    loop.quit()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGQUIT, signal_handler)

# Connect to UDisks DBus API and fetch device properties
bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

devproxy = Gio.DBusProxy.new_sync(bus, 0, None, 'org.freedesktop.UDisks', device,
                                  'org.freedesktop.UDisks.Device', None)
proproxy = Gio.DBusProxy.new_sync(bus, 0, None, 'org.freedesktop.UDisks', device,
                                  'org.freedesktop.DBus.Properties', None)
try:
    props = proproxy.GetAll('(s)', 'org.freedesktop.UDisks.Device')
except gi._glib.GError:
    value = sys.exc_info()[1]
    print('Could not receive properties for device :', device)
    print('The error is :')
    print(value)
    sys.exit(1)

devicefile = props['DeviceFile']
usage = props['IdUsage']
uuid = props['IdUuid']
label = props['IdLabel']
ismounted = props['DeviceIsMounted']
opticaldisk = props['DeviceIsOpticalDisc']
idtype = props['IdType']

# Create systray icon
if opticaldisk:
    stockitem = Gtk.STOCK_CDROM
else:
    stockitem = Gtk.STOCK_HARDDISK

if label:
    tooltip = label
else:
    tooltip = uuid

trayicon = Gtk.StatusIcon()
trayicon.set_from_stock(stockitem)
trayicon.set_tooltip_text(tooltip)

# Create handler for popup menu actions
def on_menu_click(widget):
    action = widget.get_name()
    if action == "Mount":
        if opticaldisk:
            fstype = idtype
            options = ["ro", "noatime", "nodiratime", "noexec", "nodev"]
        elif idtype == 'vfat':
            fstype = idtype
            options = ["flush", "noatime", "nodiratime", "noexec", "nodev", "utf8=0"]
        elif idtype == "ntfs":
            fstype = "ntfs-3g"
            options = ["noatime", "nodiratime", "exec"]
        else:
            fstype = idtype
            options = ["sync", "noatime", "nodiratime", "noexec", "nodev"]

        print('Mounting', devicefile + '...')
        try:
            mountpath = devproxy.FilesystemMount('(sas)', fstype, options)
        except gi._glib.GError:
            value = sys.exc_info()[1]
            print('failed with error :')
            print(value)
        else:
            print('done at mountpath :', mountpath)

    elif action == "Unmount":
        options = []
        print('Unmounting', devicefile + '...')
        try:
            devproxy.FilesystemUnmount('(as)', options)
        except gi._glib.GError:
            value = sys.exc_info()[1]
            print('failed with error :')
            print(value)
        else:
            print('done')
            
    elif opticaldisk:
        if ismounted:
            options = ["unmount"]
        else:
            options = []
        print('Ejecting', devicefile + '...')
        try:
            devproxy.DriveEject('(as)', options)
        except gi._glib.GError:
            value = sys.exc_info()[1]
            print('failed with error :')
            print(value)
        else:
            print('done')

# Create actions for the popup menu
title = re.sub('_', '__',tooltip) # To prevent using '_' for mnemonic letters in label
action_title = Gtk.Action("Title", "      " + title + "      ", None, None)
action_mount = Gtk.Action("Mount", "Mount", None, Gtk.STOCK_ADD)
action_mount.connect("activate", on_menu_click)
action_unmount = Gtk.Action("Unmount", "Unmount", None, Gtk.STOCK_REMOVE)
action_unmount.connect("activate", on_menu_click)
action_eject = Gtk.Action("Eject", "Eject", None, Gtk.STOCK_REMOVE)
action_eject.connect("activate", on_menu_click)

action_group = Gtk.ActionGroup("popup_actions")
action_group.add_action(action_title)
action_group.add_action(action_mount)
action_group.add_action(action_unmount)
action_group.add_action(action_eject)

# Ejection is always available for optical disks
action_eject.set_sensitive(opticaldisk)

# Refresh properties which may have changed from user actions
def setup_sensitive():
    global props, usage, label, ismounted, idtype, tooltip
    props = proproxy.GetAll('(s)', 'org.freedesktop.UDisks.Device')
    usage = props['IdUsage']
    label = props['IdLabel']
    ismounted = props['DeviceIsMounted']
    idtype = props['IdType']

    action_mount.set_sensitive(not ismounted and (usage == 'filesystem'))
    action_unmount.set_sensitive(ismounted)

    if label and (tooltip != label):
        tooltip = label
        trayicon.set_tooltip_text(tooltip)

# Popup menu layout and creation
UI_INFO = """
<ui>
<popup name='udisksvm'>
    <menuitem action='Title' />
    <separator />
    <menuitem action='Mount' />
    <menuitem action='Unmount' />
    <menuitem action='Eject' />
  </popup>
</ui>
"""
uiManager = Gtk.UIManager()
uiManager.add_ui_from_string(UI_INFO)
uiManager.insert_action_group(action_group)

# Connect systray icon to popup menu
def popup_menu(status_icon, button, activate_time, menu):
    setup_sensitive()
    menu.popup(None, None, status_icon.position_menu, status_icon, button, activate_time)
            
trayicon.connect('popup-menu', popup_menu, uiManager.get_widget('/ui/udisksvm'))

loop.run()


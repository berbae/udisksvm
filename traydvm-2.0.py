#!/usr/bin/python
########################################
# Name of the script : traydvm
# Author : Bernard Baeyens (berbae) 2012
########################################
import sys, os, re
import argparse
import signal
from gi.repository import UDisks, GLib, Gio, Gtk
import gi

optical_disk_device = '/org/freedesktop/UDisks2/block_devices/sr0'

# Used for parameter builder on method call
G_VARIANT_TYPE_VARDICT = GLib.VariantType.new('a{sv}')

parser = argparse.ArgumentParser(description='A systray utility for udisksvm')

parser.add_argument('object_path', help='The object to use')

args = parser.parse_args()

obj_path = args.object_path

# Use GLib MainLoop for signal_handler to quit after signal detection
loop = GLib.MainLoop()

def signal_handler(signum, frame):
    print('*'*5, 'signal', signum, 'received', '*'*5)
    print('-'*22, 'Bye!', '-'*22)
    loop.quit()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGQUIT, signal_handler)

# Connect to UDisks
client = UDisks.Client.new_sync(None)

# Central communication with DBus
manager = client.get_object_manager()

proxy = manager.get_object(obj_path)
iblock = proxy.get_interface('org.freedesktop.UDisks2.Block')

devicefile = iblock.get_cached_property('Device').get_bytestring()
devicefile = devicefile.decode()
drive = iblock.get_cached_property('Drive').get_string()
usage = iblock.get_cached_property('IdUsage').get_string()
idtype = iblock.get_cached_property('IdType').get_string()
label = iblock.get_cached_property('IdLabel').get_string()
uuid = iblock.get_cached_property('IdUUID').get_string()

ifilesystem = proxy.get_interface('org.freedesktop.UDisks2.Filesystem')

if ifilesystem:
    mountpoints = ifilesystem.get_cached_property('MountPoints').get_bytestring_array()
else:
    mountpoints = []

if mountpoints:
    ismounted = True
else:
    ismounted = False

if obj_path == optical_disk_device:
    # Drive interface needed for Eject
    proxy = manager.get_object(drive)
    idrive_optical = proxy.get_interface('org.freedesktop.UDisks2.Drive')

    opticaldisk = True
else:
    opticaldisk = False

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

    # Used to build the parameter GVariant of type (a{sv}) for call_sync "Mount", "Unmount", "Eject"
    param_builder = GLib.VariantBuilder.new(G_VARIANT_TYPE_VARDICT)

    action = widget.get_name()
    if action == "Mount":

        if idtype == 'vfat':
            fstype = idtype
            list_options = 'flush'
        elif idtype == "ntfs":
            fstype = "ntfs-3g"
            list_options = ''
        else:
            fstype = idtype
            list_options = ''

        optname = GLib.Variant.new_string('fstype')
        value = GLib.Variant.new_string(fstype)
        vvalue = GLib.Variant.new_variant(value)
        newsv = GLib.Variant.new_dict_entry(optname, vvalue)
        param_builder.add_value(newsv)

        optname = GLib.Variant.new_string('options')
        value = GLib.Variant.new_string(list_options)
        vvalue = GLib.Variant.new_variant(value)
        newsv = GLib.Variant.new_dict_entry(optname, vvalue)
        param_builder.add_value(newsv)

        vparam = param_builder.end()
        vtparam = GLib.Variant.new_tuple(vparam)                # (a{sv})

        print('Mounting', devicefile + '...')
        try:
            mountpath = ifilesystem.call_sync('Mount', vtparam, Gio.DBusCallFlags.NONE, -1, None)
            mountpath = mountpath.unpack()[0]
        except gi._glib.GError:
            value = sys.exc_info()
            print('failed with error :')
            print(value)
        else:
            print('done at mountpath :', mountpath)

    elif action == "Unmount":

        optname = GLib.Variant.new_string('force')
        value = GLib.Variant.new_boolean(False)
        vvalue = GLib.Variant.new_variant(value)
        newsv = GLib.Variant.new_dict_entry(optname, vvalue)
        param_builder.add_value(newsv)

        vparam = param_builder.end()
        vtparam = GLib.Variant.new_tuple(vparam)                # (a{sv})

        print('Unmounting', devicefile + '...')
        try:
            ifilesystem.call_sync('Unmount',vtparam, Gio.DBusCallFlags.NONE, -1, None)
        except gi._glib.GError:
            value = sys.exc_info()[1]
            print('failed with error :')
            print(value)
        else:
            print('done')
            
    elif opticaldisk:
        list_options = '' # Eject currently doesn't use it
        optname = GLib.Variant.new_string('options')
        value = GLib.Variant.new_string(list_options)
        vvalue = GLib.Variant.new_variant(value)
        newsv = GLib.Variant.new_dict_entry(optname, vvalue)
        param_builder.add_value(newsv)

        vparam = param_builder.end()
        vtparam = GLib.Variant.new_tuple(vparam)                # (a{sv})

        print('Ejecting', devicefile + '...')
        try:
            idrive_optical.call_sync('Eject',vtparam, Gio.DBusCallFlags.NONE, -1, None)
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

# Refresh properties which may have changed from user actions
def setup_sensitive():
    global usage, label, mountpoints, ismounted, tooltip
    usage = iblock.get_cached_property('IdUsage').get_string()
    idtype = iblock.get_cached_property('IdType').get_string()
    label = iblock.get_cached_property('IdLabel').get_string()
    if ifilesystem:
        mountpoints = ifilesystem.get_cached_property('MountPoints').get_bytestring_array()
    else:
        mountpoints = []

    if mountpoints:
        ismounted = True
    else:
        ismounted = False

    action_mount.set_sensitive(not ismounted and (usage == 'filesystem'))
    action_unmount.set_sensitive(ismounted)
    # Optical disk must be unmounted before Eject is possible (it has no 'unmount' option)
    action_eject.set_sensitive(opticaldisk and not ismounted)

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


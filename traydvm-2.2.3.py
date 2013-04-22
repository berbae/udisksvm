#!/usr/bin/python
########################################
# Name of the script : traydvm
# Author : Bernard Baeyens (berbae) 2013
########################################
import sys, os, re
import argparse
from gi.repository import UDisks, GLib, Gio, Gtk
import gi

# Used for parameter builder on method call
G_VARIANT_TYPE_VARDICT = GLib.VariantType.new('a{sv}')

parser = argparse.ArgumentParser(description='A systray utility for udisksvm')

parser.add_argument('object_path', help='the object to use')

args = parser.parse_args()

obj_path = args.object_path
print('-----traydvm-----> Started for', obj_path)
print('-'*50)

# Use GLib MainLoop for using signal_handler to quit
loop = GLib.MainLoop()

#############################################################
# Connect to UDisks
#############################################################
client = UDisks.Client.new_sync(None)

# Central communication with DBus
manager = client.get_object_manager()

# Connect to the object
proxy = manager.get_object(obj_path)

#############################################################
# Fetch infos on the object
#############################################################
iblock = proxy.get_interface('org.freedesktop.UDisks2.Block')

devicefile = iblock.get_cached_property('Device').get_bytestring()
devicefile = devicefile.decode()
drive = iblock.get_cached_property('Drive').get_string()
idtype = iblock.get_cached_property('IdType').get_string()
label = iblock.get_cached_property('IdLabel').get_string()
uuid = iblock.get_cached_property('IdUUID').get_string()

#############################################################
ifilesystem = proxy.get_interface('org.freedesktop.UDisks2.Filesystem')

#############################################################
# Drive interface needed for optical disks
dproxy = manager.get_object(drive)
idrive = dproxy.get_interface('org.freedesktop.UDisks2.Drive')

opticaldisk = idrive.get_cached_property('Optical').get_boolean()

#############################################################
if not opticaldisk:
    # default value when there is no Partition interface
    iscontainer = iscontained = False

    ipartition = proxy.get_interface('org.freedesktop.UDisks2.Partition')

    if ipartition:
        iscontainer = ipartition.get_cached_property('IsContainer').get_boolean()
        iscontained = ipartition.get_cached_property('IsContained').get_boolean()

#############################################################
# Create systray icon
#############################################################
if opticaldisk:
    stockitem = Gtk.STOCK_CDROM
else:
    stockitem = Gtk.STOCK_HARDDISK

if label:
    tooltip = label
elif uuid:
    tooltip = uuid
else:
    tooltip = devicefile

trayicon = Gtk.StatusIcon()
trayicon.set_from_stock(stockitem)
trayicon.set_tooltip_text(tooltip)

#############################################################
# Create handler for popup menu actions
#############################################################
def on_menu_click(widget):

    # Used to build the parameter GVariant of type a{sv}
    # for the call_mount_sync, call_unmount_sync and call_eject_sync methods
    param_builder = GLib.VariantBuilder.new(G_VARIANT_TYPE_VARDICT)

    action = widget.get_name()
    if action == "Mount":
        if opticaldisk or not (iscontainer or iscontained):

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

            vparam = param_builder.end()                            # a{sv}

            print('-----traydvm-----> Mounting', devicefile + '...')
            try:
                mountpath = ifilesystem.call_mount_sync(vparam, None)
            except gi._glib.GError:
                value = sys.exc_info()
                print('-----traydvm-----> Mounting failed with error:')
                print(value)
            else:
                print('-----traydvm-----> Mounting done at mountpath:', mountpath)

        else:
            print('-----traydvm-----> Failed: not mounting a container or contained partition')

        print('-'*50)

    elif action == "Unmount":

        optname = GLib.Variant.new_string('force')
        value = GLib.Variant.new_boolean(False)
        vvalue = GLib.Variant.new_variant(value)
        newsv = GLib.Variant.new_dict_entry(optname, vvalue)
        param_builder.add_value(newsv)

        vparam = param_builder.end()                            # a{sv}

        print('-----traydvm-----> Unmounting', devicefile + '...')

        try:
            ifilesystem.call_unmount_sync(vparam, None)
        except gi._glib.GError:
            value = sys.exc_info()[1]
            print('-----traydvm-----> Unmounting failed with error :')
            print(value)
        else:
            print('-----traydvm-----> Unmounting done')
            
        print('-'*50)

    elif action == "Eject":

        list_options = '' # Eject currently doesn't use it
        optname = GLib.Variant.new_string('options')
        value = GLib.Variant.new_string(list_options)
        vvalue = GLib.Variant.new_variant(value)
        newsv = GLib.Variant.new_dict_entry(optname, vvalue)
        param_builder.add_value(newsv)

        vparam = param_builder.end()                            # a{sv}

        print('-----traydvm-----> Ejecting', devicefile + '...')

        try:
            idrive.call_eject_sync(vparam, None)
        except gi._glib.GError:
            value = sys.exc_info()[1]
            print('-----traydvm-----> Ejecting failed with error :')
            print(value)
        else:
            print('-----traydvm-----> Ejecting done')

        print('-'*50)

#############################################################
# Create actions for the popup menu
#############################################################
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

#############################################################
# Refresh properties which may have changed from user actions
#############################################################
def setup_sensitive():

    mountpoints = ifilesystem.get_cached_property('MountPoints').get_bytestring_array()

    if mountpoints:
        ismounted = True
    else:
        ismounted = False

    action_mount.set_sensitive(not ismounted)
    action_unmount.set_sensitive(ismounted)
    # Optical disk must be unmounted before Eject is possible (it has no 'unmount' option)
    action_eject.set_sensitive(opticaldisk and not ismounted)

#############################################################
# Popup menu layout and creation
#############################################################
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

#############################################################
# Connect systray icon to popup menu
#############################################################
def popup_menu(status_icon, button, activate_time, menu):
    setup_sensitive()
    menu.popup(None, None, status_icon.position_menu, status_icon, button, activate_time)
            
trayicon.connect('popup-menu', popup_menu, uiManager.get_widget('/ui/udisksvm'))

try:
    loop.run()
except KeyboardInterrupt:
    print('-------------traydvm-----> Bye!', '-'*18)
    loop.quit()


#!/usr/bin/python
########################################
# Name of the script : traydvm
# Author : Bernard Baeyens (berbae) 2013
########################################
import os
import sys
import argparse

from gi.repository import UDisks, GLib, Gio, Gtk

_version = '2.3.3'

# Used for parameter builder on method call
G_VARIANT_TYPE_VARDICT = GLib.VariantType.new('a{sv}')

parser = argparse.ArgumentParser(description='A systray utility for udisksvm')

parser.add_argument('-v', '--version', action='version',
                    version='%(prog)s ' + _version)
parser.add_argument('-s', '--silent',
                    help='disable notification popup messages',
                    action='store_true')
parser.add_argument('object_path', help='the object to use')

args = parser.parse_args()

obj_path = args.object_path
print('     traydvm: started for', obj_path)
print('-' * 50)

popup = not args.silent
#############################################################
# Prepare notifications if enabled
#############################################################
if popup:
    try:
        from gi.repository import Notify
        Notify.init("traydvm")
        notify_action = Notify.Notification.new("device action", None,
                                                "notification-device")
    except Exception:
        value = sys.exc_info()[1]
        print("     traydvm: error preparing notifications:")
        print(value)
        print('-' * 50)
        popup = False
        print('     traydvm: notifications disabled')
    else:
        print('     traydvm: notifications initialized')
else:
    print('     traydvm: notifications disabled')
print('-' * 50)

# Use GLib MainLoop which reacts to SIGINT to quit
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
iblock = proxy.get_block()

devicefile = iblock.get_cached_property('Device')
devicefile = devicefile.get_bytestring()
devicefile = devicefile.decode()
devicename = devicefile.split('/')[2]
drive = iblock.get_cached_property('Drive')
drive = drive.get_string()
idtype = iblock.get_cached_property('IdType')
idtype = idtype.get_string()
label = iblock.get_cached_property('IdLabel')
label = label.get_string()
uuid = iblock.get_cached_property('IdUUID')
uuid = uuid.get_string()

#############################################################
ifilesystem = proxy.get_filesystem()

#############################################################
# Drive interface needed for optical disks
dproxy = manager.get_object(drive)
idrive = dproxy.get_drive()

opticaldisk = idrive.get_cached_property('Optical')
opticaldisk = opticaldisk.get_boolean()

#############################################################
if not opticaldisk:
    # default value when there is no Partition interface
    iscontainer = iscontained = False

    ipartition = proxy.get_partition()
    if ipartition is not None:
        iscontainer = ipartition.get_cached_property('IsContainer')
        iscontainer = iscontainer.get_boolean()
        iscontained = ipartition.get_cached_property('IsContained')
        iscontained = iscontained.get_boolean()

#############################################################
# Create systray icon
#############################################################
if opticaldisk:
    icon_name = 'media-optical'
else:
    icon_name = 'drive-removable-media'

tooltip = devicename
if label:
    tooltip = tooltip + ' : ' + label
elif uuid:
    tooltip = tooltip + ' : ' + uuid

trayicon = Gtk.StatusIcon.new_from_icon_name(icon_name)
#trayicon.set_tooltip_text(tooltip)


def on_menu_click(widget):
#############################################################
# Handler for popup menu actions
#############################################################
    # Used to build the parameter GVariant of type a{sv}
    # for the call_mount_sync, call_unmount_sync and call_eject_sync methods
    param_builder = GLib.VariantBuilder.new(G_VARIANT_TYPE_VARDICT)

    action = widget.get_name()
    if action == "Mount":
        if opticaldisk or not (iscontainer or iscontained):
            fstype = idtype
            list_options = ''
            if fstype == 'vfat':
                list_options = 'flush'
            elif fstype == 'ext2':
                list_options = 'sync'

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

            print('     traydvm: Mounting', devicefile + '...')
            try:
                mountpath = ifilesystem.call_mount_sync(vparam, None)
            except GLib.GError:
                value = sys.exc_info()[1]
                print('     traydvm: Mounting failed with error:')
                print(value)
                if popup:
                    notify_action.update("Could not mount " + devicename, None,
                                         "dialog-error")
                    notify_action.show()
            else:
                print('     traydvm: Mounting done at mountpath:', mountpath)
                if popup:
                    notify_action.update(devicename + " mounted :", mountpath,
                                         "dialog-information")
                    notify_action.show()
        else:
            print('     traydvm: Failed: not mounting a container or contained'
                  ' partition')
        print('-' * 50)

    elif action == "Unmount":

        optname = GLib.Variant.new_string('force')
        value = GLib.Variant.new_boolean(False)
        vvalue = GLib.Variant.new_variant(value)
        newsv = GLib.Variant.new_dict_entry(optname, vvalue)
        param_builder.add_value(newsv)

        vparam = param_builder.end()                            # a{sv}

        print('     traydvm: Unmounting', devicefile + '...')
        try:
            ifilesystem.call_unmount_sync(vparam, None)
        except GLib.GError:
            value = sys.exc_info()[1]
            print('     traydvm: Unmounting failed with error :')
            print(value)
            if popup:
                notify_action.update("Could not unmount " + devicename,
                                     "probably device busy", "dialog-error")
                notify_action.show()
        else:
            print('     traydvm: Unmounting done')
            if popup:
                notify_action.update(devicename + " unmounted", None,
                                     "dialog-information")
                notify_action.show()
        print('-' * 50)

    elif action == "Eject":

        list_options = ''  # Eject currently doesn't use it
        optname = GLib.Variant.new_string('options')
        value = GLib.Variant.new_string(list_options)
        vvalue = GLib.Variant.new_variant(value)
        newsv = GLib.Variant.new_dict_entry(optname, vvalue)
        param_builder.add_value(newsv)

        vparam = param_builder.end()                            # a{sv}

        print('     traydvm: Ejecting', devicefile + '...')
        try:
            idrive.call_eject_sync(vparam, None)
        except GLib.GError:
            value = sys.exc_info()[1]
            print('     traydvm: Ejecting failed with error :')
            print(value)
            if popup:
                notify_action.update("Could not eject disk from " + devicename,
                                     None, "dialog-error")
                notify_action.show()
        else:
            print('     traydvm: Ejecting done')
        print('-' * 50)

#############################################################
# Create actions for the popup menu
#############################################################
# To prevent using '_' for mnemonic letters in label
title = tooltip.replace('_', '__')
action_title = Gtk.Action("Title", "   " + title + "   ", None, None)
action_mount = Gtk.Action("Mount", "Mount", None, None)
action_mount.connect("activate", on_menu_click)
action_unmount = Gtk.Action("Unmount", "Unmount", None, None)
action_unmount.connect("activate", on_menu_click)
action_eject = Gtk.Action("Eject", "Eject", None, None)
action_eject.connect("activate", on_menu_click)

action_group = Gtk.ActionGroup("popup_actions")
action_group.add_action(action_title)
action_group.add_action(action_mount)
action_group.add_action(action_unmount)
action_group.add_action(action_eject)


def setup_sensitive():
#############################################################
# Refresh properties which may have changed from user actions
#############################################################
    mountpoints = ifilesystem.get_cached_property('MountPoints')
    mountpoints = mountpoints.get_bytestring_array()

    if mountpoints:
        ismounted = True
    else:
        ismounted = False

    action_mount.set_sensitive(not ismounted)
    action_unmount.set_sensitive(ismounted)
    # Eject only an unmounted optical disk
    action_eject.set_sensitive(opticaldisk and not ismounted)

#############################################################
# Popup menu layout and creation
#############################################################
UI_INFO = """
<ui>
<popup name='traydvm'>
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


def popup_menu(status_icon, button, activate_time, menu):
    setup_sensitive()
    menu.popup(None, None, status_icon.position_menu, status_icon, button,
               activate_time)
#############################################################
# Connect systray icon to popup menu using the above popup_menu() function
#############################################################
trayicon.connect('popup-menu', popup_menu, uiManager.get_widget('/ui/traydvm'))

#############################################################
try:
    loop.run()
except KeyboardInterrupt:
    print('-' * 17, 'traydvm: Bye!', '-' * 18)
    loop.quit()

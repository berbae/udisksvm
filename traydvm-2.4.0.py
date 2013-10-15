#!/usr/bin/python
########################################
# Name of the script : traydvm
# Author : Bernard Baeyens (berbae) 2013
########################################
import os
import sys
import argparse

from gi.repository import UDisks, GLib, Gio, Gtk

_version = '2.4.0'

# Used for parameter builder on method call
G_VARIANT_TYPE_VARDICT = GLib.VariantType.new('a{sv}')
# Icon images from the gnome-icon-theme package
ICON_ADD = "/usr/share/icons/gnome/48x48/actions/list-add.png"
ICON_REMOVE = "/usr/share/icons/gnome/48x48/actions/list-remove.png"
ICON_EJECT = "/usr/share/icons/gnome/48x48/actions/media-eject.png"

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


def on_menu_click(action, param, udata):
#############################################################
# Handler for popup menu actions
#############################################################
    # Used to build the parameter GVariant of type a{sv}
    # for the call_mount_sync, call_unmount_sync and call_eject_sync methods
    param_builder = GLib.VariantBuilder.new(G_VARIANT_TYPE_VARDICT)

    clicked_action = action.get_name()
    if clicked_action == "action_mount":
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

    elif clicked_action == "action_unmount":

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

    elif clicked_action == "action_eject":

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
act_mount = Gio.SimpleAction.new("action_mount", None)
act_mount.connect("activate", on_menu_click, None)

act_unmount = Gio.SimpleAction.new("action_unmount", None)
act_unmount.connect("activate", on_menu_click, None)

act_eject = Gio.SimpleAction.new("action_eject", None)
act_eject.connect("activate", on_menu_click, None)

popup_actions = Gio.SimpleActionGroup.new()
popup_actions.add_action(act_mount)
popup_actions.add_action(act_unmount)
popup_actions.add_action(act_eject)


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

    act_mount.set_enabled(not ismounted)
    act_unmount.set_enabled(ismounted)
    # Eject only an unmounted optical disk
    act_eject.set_enabled(opticaldisk and not ismounted)

#############################################################
# Popup menu creation
#############################################################
menucontent = Gio.Menu.new()

g_icon_add_image= Gio.File.new_for_path(ICON_ADD)
g_icon_add = Gio.FileIcon.new(g_icon_add_image)
gitem_mount = Gio.MenuItem.new("  Mount", "traydvm.action_mount")
gitem_mount.set_icon(g_icon_add)
menucontent.append_item(gitem_mount)

g_icon_remove_image= Gio.File.new_for_path(ICON_REMOVE)
g_icon_remove = Gio.FileIcon.new(g_icon_remove_image)
gitem_unmount = Gio.MenuItem.new("  Unount", "traydvm.action_unmount")
gitem_unmount.set_icon(g_icon_remove)
menucontent.append_item(gitem_unmount)

g_icon_eject_image= Gio.File.new_for_path(ICON_EJECT)
g_icon_eject = Gio.FileIcon.new(g_icon_eject_image)
gitem_eject = Gio.MenuItem.new("  Eject", "traydvm.action_eject")
gitem_eject.set_icon(g_icon_eject)
menucontent.append_item(gitem_eject)

menumodel = Gio.Menu.new()

gitem = Gio.MenuItem.new_section("   " + tooltip + "   ", menucontent)
menumodel.append_item(gitem)

traydvm_menu = Gtk.Menu.new_from_model(menumodel)

traydvm_menu.insert_action_group("traydvm", popup_actions)


def popup_menu(status_icon, button, activate_time, menu):
    setup_sensitive()
    menu.popup(None, None, status_icon.position_menu, status_icon, button,
               activate_time)
#############################################################
# Connect systray icon to popup menu using the above popup_menu() function
#############################################################
trayicon.connect('popup-menu', popup_menu, traydvm_menu)

#############################################################
try:
    loop.run()
except KeyboardInterrupt:
    print('-' * 17, 'traydvm: Bye!', '-' * 18)
    loop.quit()

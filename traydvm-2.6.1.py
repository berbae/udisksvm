#!/usr/bin/python
########################################
# Name of the script : traydvm
# Copyright (C) 2013 Bernard Baeyens (berbae)
########################################
# This file is part of udisksvm.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
########################################

import os
import sys
import argparse

from gi.repository import UDisks, GLib

from PyQt4 import QtGui, QtCore

_version = '2.6.1'

# Use GLib MainLoop which reacts to SIGINT to quit
loop = GLib.MainLoop()

# To prevent crash on exit
import sip
sip.setdestroyonexit(False)

app = QtGui.QApplication(['traydvm'])

# Used for parameter builder on method call
G_VARIANT_TYPE_VARDICT = GLib.VariantType.new('a{sv}')
# Icon images from the oxygen-icons package
ICON_THEME = '/usr/share/icons/oxygen/32x32'
ICON_DRIVE = QtGui.QIcon(ICON_THEME + '/devices/drive-removable-media.png')
ICON_OPTICAL = QtGui.QIcon(ICON_THEME + '/devices/media-optical.png')
ICON_ADD = QtGui.QIcon(ICON_THEME + '/actions/list-add.png')
ICON_REMOVE = QtGui.QIcon(ICON_THEME + '/actions/list-remove.png')
ICON_EJECT = QtGui.QIcon(ICON_THEME + '/actions/media-eject.png')
ICON_CLOSE = QtGui.QIcon(ICON_THEME + '/actions/window-close.png')

parser = argparse.ArgumentParser(description='A systray utility for udisksvm')

parser.add_argument('-v', '--version', action='version',
                    version='%(prog)s ' + _version)
parser.add_argument('-s', '--silent',
                    help='disable notification balloon messages',
                    action='store_true')
parser.add_argument('object_path', help='the object to use')

args = parser.parse_args()

obj_path = args.object_path
print('     traydvm: started for', obj_path)
print('-' * 50)

balloon = not args.silent

# Connect to UDisks
client = UDisks.Client.new_sync(None)

# Central communication with DBus
manager = client.get_object_manager()

# Connect to the object
proxy = manager.get_object(obj_path)

# Fetch infos on the object
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

ifilesystem = proxy.get_filesystem()

# Drive interface needed for optical disks
opticaldisk = False
dproxy = manager.get_object(drive)
if dproxy is not None:
    idrive = dproxy.get_drive()
    if idrive is not None:
        opticaldisk = idrive.get_cached_property('Optical')
        opticaldisk = opticaldisk.get_boolean()

if not opticaldisk:
    # default value when there is no Partition interface
    iscontainer = iscontained = False

    ipartition = proxy.get_partition()
    if ipartition is not None:
        iscontainer = ipartition.get_cached_property('IsContainer')
        iscontainer = iscontainer.get_boolean()
        iscontained = ipartition.get_cached_property('IsContained')
        iscontained = iscontained.get_boolean()

# Create systray icon
if opticaldisk:
    icon_name = ICON_OPTICAL
else:
    icon_name = ICON_DRIVE

tooltip_header = devicename
if label:
    tooltip_header = tooltip_header + ' : ' + label
elif uuid:
    tooltip_header = tooltip_header + ' : ' + uuid

trayicon = QtGui.QSystemTrayIcon(icon_name)

# Popup menu creation
traypopup = QtGui.QMenu()

popuptitle = QtGui.QWidgetAction(traypopup)

title = QtGui.QLabel('\n' + tooltip_header)
title.setAlignment(QtCore.Qt.AlignHCenter)
titlefont = title.font()
titlefont.setWeight(QtGui.QFont.Bold)
title.setFont(titlefont)

popuptitle.setDefaultWidget(title)

traypopup.addAction(popuptitle)
traypopup.addSeparator()

mountAction = traypopup.addAction(ICON_ADD, 'Mount')
unmountAction = traypopup.addAction(ICON_REMOVE, 'Unmount')
ejectAction = traypopup.addAction(ICON_EJECT, 'Eject')

traypopup.addSeparator()
closeAction = traypopup.addAction(ICON_CLOSE, 'Close menu')


def refresh_setup():
    # Refresh properties
    mountpoints = ifilesystem.get_cached_property('MountPoints')
    mountpoints = mountpoints.get_bytestring_array()

    if mountpoints:
        tooltip_text = tooltip_header + "\nMounted at : " + mountpoints[0]
        ismounted = True
    else:
        tooltip_text = tooltip_header + "\nNot mounted"
        ismounted = False

    # Generate the tooltip text
    trayicon.setToolTip(tooltip_text)

    # Set the actions state
    mountAction.setEnabled(not ismounted)
    unmountAction.setEnabled(ismounted)
    # Eject only an unmounted optical disk
    ejectAction.setEnabled(opticaldisk and not ismounted)


def on_click(action):
    # This is the handler for popup menu actions

    # Variable used to build the parameter GVariant of type a{sv}
    # for the call_mount_sync, call_unmount_sync and call_eject_sync methods:
    param_builder = GLib.VariantBuilder.new(G_VARIANT_TYPE_VARDICT)

    clicked_action = action.text()
    if clicked_action == "Mount":
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
                if balloon:
                    trayicon.showMessage(tooltip_header, 'mount error',
                                         trayicon.Warning, 5000)
            else:
                print('     traydvm: Mounting done at mountpath:', mountpath)
                if balloon:
                    trayicon.showMessage(tooltip_header, 'mounted at:\n' +
                                         mountpath, trayicon.Information, 5000)
        else:
            print('     traydvm: Failed: not mounting a container or contained'
                  ' partition')
        print('-' * 50)

    elif clicked_action == "Unmount":

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
            if balloon:
                trayicon.showMessage(tooltip_header, 'unmount error\nprobably '
                                     'device busy', trayicon.Warning, 5000)
        else:
            print('     traydvm: Unmounting done')
            if balloon:
                trayicon.showMessage(tooltip_header, 'unmounted successfully',
                                     trayicon.Information, 5000)
        print('-' * 50)

    elif clicked_action == "Eject":

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
            if balloon:
                trayicon.showMessage(tooltip_header, 'could not eject disk',
                                     trayicon.Warning, 5000)
        else:
            print('     traydvm: Ejecting done')
        print('-' * 50)

traypopup.triggered.connect(on_click)

trayicon.setContextMenu(traypopup)

refresh_setup()

timer = QtCore.QTimer()
timer.start(1000)
timer.timeout.connect(refresh_setup)  # Refresh setup every second

trayicon.show()

try:
    sys.exit(loop.run())
except KeyboardInterrupt:
    print('\n' + '-' * 17, 'traydvm: Bye!', '-' * 18)
    timer.stop()
    loop.quit()

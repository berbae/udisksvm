#!/bin/bash
# Name of the script : udisksvm
# Author : Bernard Baeyens (berbae) 2011
#
# configuration file for traydevice
TRAYCONF="/usr/share/udisksvm/udisksvm.xml"
# Start monitoring
coproc udisks --monitor
#echo "----$COPROC_PID----"
#echo "----${COPROC[0]}----"
#echo "----${COPROC[1]}----"

trap "kill $COPROC_PID 2>/dev/null;echo ------------ Bye! --------------" EXIT SIGINT SIGTERM SIGQUIT
trap "" SIGHUP
# Read the first line header 
if ps -p $COPROC_PID &>/dev/null; then
    read -u ${COPROC[0]}
else
    echo "udisk monitoring could not be started"
    exit 1
fi
# Waiting for uevents
while ps -p $COPROC_PID &>/dev/null; do
    read -u ${COPROC[0]}
    event=${REPLY%:*}
    devpath=${REPLY#*:}
    devpath=${devpath/#*\//\/dev\/}
    if [[ -e $devpath ]]; then
	listinfos=$(udisks --show-info $devpath|\
	grep -e "system internal" -e "usage" -e "is mounted" -e "has media" -e "optical disc" -e "num audio tracks"\
	-e "type" -e "partition:" -e "blank")
	unset systeminternal usage ismounted hasmedia opticaldisc numaudiotracks type partition blank
	while read infoline; do
	    vinfo=$(cut -d: -f1 <<< "$infoline")
	    vinfo=${vinfo// }
	    cinfo=$(cut -d: -f2 <<< "$infoline")
	    cinfo=${cinfo// }
	    case $vinfo in
		opticaldisc) opticaldisc=1;;
		type) type=${type:-$cinfo};;
		partition) partition=1;;
		*) printf -v $vinfo %s "$cinfo";;
	    esac
	done <<< "$listinfos"
	# The change for type= is to take only its first value in listinfos
	# Take only the first character
	hasmedia=${hasmedia:0:1}
	# If "partition:" not find in listinfos, should mean it is not a partition
	partition=${partition:-0}
#	echo "systeminternal : ---$systeminternal---"
#	echo "usage : ---$usage---"
#	echo "ismounted : ---$ismounted---"
#	echo "hasmedia : ---$hasmedia---"
#	echo "opticaldisc : ---$opticaldisc---"
#	echo "numaudiotracks : ---$numaudiotracks---"
#	echo "type : ---$type---"
#	echo "partition : ---$partition---"
#	echo "blank : ---$blank---"
	case $event in
	    added)
		echo "------------ $event --------------"
		if [[ "$systeminternal" == "0" ]] && [[ "$usage" == "filesystem" ]] && [[ "$partition" == "1" ]]; then
		    if [[ "$type" == "vfat" ]]; then
			options="flush,noatime,nodiratime,noexec,nodev,utf8=0"
		    else
			options="sync,noatime,nodiratime,noexec,nodev"
		    fi
		    if ! pgrep -f "traydevice -c $TRAYCONF $devpath" &>/dev/null; then
			udisks --mount $devpath --mount-options $options &>/dev/null
			traydevice -c $TRAYCONF $devpath &>/dev/null &
		    fi
		fi
		;;
	    job-changed)
		echo "------------ $event --------------" ;;
	    removed)
		echo "------------ $event --------------" ;;
	    changed)
		echo "------------ $event --------------"
		if [[ "$systeminternal" == "0" ]] && [[ "$opticaldisc" == "1" ]] && [[ "$hasmedia" == "1" ]] && \
		   [[ "$usage" == "filesystem" ]] && [[ "$numaudiotracks" == "0" ]] && [[ "$blank" == "0" ]]; then
		    pgrep -f "traydevice -c $TRAYCONF $devpath" &>/dev/null || \
		    traydevice -c $TRAYCONF $devpath &>/dev/null &
		fi
		;;
	esac
    elif [[ "$event" == "removed" ]]; then
	    echo "------------ $event --------------"
    fi
done

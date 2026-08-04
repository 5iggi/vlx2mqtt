#!/bin/bash
# Register vlx2mqtt.log as LoxBerry Logging SDK session.
# This does not manually list files in the frontend. It tells LoxBerry that the
# fixed daemon log belongs to PACKAGE=vlx2mqtt, NAME=Daemon.

PLUGIN="vlx2mqtt"
LBHOMEDIR="${LBHOMEDIR:-/opt/loxberry}"
LBPLOG="${LBPLOG:-/opt/loxberry/log/plugins}"
LOGDIR_PLUGIN="$LBPLOG/$PLUGIN"
LOG_LIB="$LBHOMEDIR/libs/bashlib/loxberry_log.sh"
FILENAME="$LOGDIR_PLUGIN/vlx2mqtt.log"

if [ ! -r "$LOG_LIB" ]; then
  echo "LoxBerry log library not found: $LOG_LIB" >&2
  exit 1
fi

mkdir -p "$LOGDIR_PLUGIN"
touch "$FILENAME"
chmod 664 "$FILENAME" 2>/dev/null || true
chown loxberry:loxberry "$FILENAME" 2>/dev/null || true

PACKAGE="$PLUGIN"
NAME="Daemon"
LOGDIR=""
APPEND=1
STDERR=1
LOGLEVEL=7

. "$LOG_LIB"

PACKAGE="$PLUGIN"
NAME="Daemon"
LOGDIR=""
APPEND=1
STDERR=1
LOGLEVEL=7

LOGSTART "VLX2MQTT daemon log registered."
LOGINF "This fixed daemon logfile is registered for LoxBerry loglist_html()."
LOGOK "Daemon log file: $FILENAME"
LOGEND "VLX2MQTT daemon log registration finished."

chmod 664 "$FILENAME" 2>/dev/null || true
chown loxberry:loxberry "$FILENAME" 2>/dev/null || true
exit 0

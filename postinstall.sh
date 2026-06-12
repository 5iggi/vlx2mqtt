#!/bin/bash
# Runs AFTER plugin files were unpacked.
# Runs as user "loxberry".
# Exit codes: 0=ok, 1=warning, 2=fatal

COMMAND=$0
PTEMPDIR=$1
PSHNAME=$2
PDIR=$3
PVERSION=$4
PTEMPPATH=$6

PBIN=$LBPBIN/$PDIR
PCONFIG=$LBPCONFIG/$PDIR
PDATA=$LBPDATA/$PDIR
PLOGS=$LBPLOG/$PDIR

echo "<INFO> vlx2mqtt POSTINSTALL — PDIR=$PDIR PVERSION=$PVERSION"

mkdir -p "$PBIN" "$PCONFIG" "$PDATA" "$PLOGS" || {
  echo "<ERROR> Could not create plugin directories."
  exit 2
}

# Default-Konfiguration nur beim ersten Installieren anlegen
if [ ! -f "$PCONFIG/vlx2mqtt.cfg" ] && [ -f "$PBIN/../config/vlx2mqtt.cfg" ]; then
  cp "$PBIN/../config/vlx2mqtt.cfg" "$PCONFIG/vlx2mqtt.cfg" || {
    echo "<WARNING> Could not copy default config."
  }
fi

# Python-Skript ausführbar setzen
if [ -f "$PBIN/vlx2mqtt.py" ]; then
  chmod 755 "$PBIN/vlx2mqtt.py" || {
    echo "<WARNING> Could not chmod vlx2mqtt.py"
  }
fi

echo "<OK> vlx2mqtt POSTINSTALL finished."
exit 0

#!/bin/bash

# uninstall - Executed when the plugin is uninstalled via the LoxBerry Plugin Manager.
# Runs as user "ROOT".
# Use this to clean up anything that your plugin created outside of its own plugin
# directories (e.g. system service entries, entries in /etc, external symlinks).
# The plugin's own directories (config, data, html, cgi, templates, log, bin, sbin)
# are removed automatically by LoxBerry - you do not need to delete them here.
# Use with caution - remember that all target systems may differ.
#
# Exit codes:
#   0 = success, uninstallation continues
#   1 = warning, uninstallation continues but a warning is shown
#
# All variables from /etc/environment are available in this script.
#
# Arguments passed to this script:
#   $0 = path to this script
#   $1 = temporary folder used during uninstallation (short form)
#   $2 = plugin short name (NAME from plugin.cfg)
#   $3 = plugin installation folder (FOLDER from plugin.cfg)
#   $4 = plugin version (VERSION from plugin.cfg)

COMMAND=$0
PTEMPDIR=$1
PSHNAME=$2
PDIR=$3
PVERSION=$4

# Build full plugin-specific paths from environment variables
PCGI=$LBPCGI/$PDIR
PHTML=$LBPHTML/$PDIR
PTEMPL=$LBPTEMPL/$PDIR
PDATA=$LBPDATA/$PDIR
PLOG=$LBPLOG/$PDIR
PCONFIG=$LBPCONFIG/$PDIR
PSBIN=$LBPSBIN/$PDIR
PBIN=$LBPBIN/$PDIR

SERVICE_NAME="vlx2mqtt.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"

echo "<INFO> Command is: $COMMAND"
echo "<INFO> Temporary folder is: $PTEMPDIR"
echo "<INFO> Plugin short name is: $PSHNAME"
echo "<INFO> Installation folder is: $PDIR"
echo "<INFO> Plugin version is: $PVERSION"
echo "<INFO> Plugin CGI folder is: $PCGI"
echo "<INFO> Plugin HTML folder is: $PHTML"
echo "<INFO> Plugin Template folder is: $PTEMPL"
echo "<INFO> Plugin Data folder is: $PDATA"
echo "<INFO> Plugin Log folder is: $PLOG"
echo "<INFO> Plugin Config folder is: $PCONFIG"
echo "<INFO> Plugin SBIN folder is: $PSBIN"
echo "<INFO> Plugin BIN folder is: $PBIN"

echo "<INFO> Stopping systemd service if present"
if systemctl list-unit-files | grep -q "^$SERVICE_NAME"; then
  systemctl stop "$SERVICE_NAME" >/dev/null 2>&1 && \
    echo "<OK> Stopped $SERVICE_NAME" || \
    echo "<WARNING> Could not stop $SERVICE_NAME (maybe already stopped)"
else
  echo "<INFO> $SERVICE_NAME not registered"
fi

echo "<INFO> Disabling systemd service if present"
if systemctl list-unit-files | grep -q "^$SERVICE_NAME"; then
  systemctl disable "$SERVICE_NAME" >/dev/null 2>&1 && \
    echo "<OK> Disabled $SERVICE_NAME" || \
    echo "<WARNING> Could not disable $SERVICE_NAME"
fi

echo "<INFO> Removing service file if present"
if [ -f "$SERVICE_FILE" ]; then
  rm -f "$SERVICE_FILE" && \
    echo "<OK> Removed $SERVICE_FILE" || \
    echo "<WARNING> Could not remove $SERVICE_FILE"
else
  echo "<INFO> No service file found at $SERVICE_FILE"
fi

echo "<INFO> Reloading systemd"
systemctl daemon-reload >/dev/null 2>&1 && \
  echo "<OK> systemd daemon reloaded" || \
  echo "<WARNING> systemctl daemon-reload failed"

echo "<INFO> Resetting failed systemd state"
systemctl reset-failed "$SERVICE_NAME" >/dev/null 2>&1 && \
  echo "<OK> Reset failed state for $SERVICE_NAME" || \
  echo "<INFO> No failed state to reset"

echo "<OK> vlx2mqtt uninstall cleanup finished"
exit 0
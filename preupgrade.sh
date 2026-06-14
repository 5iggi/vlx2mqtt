#!/bin/bash
# preupgrade.sh - Executed as the first step when updating an already-installed plugin.
# Runs as user "loxberry" BEFORE preinstall.sh, only during updates (not on fresh install).
# Purpose: Preserve existing user configuration before update files overwrite defaults.
# Exit codes: 0 = success, 1 = warning, 2 = error

# Load LoxBerry environment variables defensively.
if [ -f /etc/environment ]; then
    # shellcheck disable=SC1091
    . /etc/environment || true
fi

COMMAND=$0              # Path to this script
PTEMPDIR=${1:-}         # Temporary folder (short) during installation
PSHNAME=${2:-}          # Plugin short name for scripts/cron
PDIR=${3:-}             # Plugin installation folder
PVERSION=${4:-}         # Plugin version
PTEMPPATH=${6:-}        # Full temporary path during installation (if provided)

# Only use variables that are really needed here.
LBPCONFIG_SAFE=${LBPCONFIG:-/opt/loxberry/config/plugins}
PCONFIG="${LBPCONFIG_SAFE}/${PDIR}"

# Use update-specific temp folder as intended for upgrade handover.
BACKUPROOT="/tmp/${PTEMPDIR}_upgrade"
BACKUPCONFIG="${BACKUPROOT}/config"

mkdir -p "$BACKUPCONFIG"


echo "<INFO> Command is: $COMMAND"
echo "<INFO> Temporary folder is: $PTEMPDIR"
echo "<INFO> Temporary full path is: $PTEMPPATH"
echo "<INFO> Plugin short name is: $PSHNAME"
echo "<INFO> Installation folder is: $PDIR"
echo "<INFO> Plugin version is: $PVERSION"
echo "<INFO> Plugin CONFIG folder is: $PCONFIG"
echo "<INFO> Backup root is: $BACKUPROOT"

# Preserve the full plugin config folder before update files overwrite defaults.
if [ -d "$PCONFIG" ]; then
    echo "<INFO> Backing up existing config folder"
    rm -rf "$BACKUPCONFIG/$PDIR"
    cp -a "$PCONFIG" "$BACKUPCONFIG/"
    if [ $? -ne 0 ]; then
        echo "<ERROR> Failed to back up config folder from $PCONFIG"
        exit 2
    fi
    echo "<OK> Config backup created at $BACKUPCONFIG/$PDIR"
else
    echo "<INFO> No existing config folder found at $PCONFIG - nothing to back up"
fi

exit 0

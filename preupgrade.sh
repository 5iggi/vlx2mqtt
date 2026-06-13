#!/bin/bash
# preupgrade.sh - Executed as the first step when updating an already-installed plugin.
# Runs as user "loxberry" BEFORE preinstall.sh, only during updates (not on fresh install).
# Use this to preserve existing user data before new files overwrite them.
# Exit codes: 0 = success, 1 = warning, 2 = error

set -u

COMMAND=$0        # Path to this script
PTEMPDIR=$1       # Temporary folder (short) during installation
PSHNAME=$2        # Plugin short name for scripts/cron
PDIR=$3           # Plugin installation folder
PVERSION=$4       # Plugin version
# $5 unused - LBHOMEDIR now comes from /etc/environment
PTEMPPATH=${6:-}  # Full temporary path during installation

# Build full plugin-specific paths from environment variables
PCGI=$LBPCGI/$PDIR
PHTML=$LBPHTML/$PDIR
PTEMPL=$LBPTEMPL/$PDIR
PDATA=$LBPDATA/$PDIR
PLOG=$LBPLOG/$PDIR
PCONFIG=$LBPCONFIG/$PDIR
PSBIN=$LBPSBIN/$PDIR
PBIN=$LBPBIN/$PDIR

BACKUPROOT="/tmp/${PSHNAME}_upgrade"
BACKUPCONFIG="$BACKUPROOT/config"

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

#!/bin/bash
# postupgrade.sh - Executed as the very last step when updating an already-installed plugin.
# Runs as user "loxberry" AFTER postinstall.sh, only during updates (not on fresh install).
# Use this to restore user data saved by preupgrade.sh, or to run any migration logic
# needed when upgrading from an older plugin version.
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
BACKUPCONFIG="$BACKUPROOT/config/$PDIR"
CFGFILE="$PCONFIG/vlx2mqtt.cfg"

ensure_ini_key() {
    local file="$1"
    local key="$2"
    local value="$3"

    if grep -Eq "^[[:space:]]*${key}[[:space:]]*=" "$file" 2>/dev/null; then
        return 0
    fi

    echo "${key} = ${value}" >> "$file"
    echo "<INFO> Added missing config key: ${key} = ${value}"
}

echo "<INFO> Command is: $COMMAND"
echo "<INFO> Temporary folder is: $PTEMPDIR"
echo "<INFO> Temporary full path is: $PTEMPPATH"
echo "<INFO> Plugin short name is: $PSHNAME"
echo "<INFO> Installation folder is: $PDIR"
echo "<INFO> Plugin version is: $PVERSION"
echo "<INFO> Plugin CONFIG folder is: $PCONFIG"
echo "<INFO> Backup root is: $BACKUPROOT"

# Restore preserved config folder from preupgrade
if [ -d "$BACKUPCONFIG" ]; then
    echo "<INFO> Restoring config folder from backup"
    mkdir -p "$PCONFIG"
    cp -a "$BACKUPCONFIG/." "$PCONFIG/"
    if [ $? -ne 0 ]; then
        echo "<ERROR> Failed to restore config folder to $PCONFIG"
        exit 2
    fi
    echo "<OK> Config folder restored"
else
    echo "<INFO> No backup config folder found at $BACKUPCONFIG - nothing to restore"
fi

# Non-destructive migration for newer config keys introduced in later releases.
if [ -f "$CFGFILE" ]; then
    if ! grep -Eq "^[[:space:]]*\[vlx2mqtt\][[:space:]]*$" "$CFGFILE"; then
        echo "" >> "$CFGFILE"
        echo "[vlx2mqtt]" >> "$CFGFILE"
        echo "<INFO> Added missing [vlx2mqtt] section to $CFGFILE"
    fi

    ensure_ini_key "$CFGFILE" "topic_identifier" "name"
    ensure_ini_key "$CFGFILE" "rain_poll_interval" "300"
    ensure_ini_key "$CFGFILE" "publish_rain_raw_limit" "0"
else
    echo "<INFO> No config file found at $CFGFILE - skipping migration"
fi

# Cleanup temporary upgrade backup
if [ -d "$BACKUPROOT" ]; then
    echo "<INFO> Removing temporary backup folder"
    rm -rf "$BACKUPROOT"
fi

echo "<OK> Upgrade restore/migration finished"
exit 0

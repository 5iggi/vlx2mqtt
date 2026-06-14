#!/bin/bash
# postupgrade.sh - Executed as the very last step when updating an already-installed plugin.
# Runs as user "loxberry" AFTER postinstall.sh, only during updates (not on fresh install).
# Purpose: Restore user configuration saved by preupgrade.sh and run light config migration.
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
CFGFILE="${PCONFIG}/vlx2mqtt.cfg"

BACKUPROOT="/tmp/${PTEMPDIR}_upgrade"
BACKUPCONFIG="${BACKUPROOT}/config/${PDIR}"

ensure_ini_key() {
    local file="$1"
    local key="$2"
    local value="$3"

    if grep -Eq "^[[:space:]]*${key}[[:space:]]*=" "$file" 2>/dev/null; then
        return 0
    fi

    printf '%s = %s
' "$key" "$value" >> "$file"
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

# Restore preserved config folder from preupgrade.
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
    # Ensure the expected section exists. Only append if the file does not already contain it.
    if ! grep -Eq "^[[:space:]]*\[vlx2mqtt\][[:space:]]*$" "$CFGFILE"; then
        printf '
[vlx2mqtt]
' >> "$CFGFILE"
        echo "<INFO> Added missing [vlx2mqtt] section to $CFGFILE"
    fi

    ensure_ini_key "$CFGFILE" "topic_identifier" "name"
    ensure_ini_key "$CFGFILE" "rain_poll_interval" "300"
    ensure_ini_key "$CFGFILE" "publish_rain_raw_limit" "0"
else
    echo "<INFO> No config file found at $CFGFILE - skipping migration"
fi

# Cleanup temporary upgrade backup.
if [ -d "$BACKUPROOT" ]; then
    echo "<INFO> Removing temporary backup folder"
    rm -rf "$BACKUPROOT"
fi

echo "<OK> Upgrade restore/migration finished"
exit 0

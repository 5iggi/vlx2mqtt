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

echo "<INFO> vlx2mqtt POSTINSTALL - PDIR=$PDIR PVERSION=$PVERSION"

mkdir -p "$PBIN" "$PCONFIG" "$PDATA" "$PLOGS" || {
  echo "<ERROR> Could not create plugin directories."
  exit 2
}

LOGFILE="$PLOGS/vlx2mqtt.log"
if [ ! -f "$LOGFILE" ]; then
  touch "$LOGFILE" 2>/dev/null || echo "<WARNING> Could not create logfile $LOGFILE"
fi
chmod 664 "$LOGFILE" 2>/dev/null || true


CFGFILE="$PCONFIG/vlx2mqtt.cfg"
BUNDLED_CFG="$PBIN/../config/vlx2mqtt.cfg"
BUNDLED_EXAMPLE_CFG="$PBIN/../config/vlx2mqtt_example.cfg"

# Default-Konfiguration nur beim ersten Installieren anlegen.
# Reihenfolge:
# 1. config/vlx2mqtt.cfg, falls im Paket vorhanden
# 2. config/vlx2mqtt_example.cfg als Vorlage kopieren
# 3. Minimal-Default inline erzeugen, damit der systemd-Dienst auch vor dem ersten
#    Öffnen der Weboberfläche eine gültige Config-Datei hat.
if [ ! -f "$CFGFILE" ]; then
  if [ -f "$BUNDLED_CFG" ]; then
    cp "$BUNDLED_CFG" "$CFGFILE" || {
      echo "<WARNING> Could not copy bundled default config."
    }
    echo "<OK> Created default config from bundled vlx2mqtt.cfg"
  elif [ -f "$BUNDLED_EXAMPLE_CFG" ]; then
    cp "$BUNDLED_EXAMPLE_CFG" "$CFGFILE" || {
      echo "<WARNING> Could not copy bundled example config."
    }
    echo "<OK> Created default config from bundled vlx2mqtt_example.cfg"
  else
    cat > "$CFGFILE" <<'EOF'
[vlx2mqtt]

# KLF200
klf_host = VELUX-KLF.fritz.box
klf_pw = KLF_WiFi_PASSWORT

# MQTT
mqtt_host = 127.0.0.1
mqtt_port = 1883
mqtt_user = loxberry
mqtt_pw = MQTT_PASSWORT
root_topic = vlx2mqtt

# Runtime
initial_delay = 2.5
connect_timeout = 30.0
moving_timeout = 60.0
backoff_max = 30.0
verbose = false
logfile = /opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log
topic_identifier = name

# Rain / Event Monitor
rain_poll_interval = 300
rain_read_timeout = 15.0
rain_skip_during_recovery = true
publish_rain_raw_limit = false
event_monitor_interval = 60
event_stale_warn_seconds = 900

# Recovery / Power-Cycle
external_recovery_enabled = false
external_recovery_threshold = 4
runtime_recovery_command_weight = 2
runtime_recovery_rain_weight = 1
external_recovery_cooldown = 1800
external_recovery_grace = 120
external_recovery_topic = vlx2mqtt/recovery/powercycle_required
preventive_recovery_hours = 0
EOF
    echo "<OK> Created inline default config"
  fi
  chmod 600 "$CFGFILE" 2>/dev/null || true
else
  echo "<INFO> Existing config preserved: $CFGFILE"
fi


# Helper scripts for LoxBerry loglist/daemon wrapper.
for helper in "$PBIN/register_daemon_log.sh" "$PBIN/vlx2mqtt_daemon.pl"; do
  if [ -f "$helper" ]; then
    chmod 755 "$helper" 2>/dev/null || true
  fi
done
if [ -f "$PBIN/register_daemon_log.sh" ]; then
  "$PBIN/register_daemon_log.sh" >/dev/null 2>&1 || true
fi

# Python-Skript ausführbar setzen
if [ -f "$PBIN/vlx2mqtt.py" ]; then
  chmod 755 "$PBIN/vlx2mqtt.py" || {
    echo "<WARNING> Could not chmod vlx2mqtt.py"
  }
fi

echo "<OK> vlx2mqtt POSTINSTALL finished."
exit 0

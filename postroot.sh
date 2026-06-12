#!/bin/bash
# Runs as root AFTER complete installation is done

COMMAND=$0
PTEMPDIR=$1
PSHNAME=$2
PDIR=$3
PVERSION=$4
PTEMPPATH=$6

PBIN=$LBPBIN/$PDIR
PCONFIG=$LBPCONFIG/$PDIR
PDATA=$LBPDATA/$PDIR

VENV="$PDATA/venv"
SERVICE_FILE="/etc/systemd/system/vlx2mqtt.service"

echo "<INFO> vlx2mqtt POSTROOT starting"

mkdir -p "$PDATA" || {
  echo "<ERROR> Could not create plugin data directory."
  exit 2
}

# Virtuelle Python-Umgebung anlegen
if [ ! -x "$VENV/bin/python3" ]; then
  echo "<INFO> Creating virtual environment at $VENV"
  /usr/bin/python3 -m venv "$VENV" || {
    echo "<ERROR> Failed to create Python virtual environment."
    echo "<ERROR> Please ensure python3-venv is installed."
    exit 2
  }
fi

echo "<INFO> Installing Python dependencies into virtual environment"
"$VENV/bin/python3" -m pip install --upgrade pip || {
  echo "<ERROR> Failed to upgrade pip in venv."
  exit 2
}

"$VENV/bin/python3" -m pip install --upgrade pyvlx paho-mqtt || {
  echo "<ERROR> Failed to install Python dependencies."
  exit 2
}

chown -R loxberry:loxberry "$PDATA" || {
  echo "<WARNING> Could not chown plugin data directory"
}

echo "<INFO> Creating systemd service file"
cat <<EOT > "$SERVICE_FILE"
[Unit]
Description=VLX to MQTT bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=loxberry
Group=loxberry
WorkingDirectory=$PBIN
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV/bin/python3 $PBIN/vlx2mqtt.py $PCONFIG/vlx2mqtt.cfg
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOT

chmod 644 "$SERVICE_FILE" || {
  echo "<WARNING> Could not chmod service file"
}

echo "<INFO> Reloading systemd"
systemctl daemon-reload || {
  echo "<ERROR> systemctl daemon-reload failed."
  exit 2
}

echo "<INFO> Enabling vlx2mqtt.service"
systemctl enable vlx2mqtt.service || {
  echo "<WARNING> Could not enable vlx2mqtt.service"
}

echo "<INFO> Restarting vlx2mqtt.service"
systemctl restart vlx2mqtt.service || {
  echo "<WARNING> Could not restart vlx2mqtt.service"
}

echo "<OK> vlx2mqtt POSTROOT finished"
exit 0

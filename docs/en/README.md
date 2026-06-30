<p align="center">
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo" width="100">
</p>

<h1 align="center">VLX2MQTT</h1>

<p align="center">
  <strong>LoxBerry · MQTT · VELUX KLF200 · Loxone Config Export</strong>
</p>

<p align="center">
  <img alt="English" src="https://img.shields.io/badge/Language-English-66AA00?style=flat-square">
  <img alt="LoxBerry" src="https://img.shields.io/badge/LoxBerry-Plugin-66AA00?style=flat-square">
  <img alt="MQTT" src="https://img.shields.io/badge/MQTT-Bridge-blue?style=flat-square">
  <img alt="Loxone" src="https://img.shields.io/badge/Loxone-Export-orange?style=flat-square">
</p>

## Contents

- [Features](#features)
- [Design decisions](#design-decisions)
- [Requirements](#requirements)
- [Installation and operation](#installation-and-operation)
- [Configuration](#configuration)
- [Parameters and meaning](#parameters-and-meaning)
- [Web interface](#web-interface)
- [index.cgi AJAX / JSON endpoints](#indexcgi-ajax--json-endpoints)
- [MQTT topics](#mqtt-topics)
- [Loxone Config export](#loxone-config-export)
- [Rain state](#rain-state)
- [Logging](#logging)
- [Further documentation](#further-documentation)

## Features

- MQTT bridge for **VELUX KLF200 / Homecontrol IO**
- Control via MQTT: `UP`, `DOWN`, `OPEN`, `CLOSE`, `STOP`, `0..100`
- State topics via MQTT: `position`, `moving`, optional `rain`, optional `rain_raw_limit`
- Diagnostic and health topics
- numeric `*_code` status topics for Loxone and visualizations
- topic identifier modes: `name` or `node_id`
- optional external recovery / power-cycle trigger
- optional preventive recovery trigger
- Loxone Config export for Virtual UDP Inputs and Virtual Outputs
- systemd service under LoxBerry

## Design decisions

### Event-driven positions

VLX2MQTT intentionally keeps position and movement updates event-driven via the KLF / pyvlx callback path. There is no permanent position polling in the normal runtime path.

### No interpolation

VLX2MQTT intentionally does not interpolate movements because remaining runtimes reported by the KLF are not reliable enough in all situations.

## Requirements

- LoxBerry
- VELUX KLF200 / Homecontrol IO
- MQTT broker
- Network access between LoxBerry and KLF200
- Python 3 with `pyvlx` and `paho-mqtt`

## Installation and operation

Check service status:

```bash
sudo systemctl status vlx2mqtt.service
```

Restart service:

```bash
sudo systemctl restart vlx2mqtt.service
```

## Configuration

Typical configuration file:

```text
/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg
```

Example:

```ini
[vlx2mqtt]
klf_host = VELUX-KLF.fritz.box
klf_pw = KLF_WIFI_PASSWORD
mqtt_host = 127.0.0.1
mqtt_port = 1883
mqtt_user = loxberry
mqtt_pw = MQTT_PASSWORD
root_topic = vlx2mqtt
initial_delay = 2.5
connect_timeout = 30.0
moving_timeout = 60.0
backoff_max = 30.0
verbose = 0
logfile = /opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log
topic_identifier = name
rain_poll_interval = 300
publish_rain_raw_limit = false
event_monitor_interval = 60
event_stale_warn_seconds = 900
external_recovery_enabled = false
external_recovery_threshold = 4
external_recovery_cooldown = 1800
external_recovery_grace = 120
external_recovery_topic = vlx2mqtt/recovery/powercycle_required
preventive_recovery_hours = 0
```


## Parameters and meaning

| Parameter | Meaning |
|---|---|
| `klf_host` | Hostname or IP address of the KLF200 |
| `klf_pw` | WiFi password of the KLF200 |
| `mqtt_host` | Hostname or IP address of the MQTT broker |
| `mqtt_port` | MQTT port, usually `1883` |
| `mqtt_user` | MQTT username |
| `mqtt_pw` | MQTT password |
| `root_topic` | Top-level MQTT topic, default `vlx2mqtt` |
| `initial_delay` | Delay after startup before publishing the initial snapshot |
| `connect_timeout` | Timeout for establishing the KLF connection |
| `moving_timeout` | Watchdog time for ongoing movements |
| `backoff_max` | Maximum wait time between reconnect attempts |
| `verbose` | `0` = compact log, `1` = debug logging |
| `logfile` | Path to the log file |
| `topic_identifier` | MQTT identifier per node: `name` or `node_id` |
| `rain_poll_interval` | Polling interval for indirect rain state in seconds |
| `publish_rain_raw_limit` | Additionally publishes `rain_raw_limit` |
| `event_monitor_interval` | Diagnostic interval for checking KLF node events |
| `event_stale_warn_seconds` | Warning threshold if no KLF node events arrive |
| `external_recovery_enabled` | Enables external recovery / power-cycle trigger |
| `external_recovery_threshold` | Number of relevant errors before recovery is requested |
| `external_recovery_cooldown` | Minimum interval between recovery requests |
| `external_recovery_grace` | Wait time after external recovery |
| `external_recovery_topic` | MQTT topic for external power-cycle trigger |
| `preventive_recovery_hours` | Optional preventive recovery trigger after X hours, `0` = disabled |

## Web interface

The LoxBerry web interface provides:

- KLF configuration
- MQTT configuration
- topic identifier selection
- rain polling settings
- recovery settings
- event monitor diagnostics
- service actions: Restart, Stop, Show log
- Loxone Config export


## index.cgi AJAX / JSON endpoints

In addition to the normal web interface, `index.cgi` provides simple AJAX / JSON endpoints.

### Query service status

```text
index.cgi?ajax=statusvlx
```

Returns, among other fields:

```json
{
  "error": 0,
  "pid": "1234",
  "state": "active",
  "message": "OK",
  "klf_status": "klf_connected"
}
```

### Restart service

```text
index.cgi?ajax=restartvlx
```

Restarts `vlx2mqtt.service`.

### Stop service

```text
index.cgi?ajax=stopvlx
```

Stops `vlx2mqtt.service`.

### Read MQTT topic once

```text
index.cgi?ajax=gettopic&topic=vlx2mqtt/status_live
```

Reads one MQTT topic once and returns the payload as JSON.

### Optional: Secure PIN

If used, a secure PIN parameter can be added:

```text
index.cgi?ajax=statusvlx&secpin=1234
```

### Supported `ajax` values

```text
statusvlx
restartvlx
stopvlx
gettopic
```

## MQTT topics

The complete topic reference is available in [MQTT_TOPICS.md](MQTT_TOPICS.md).

## Loxone Config export

The complete Loxone documentation is available in [LOXONE.md](LOXONE.md).

Short version:

```text
VIU_VLX2MQTT.xml   virtual UDP inputs
VO_VLX2MQTT.xml    virtual outputs
README             notes and detected nodes
ZIP                all files together
```

## Rain state

For supported windows, VLX2MQTT can publish an indirect rain state.

```text
<root_topic>/<node>/rain
<root_topic>/<node>/rain_raw_limit
```

## Logging

```text
/opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log
```

## Further documentation

- [MQTT topics](MQTT_TOPICS.md)
- [Loxone Config export](LOXONE.md)
- [Recovery / power cycle](RECOVERY.md)
- [Troubleshooting](TROUBLESHOOTING.md)

---

<p align="center">
  <a href="README.md">Back to contents</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

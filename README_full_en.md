<p align="center">
  <img src="icons/icon.svg" width="160" alt="VLX2MQTT logo">

# VLX2MQTT KLF200 Bridge LoxBerry Plugin 
</p>

**VLX2MQTT** is a LoxBerry plugin and a Python-based MQTT bridge for **VELUX KLF200 / Homecontrol IO**.

The plugin connects directly to the KLF200, reads positions and states from windows and shutters, publishes them via MQTT, and processes MQTT commands for control.

---

<a id="contents"></a>
<details>
<summary><strong>Table of contents</strong></summary>

- [Features](#features)
- [Important design decisions](#important-design-decisions)
- [Requirements](#requirements)
- [Configuration](#configuration)
  - [Example](#example)
  - [Important parameters](#important-parameters)
- [MQTT topics](#mqtt-topics)
  - [Status / diagnostics](#status--diagnostics)
  - [Node topics](#node-topics)
  - [Recovery topics](#recovery-topics)
- [Meaning of the most important status topics](#meaning-of-the-most-important-status-topics)
  - [`<root_topic>/status`](#root_topicstatus)
  - [`<root_topic>/status_detail`](#root_topicstatus_detail)
  - [`<root_topic>/status_live`](#root_topicstatus_live)
- [Meaning of the node topics](#meaning-of-the-node-topics)
- [Control via MQTT](#control-via-mqtt)
- [Identifier mode: `name` or `node_id`](#identifier-mode-name-or-node_id)
- [Rain sensor](#rain-sensor)
- [Recovery / power cycle](#recovery--power-cycle)
  - [Recommendation](#recommendation)
  - [Why is there a preventive recovery trigger?](#why-is-there-a-preventive-recovery-trigger)
  - [Recommended usage](#recommended-usage)
  - [Background / sources](#background--sources)
- [Logging](#logging)
- [Files and directories](#files-and-directories)
- [Web interface](#web-interface)
- [Template system / LoxBerry integration](#template-system--loxberry-integration)
- [index.cgi API](#indexcgi-api)
  - [Frontend](#frontend)
  - [AJAX endpoints](#ajax-endpoints)
    - [Query service status](#query-service-status)
    - [Restart service](#restart-service)
    - [Stop service](#stop-service)
    - [Read MQTT topic once](#read-mqtt-topic-once)
  - [Optional: Secure PIN](#optional-secure-pin)
  - [Supported `ajax` values](#supported-ajax-values)
- [Known quirks](#known-quirks)
- [Useful tests](#useful-tests)
- [Uninstallation](#uninstallation)
- [Project status](#project-status)
- [License](#license)
- [Author](#author)

</details>

---

## Features

- MQTT bridge for **VELUX KLF200 / Homecontrol IO**
- Reads positions, states, and movement status from windows and shutters
- Controls windows and shutters via MQTT
- Supports the following MQTT commands:
  - `UP` / `OPEN`
  - `DOWN` / `CLOSE`
  - `STOP`
  - numeric target positions `0..100`
- Publishes diagnostic and status information via MQTT
- Supports two topic identifier modes:
  - `name`
  - `node_id`
- Optionally publishes a rain status for supported windows via MQTT
- Optional external **recovery / power-cycle trigger** in case of KLF connection problems
- Optional **preventive recovery trigger** after a configurable uptime
- Startup snapshot for position and `moving`
- Helpful compact logging when `verbose = 0`

[Back to contents](#contents)

---

## Important design decisions

### No interpolation in this version

This version **deliberately does not interpolate** movements.

**Reason:**  
The remaining runtimes (`remaining_time`) supplied by the KLF are currently not reliable enough in all cases in combination with `pyvlx` to derive stable intermediate positions from them.

**Advantages of this decision:**

- more robust operation
- fewer incorrect intermediate values
- more stable `moving` logic
- easier to understand behaviour in case of errors

[Back to contents](#contents)

---

## Requirements

- **LoxBerry**
- **VELUX KLF200 / Homecontrol IO**
- MQTT broker
- Network connectivity between LoxBerry and KLF200
- Python 3 with `pyvlx` and `paho-mqtt`

[Back to contents](#contents)

---

## Configuration

The central configuration file is typically located at:

```text
/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg
```

### Example

```ini
[vlx2mqtt]
klf_host = VELUX-KLF-DE3B.fritz.box
klf_pw = KLF_WiFi_PASSWORD
mqtt_host = 127.0.0.1
mqtt_port = 1883
mqtt_user = loxberry
mqtt_pw = YOUR_MQTT_PASSWORD
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

external_recovery_enabled = false
external_recovery_threshold = 4
external_recovery_cooldown = 1800
external_recovery_grace = 120
external_recovery_topic = vlx2mqtt/recovery/powercycle_required
preventive_recovery_hours = 0
```

### Important parameters

| Parameter | Meaning |
|---|---|
| `klf_host` | Hostname or IP address of the KLF200 |
| `klf_pw` | WiFi password of the KLF200 |
| `mqtt_host` | MQTT broker |
| `mqtt_port` | MQTT port |
| `mqtt_user` | MQTT username |
| `mqtt_pw` | MQTT password |
| `root_topic` | Top-level MQTT topic |
| `initial_delay` | Delay before the initial snapshot |
| `connect_timeout` | Timeout for establishing the KLF connection |
| `moving_timeout` | Watchdog time for movements |
| `backoff_max` | Maximum reconnect wait time |
| `verbose` | `1` = debug logging, `0` = compact log |
| `logfile` | Path to the log file |
| `topic_identifier` | MQTT identifier per node: `name` or `node_id` |
| `rain_poll_interval` | Polling interval for rain detection in seconds |
| `publish_rain_raw_limit` | additionally publishes the raw value `rain_raw_limit` |
| `external_recovery_enabled` | enables the external recovery / power-cycle trigger |
| `external_recovery_threshold` | number of relevant errors before recovery is requested |
| `external_recovery_cooldown` | minimum interval between two recovery requests |
| `external_recovery_grace` | wait time after external recovery |
| `external_recovery_topic` | MQTT topic for the external power-cycle trigger |
| `preventive_recovery_hours` | preventive recovery trigger after X hours (`0` = disabled) |

[Back to contents](#contents)

---

## MQTT topics

### Status / diagnostics

```text
<root_topic>/status
<root_topic>/status_detail
<root_topic>/status_live
<root_topic>/service_status
<root_topic>/service_detail
<root_topic>/error_text
<root_topic>/health
```

### Node topics

```text
<root_topic>/<Identifier>/position
<root_topic>/<Identifier>/moving
<root_topic>/<Identifier>/set
<root_topic>/<Identifier>/rain
<root_topic>/<Identifier>/rain_raw_limit
```

> `rain` and `rain_raw_limit` are only published for supported window nodes.

### Recovery topics

```text
<root_topic>/recovery/powercycle_required
<root_topic>/recovery/reason
<root_topic>/recovery/failure_count
<root_topic>/recovery/state
```

[Back to contents](#contents)

---

## Meaning of the most important status topics

### `<root_topic>/status`
<a id="root_topicstatus"></a>

A **simple overall status** for logic and visualization.

**Values:**

- `ok`
- `error`

---

### `<root_topic>/status_detail`
<a id="root_topicstatus_detail"></a>

A **stable detailed status** for automation, diagnostics, and history.

`status_detail` is **service-oriented**:

- if the service is **not** running, e.g. `service_starting`, `service_stopped`, `service_lost`
- if the service is running, it typically reflects the current KLF status, e.g. `klf_connected`, `klf_connecting`, `klf_connection_refused`, `klf_auth_failed`, `klf_unreachable`

---

### `<root_topic>/status_live`
<a id="root_topicstatus_live"></a>

A **raw live status** of the KLF connection.

`status_live` always represents the current KLF status directly.

[Back to contents](#contents)

---

## Meaning of the node topics

### `<root_topic>/<Identifier>/position`
Feedback of the current device position.

### `<root_topic>/<Identifier>/set`
Command input for controlling the device. Supports `UP`, `DOWN`, `STOP`, `OPEN`, `CLOSE`, and numeric target positions `0..100`.

### `<root_topic>/<Identifier>/moving`
Movement status derived by the script.

### `<root_topic>/<Identifier>/rain`
Binary rain status for supported windows (`true` / `false`).

### `<root_topic>/<Identifier>/rain_raw_limit`
Optional raw value of the indirect rain detection via the opening limitation.

[Back to contents](#contents)

---

## Control via MQTT

### Examples in `name` mode

```text
vlx2mqtt/Shutter_left/set -> DOWN
vlx2mqtt/Shutter_left/set -> STOP
vlx2mqtt/Shutter_left/set -> 65
```

### Examples in `node_id` mode

```text
vlx2mqtt/2/set -> DOWN
vlx2mqtt/2/set -> STOP
vlx2mqtt/2/set -> 65
```

[Back to contents](#contents)

---

## Identifier mode: `name` or `node_id`

With `topic_identifier`, you can define which identifier is used in the MQTT topic:

- `name` → device / node name, e.g. `Shutter_left`
- `node_id` → numeric KLF node ID, e.g. `2`

If you switch from `name` to `node_id` (or vice versa), **old retained topics** may remain visible in the MQTT broker.

[Back to contents](#contents)

---

## Rain sensor

For supported windows, an indirect rain status is published:

```text
<root_topic>/<Identifier>/rain
<root_topic>/<Identifier>/rain_raw_limit
```

Rain status is determined **indirectly via the window's opening limitation** and polled periodically.

### Technical note

Depending on the `pyvlx` version or node representation used, the required information may be available via different APIs. VLX2MQTT supports both variants:

- `get_limitation_min()`
- `get_limitation()`

### Heuristic

- `raw_limit < 89` → no rain detected
- `raw_limit >= 89` → rain detected

### Important notes

- Rain status is **only published for nodes** that provide the required limitation data.
- Publication is **not** dependent on the device name.
- `rain_raw_limit` is optional and is only published if `publish_rain_raw_limit = true` is set.
- `rain` is a **status topic**, not a control topic.

[Back to contents](#contents)

---

## Recovery / power cycle

In the event of repeated error states such as `klf_connection_refused`, the plugin can optionally publish an external recovery / power-cycle trigger via MQTT.

### Recommendation

- **do not reboot** the KLF on a normal service stop
- use external recovery only for real connection problems
- configure preventive recovery consciously and conservatively

### Why is there a preventive recovery trigger?

In practice, the KLF200 is not always stable over long periods of time when many or repeated connection attempts occur. For this reason, VLX2MQTT optionally supports a **preventive recovery trigger**.

### Recommended usage

- Prefer **reactive recovery** for real faults in normal operation
- Only enable preventive recovery consciously
- Choose preventive intervals conservatively (e.g. 24 hours or more)

### Background / sources

The practical motivation for this mechanism is the instability that is often observed in real KLF200 installations with repeated reconnection attempts or long uptimes.

[Back to contents](#contents)

---

## Logging

Log file:

```text
/opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log
```

### Logging mode

- `verbose = 1` → detailed debug logging
- `verbose = 0` → reduced logging for production use

### Examples for compact logging (`verbose = 0`)

```text
Window_left rain: false (raw_limit=0)
Window_right rain: true (raw_limit=100)
```

[Back to contents](#contents)

---

## Files and directories

### Typical paths under LoxBerry

```text
/opt/loxberry/bin/plugins/vlx2mqtt/vlx2mqtt.py
/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg
/opt/loxberry/data/plugins/vlx2mqtt/venv
/opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log
/etc/systemd/system/vlx2mqtt.service
/opt/loxberry/webfrontend/htmlauth/plugins/vlx2mqtt/index.cgi
/opt/loxberry/templates/plugins/vlx2mqtt/index.html
/opt/loxberry/templates/plugins/vlx2mqtt/lang/language_de.ini
/opt/loxberry/templates/plugins/vlx2mqtt/lang/language_en.ini
```

[Back to contents](#contents)

---

## Web interface

The plugin contains a LoxBerry web interface for configuring:

- KLF200 connection
- MQTT access
- root topic
- logging
- topic identifier (`name` / `node_id`)
- rain polling (`rain_poll_interval`)
- optional `rain_raw_limit`
- recovery / power-cycle settings

In addition, service functions such as **Restart**, **Stop**, and **Show log** are integrated.

[Back to contents](#contents)

---

## Template system / LoxBerry integration

The web interface uses the LoxBerry template system with `HTML::Template`.

Important notes:

- `index.cgi` is placed in the authenticated plugin webfrontend.
- The actual HTML template is located in the plugin's template directory.
- The page is embedded into the LoxBerry layout via `LoxBerry::Web::lbheader()` and `LoxBerry::Web::lbfooter()`.
- Custom templates should **not generate their own `<html>`, `<head>`, or `<body>`**.
- Language files are typically stored under `templates/.../lang/` and are loaded via `readlanguage()`.

[Back to contents](#contents)

---

## index.cgi API

Besides the normal frontend, `index.cgi` also provides simple AJAX / JSON endpoints for status queries and service actions.

### Frontend

Normal web interface:

```text
/admin/plugins/vlx2mqtt/index.cgi
```

### AJAX endpoints

#### Query service status

```text
index.cgi?ajax=statusvlx
```

Returns the current service status as JSON, typically with fields like `error`, `pid`, `state`, `message`, and `klf_status`.

#### Restart service

```text
index.cgi?ajax=restartvlx
```

Restarts the `vlx2mqtt.service` service.

#### Stop service

```text
index.cgi?ajax=stopvlx
```

Stops the `vlx2mqtt.service` service.

#### Read MQTT topic once

```text
index.cgi?ajax=gettopic&topic=<root_topic>/status
```

Reads an MQTT topic once and returns the payload as JSON.

### Optional: Secure PIN

Optionally, a Secure PIN parameter can be provided:

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

[Back to contents](#contents)

---

## Known quirks

- On startup, an old retained `moving=true` state may be briefly visible before the initial status corrects it.
- When switching between `topic_identifier = name` and `topic_identifier = node_id`, old retained topics may remain in the broker.
- Internal KLF timestamps in received frames may differ from the real system time.
- Rain polling depends on `pyvlx` / node support.
- `rain` and `rain_raw_limit` are published only for supported window nodes.

[Back to contents](#contents)

---

## Useful tests

1. Start the plugin
2. Check whether `status = ok` and `status_detail = klf_connected` are set
3. Test in the desired identifier mode
4. Send the MQTT command `DOWN` or `100`
5. Send the MQTT command `STOP`
6. Move to a numeric position
7. Check whether the window rain status (`.../rain`) is published
8. Optionally enable `publish_rain_raw_limit = true` and observe `.../rain_raw_limit`
9. Stop the service cleanly and verify that **no KLF reboot** is triggered
10. Optionally test the recovery topic with an external smart plug / Loxone

[Back to contents](#contents)

---

## Uninstallation

When the plugin is removed, the uninstall script cleans up the externally created `systemd` service in particular.

[Back to contents](#contents)

---

## Project status

The plugin is intentionally designed for **robust, comprehensible operation**. The focus is on a stable MQTT connection of the KLF200 under LoxBerry with clear status and recovery logic.

[Back to contents](#contents)

---

## License

MIT License

[Back to contents](#contents)

---

## Author

**Siggi**  
GitHub: [5iggi](https://github.com/5iggi)

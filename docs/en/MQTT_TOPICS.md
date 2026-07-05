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

# MQTT Topics

This file describes the most important MQTT topics of VLX2MQTT.

## Placeholders

```text
<root_topic>   default: vlx2mqtt
<node>         device name or node_id, depending on topic_identifier
```

Examples:

```text
vlx2mqtt/Fenster_links/position
vlx2mqtt/0/position
```

## Status and diagnostic topics

```text
<root_topic>/status
<root_topic>/status_code
<root_topic>/status_detail
<root_topic>/status_detail_code
<root_topic>/status_live
<root_topic>/status_live_code
<root_topic>/service_status
<root_topic>/service_status_code
<root_topic>/service_detail
<root_topic>/error_text
<root_topic>/health
```

## Numeric status codes

The `*_code` topics provide numeric values for Loxone and other visualizations.  
The corresponding text topics are still published as well.

### `status_code`

Belongs to:

```text
<root_topic>/status
<root_topic>/status_code
```

```text
ok=1
error=0
```

### `status_detail_code`

Belongs to:

```text
<root_topic>/status_detail
<root_topic>/status_detail_code
```

`status_detail` is the stable detailed status. If the service is running, the value usually corresponds to the KLF status. If the service is not running or is starting, the value may be service-related.

```text
klf_connected=1
klf_connecting=2
klf_disconnected=3
klf_unreachable=4
klf_connection_refused=5
klf_auth_failed=6
klf_error=7
starting=8
unknown=99
service_running=1
service_starting=2
service_stopped=0
service_lost=0
service_error=0
```

### `status_live_code`

Belongs to:

```text
<root_topic>/status_live
<root_topic>/status_live_code
```

`status_live` is the raw live status of the KLF connection.

```text
klf_connected=1
klf_connecting=2
klf_disconnected=3
klf_unreachable=4
klf_connection_refused=5
klf_auth_failed=6
klf_error=7
starting=8
unknown=99
```

### `service_status_code`

Belongs to:

```text
<root_topic>/service_status
<root_topic>/service_status_code
```

```text
running=1
starting=2
stopped=0
lost=0
error=0
unknown=99
```

## Node topics

```text
<root_topic>/<node>/position
<root_topic>/<node>/moving
<root_topic>/<node>/set
<root_topic>/<node>/rain
<root_topic>/<node>/rain_raw_limit
```

### `position`

Current position of the device in percent.

```text
0..100
```

### `moving`

Derived movement status.

```text
true
false
```

### `rain`

Indirect rain status for supported windows.

```text
true
false
```

### `rain_raw_limit`

Optional raw value of the indirect rain detection. It is only published if `publish_rain_raw_limit = true` is set.

## Control via MQTT

```text
<root_topic>/<node>/set = UP
<root_topic>/<node>/set = DOWN
<root_topic>/<node>/set = OPEN
<root_topic>/<node>/set = CLOSE
<root_topic>/<node>/set = STOP
<root_topic>/<node>/set = 0..100
```

Examples:

```text
vlx2mqtt/Fenster_links/set = DOWN
vlx2mqtt/Fenster_links/set = STOP
vlx2mqtt/Fenster_links/set = 65
```


## Rain polling and log cleanup

The indirect rain/limitation read also supports these configuration values:

```ini
rain_read_timeout = 15.0
rain_skip_during_recovery = true
```

`rain_read_timeout` limits one KLF/pyvlx limitation read. Known KLF/network failures are logged in compact form with `verbose = 0`; full stack traces remain available with `verbose = 1`.

If `rain_skip_during_recovery = true` is set, rain polling is skipped while `recovery/state=requested` or `recovery/state=waiting`.

## Recovery topics

```text
<root_topic>/recovery/powercycle_required
<root_topic>/recovery/reason
<root_topic>/recovery/reason_code
<root_topic>/recovery/failure_count
<root_topic>/recovery/state
<root_topic>/recovery/state_code
```

### `recovery/state_code`

Belongs to:

```text
<root_topic>/recovery/state
<root_topic>/recovery/state_code
```

```text
idle=0
requested=1
waiting=2
```

### `recovery/reason_code`

Belongs to:

```text
<root_topic>/recovery/reason
<root_topic>/recovery/reason_code
```

```text
none=0
klf_connected=1
klf_connecting=2
klf_disconnected=3
klf_unreachable=4
klf_connection_refused=5
klf_auth_failed=6
klf_error=7
preventive_recovery=10
preventive_interval=10
unknown=99
```

`preventive_interval` is the currently published recovery reason if preventive recovery was triggered by `preventive_recovery_hours`. `preventive_recovery` remains documented as a compatible alias with the same code.

### Runtime recovery weights

During normal operation, recovery-relevant failures are counted with weights:

```ini
runtime_recovery_command_weight = 2
runtime_recovery_rain_weight = 1
```

By default, a failed movement / position command counts `+2`, while a failed rain / limitation read after retry counts `+1`.

### `recovery/state = waiting`

`waiting` means: the recovery threshold has been reached, but `external_recovery_cooldown` is still active. During this state, `powercycle_required=false`. After the cooldown has elapsed, `powercycle_required=true` is set automatically if the KLF is still not connected.

## Health JSON

`<root_topic>/health` contains a JSON summary with status, service state, KLF state, recovery information and counters.

Example:

```json
{
  "status": "ok",
  "status_code": 1,
  "status_detail": "klf_connected",
  "status_detail_code": 1,
  "status_live": "klf_connected",
  "status_live_code": 1,
  "service_state": "running",
  "service_status_code": 1,
  "recovery_requested": false,
  "recovery_waiting": false,
  "recovery_waiting_until": null,
  "recovery_reason": null,
  "recovery_reason_code": 0,
  "failure_count": 0
}
```

---

<p align="center">
  <a href="README.md">Back to contents</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

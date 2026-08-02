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

## Node topics

```text
<root_topic>/<node>/position
<root_topic>/<node>/moving
<root_topic>/<node>/set
<root_topic>/<node>/rain
<root_topic>/<node>/rain_code
<root_topic>/<node>/rain_raw_limit
```

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

## Recovery topics

```text
<root_topic>/recovery/powercycle_required
<root_topic>/recovery/powercycle_required_code
<root_topic>/recovery/reason
<root_topic>/recovery/reason_code
<root_topic>/recovery/failure_count
<root_topic>/recovery/state
<root_topic>/recovery/state_code
```

## Numeric codes

The `*_code` topics provide numeric values for Loxone and other visualizations. The corresponding text topics remain available as well.

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

### `status_live_code`

Belongs to:

```text
<root_topic>/status_live
<root_topic>/status_live_code
```

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

### `<node>/rain_code`

Belongs to:

```text
<root_topic>/<node>/rain
<root_topic>/<node>/rain_code
```

```text
false=0
true=1
```

Meaning:

```text
0 = no rain
1 = rain detected
```

### `recovery/powercycle_required_code`

Belongs to:

```text
<root_topic>/recovery/powercycle_required
<root_topic>/recovery/powercycle_required_code
```

```text
false=0
true=1
```

Meaning:

```text
0 = no power-cycle required
1 = power-cycle required
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

`preventive_interval` is the currently published recovery reason when preventive recovery is triggered by `preventive_recovery_hours`. `preventive_recovery` remains documented as a compatible alias with the same code.

## Health JSON

`<root_topic>/health` contains a JSON summary with status, service state, KLF state, recovery information, status codes and counters.

---

<p align="center">
  <a href="README.md">Back to contents</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

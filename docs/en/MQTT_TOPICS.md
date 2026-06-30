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

## Numeric status codes

```text
ok=1
error=0

klf_connected=1
klf_connecting=2
klf_disconnected=3
klf_unreachable=4
klf_connection_refused=5
klf_auth_failed=6
klf_error=7
starting=8
unknown=99

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
vlx2mqtt/Window_left/set = DOWN
vlx2mqtt/Window_left/set = STOP
vlx2mqtt/Window_left/set = 65
```

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

```text
idle=0
requested=1
waiting=2
```

### `recovery/reason_code`

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
unknown=99
```

## Health JSON

`<root_topic>/health` contains a JSON summary with status, service state, KLF state, recovery information and counters.

---

<p align="center">
  <a href="README.md">Back to contents</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

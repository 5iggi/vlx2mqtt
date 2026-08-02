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

# Recovery / Power-Cycle

VLX2MQTT can request external recovery or a power-cycle when repeated KLF connection problems are detected.

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

## Power-cycle request

```text
<root_topic>/recovery/powercycle_required = true / false
<root_topic>/recovery/powercycle_required_code = 1 / 0
```

```text
0 = no power-cycle required
1 = power-cycle required
```

For Loxone logic, `powercycle_required_code` is recommended.

## Recovery states

```text
state=idle       state_code=0
state=requested  state_code=1
state=waiting    state_code=2
```

## Waiting while cooldown is active

If the threshold is reached while `external_recovery_cooldown` is still active, no immediate power-cycle is requested. VLX2MQTT publishes:

```text
<root_topic>/recovery/powercycle_required = false
<root_topic>/recovery/powercycle_required_code = 0
<root_topic>/recovery/state = waiting
<root_topic>/recovery/state_code = 2
```

After the cooldown expires, `powercycle_required=true` and `powercycle_required_code=1` are published automatically if the KLF is still not connected.

## Runtime recovery

VLX2MQTT detects recovery problems in two ways:

- during startup or reconnect to the KLF200
- during runtime when movement commands or rain / limitation reads fail

Runtime weighting:

```ini
runtime_recovery_command_weight = 2
runtime_recovery_rain_weight = 1
external_recovery_threshold = 4
```

A failed movement / position command counts as `+2` by default. A failed rain / limitation read after retry counts as `+1`.

## Rain polling during recovery

If `rain_skip_during_recovery = true` is set, rain polling is paused while recovery is `requested` or `waiting`. This reduces unnecessary KLF access during a known fault.

---

<p align="center">
  <a href="README.md">Back to contents</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

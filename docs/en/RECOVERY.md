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

VLX2MQTT can optionally publish an external recovery / power-cycle trigger via MQTT after repeated KLF connection problems.

## Purpose

In practice, the KLF200 may become unstable after long uptime, network issues or repeated connection attempts. VLX2MQTT can detect this situation and publish an MQTT topic that can be evaluated by an external automation.

```text
vlx2mqtt/recovery/powercycle_required = true
```

Typical use case: Loxone or another automation briefly switches the external power supply of the KLF200 off and on again.

## When is recovery triggered?

VLX2MQTT distinguishes two types of recovery-relevant failures:

1. **Connect / reconnect failures** during startup or while reconnecting to the KLF200.
2. **Runtime failures** while the bridge is already running, for example if a movement command or rain / limitation read can no longer be sent to the KLF200.

Runtime failures are counted with weights:

```ini
runtime_recovery_command_weight = 2
runtime_recovery_rain_weight = 1
```

Default behavior:

```text
failed movement / position command = +2
failed rain / limitation read after retry = +1
```

If the weighted failure counter reaches `external_recovery_threshold` and no cooldown is active, `powercycle_required=true` is published.

## Relevant error states

```text
klf_connection_refused
klf_disconnected
klf_unreachable
```

## Configuration

```ini
external_recovery_enabled = false
external_recovery_threshold = 4
runtime_recovery_command_weight = 2
runtime_recovery_rain_weight = 1
rain_read_timeout = 15.0
rain_skip_during_recovery = true
external_recovery_cooldown = 1800
external_recovery_grace = 120
external_recovery_topic = vlx2mqtt/recovery/powercycle_required
preventive_recovery_hours = 0
```

## Topics

```text
<root_topic>/recovery/powercycle_required
<root_topic>/recovery/reason
<root_topic>/recovery/reason_code
<root_topic>/recovery/failure_count
<root_topic>/recovery/state
<root_topic>/recovery/state_code
```

## Status codes

```text
idle=0
requested=1
waiting=2
```

## Sequence without active cooldown

If `external_recovery_enabled = true` is set, the weighted failure counter reaches the threshold and no cooldown is active, VLX2MQTT publishes:

```text
/recovery/powercycle_required = true
/recovery/state = requested
/recovery/state_code = 1
/recovery/reason = <KLF failure reason>
/recovery/reason_code = <numeric reason>
```

## Sequence with active cooldown

If the threshold is reached while `external_recovery_cooldown` is still active, **no immediate power-cycle** is requested. Instead, VLX2MQTT enters the `waiting` state:

```text
/recovery/powercycle_required = false
/recovery/state = waiting
/recovery/state_code = 2
/recovery/reason = <KLF failure reason>
/recovery/reason_code = <numeric reason>
```

After the cooldown has elapsed, `powercycle_required=true` is set automatically if the KLF200 is still not connected. If the KLF200 reconnects before the cooldown expires, the waiting state is cleared automatically.

## Runtime recovery log cleanup

While `recovery/state=requested` or `recovery/state=waiting`, rain polling is skipped if `rain_skip_during_recovery = true`. This avoids additional limitation reads against the KLF during a known KLF fault.

`rain_read_timeout` limits one rain/limitation read. Known KLF/pyvlx network failures are logged in compact form without long stack traces when `verbose = 0`. Full stack traces remain available with `verbose = 1`.

## Recommendation

- Only enable external recovery if an external power-cycle setup actually exists.
- Use a sufficiently large `external_recovery_cooldown` in production, for example `1800` seconds.
- For testing, `external_recovery_cooldown` can be temporarily reduced, for example to `60` seconds.
- Set `external_recovery_grace` so that the KLF can become fully reachable again after the power-cycle.
- Do not trigger a KLF reboot on a normal service stop.
- Use preventive recovery deliberately and conservatively.

---

<p align="center">
  <a href="README.md">Back to contents</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

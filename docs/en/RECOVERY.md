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

# Recovery / Power Cycle

VLX2MQTT can optionally publish an external recovery / power-cycle trigger via MQTT when repeated KLF connection problems occur.

## Goal

In practice, the KLF200 may become unstable after long runtime or repeated connection attempts. VLX2MQTT can detect this state and set an MQTT topic that can be evaluated by external automation.

```text
vlx2mqtt/recovery/powercycle_required = true
```

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

## Recommendation

- Enable external recovery only if an external power-cycle device actually exists.
- Choose `external_recovery_cooldown` high enough.
- Set `external_recovery_grace` so that the KLF is fully reachable again after a power cycle.
- Do not trigger a KLF reboot on a normal service stop.
- Use preventive recovery consciously and conservatively.

---

<p align="center">
  <a href="README.md">Back to contents</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

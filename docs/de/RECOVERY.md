<p align="center">
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo" width="100">
</p>

<h1 align="center">VLX2MQTT</h1>

<p align="center">
  <strong>LoxBerry · MQTT · VELUX KLF200 · Loxone Config Export</strong>
</p>

<p align="center">
  <img alt="Deutsch" src="https://img.shields.io/badge/Sprache-Deutsch-66AA00?style=flat-square">
  <img alt="LoxBerry" src="https://img.shields.io/badge/LoxBerry-Plugin-66AA00?style=flat-square">
  <img alt="MQTT" src="https://img.shields.io/badge/MQTT-Bridge-blue?style=flat-square">
  <img alt="Loxone" src="https://img.shields.io/badge/Loxone-Export-orange?style=flat-square">
</p>

# Recovery / Power-Cycle

VLX2MQTT kann bei wiederholten KLF-Verbindungsproblemen optional einen externen Recovery-/Power-Cycle-Trigger per MQTT veröffentlichen.

## Ziel

Die KLF200 kann in der Praxis nach längerer Laufzeit oder nach wiederholten Verbindungsversuchen instabil reagieren. VLX2MQTT kann diesen Zustand erkennen und ein MQTT-Topic setzen, das eine externe Automatisierung auswerten kann.

```text
vlx2mqtt/recovery/powercycle_required = true
```

## Relevante Fehlerzustände

```text
klf_connection_refused
klf_disconnected
klf_unreachable
```

## Konfiguration

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

## Statuscodes

```text
idle=0
requested=1
waiting=2
```

## Empfehlung

- Externe Recovery nur aktivieren, wenn ein externer Power-Cycle wirklich vorhanden ist.
- `external_recovery_cooldown` ausreichend groß wählen.
- `external_recovery_grace` so setzen, dass die KLF nach Power-Cycle wieder vollständig erreichbar ist.
- Kein KLF-Reboot beim normalen Stop des Dienstes auslösen.
- Präventive Recovery nur bewusst und konservativ verwenden.

---

<p align="center">
  <a href="README.md">Zurück zum Inhalt</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

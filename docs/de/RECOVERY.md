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

Die KLF200 kann in der Praxis nach längerer Laufzeit, nach Netzwerkproblemen oder nach wiederholten Verbindungsversuchen instabil reagieren. VLX2MQTT kann diesen Zustand erkennen und ein MQTT-Topic setzen, das eine externe Automatisierung auswerten kann.

```text
vlx2mqtt/recovery/powercycle_required = true
```

Typischer Anwendungsfall: Loxone oder eine andere Automatisierung schaltet daraufhin die externe Stromversorgung der KLF200 kurz aus und wieder ein.

## Wann wird Recovery ausgelöst?

VLX2MQTT unterscheidet zwei Arten von Recovery-relevanten Fehlern:

1. **Connect-/Reconnect-Fehler** beim Start oder beim Wiederverbinden zur KLF200.
2. **Runtime-Fehler** im laufenden Betrieb, z. B. wenn ein Fahrbefehl oder eine Regen-/Limitation-Abfrage nicht mehr an die KLF200 gesendet werden kann.

Runtime-Fehler werden gewichtet gezählt:

```ini
runtime_recovery_command_weight = 2
runtime_recovery_rain_weight = 1
```

Standardmäßig gilt:

```text
fehlgeschlagener Fahr-/Positionsbefehl = +2
fehlgeschlagene Regen-/Limitation-Abfrage nach Retry = +1
```

Wenn der gewichtete Fehlerzähler `external_recovery_threshold` erreicht und kein Cooldown aktiv ist, wird `powercycle_required=true` veröffentlicht.

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

## Statuscodes

```text
idle=0
requested=1
waiting=2
```

## Ablauf ohne aktiven Cooldown

Wenn `external_recovery_enabled = true` gesetzt ist, der gewichtete Fehlerzähler den Schwellwert erreicht und kein Cooldown aktiv ist, publiziert VLX2MQTT:

```text
/recovery/powercycle_required = true
/recovery/state = requested
/recovery/state_code = 1
/recovery/reason = <KLF-Fehlergrund>
/recovery/reason_code = <numerischer Grund>
```

## Ablauf mit aktivem Cooldown

Wenn der Schwellwert erreicht ist, aber `external_recovery_cooldown` noch aktiv ist, wird **kein sofortiger Power-Cycle** angefordert. Stattdessen geht VLX2MQTT in den Zustand `waiting`:

```text
/recovery/powercycle_required = false
/recovery/state = waiting
/recovery/state_code = 2
/recovery/reason = <KLF-Fehlergrund>
/recovery/reason_code = <numerischer Grund>
```

Nach Ablauf des Cooldowns wird automatisch `powercycle_required=true` gesetzt, wenn die KLF200 weiterhin nicht verbunden ist. Wenn die KLF200 vor Ablauf des Cooldowns wieder verbunden ist, wird der Waiting-Zustand automatisch gelöscht.

## Runtime-Recovery Log-Cleanup

Während `recovery/state=requested` oder `recovery/state=waiting` wird Rain-Polling bei `rain_skip_during_recovery = true` übersprungen. Dadurch werden während einer bekannten KLF-Störung keine zusätzlichen Limitation-Abfragen gegen die KLF gesendet.

`rain_read_timeout` begrenzt eine einzelne Regen-/Limitation-Abfrage. Bekannte KLF-/pyvlx-Netzwerkfehler werden bei `verbose = 0` kompakt ohne langen Stacktrace geloggt. Bei `verbose = 1` bleiben vollständige Stacktraces verfügbar.

## Empfehlung

- Externe Recovery nur aktivieren, wenn ein externer Power-Cycle wirklich vorhanden ist.
- `external_recovery_cooldown` produktiv ausreichend groß wählen, z. B. `1800` Sekunden.
- Zum Testen kann `external_recovery_cooldown` temporär reduziert werden, z. B. auf `60` Sekunden.
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

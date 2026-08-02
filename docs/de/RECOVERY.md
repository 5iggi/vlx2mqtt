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

VLX2MQTT kann bei wiederholten KLF-Verbindungsproblemen eine externe Recovery bzw. einen Power-Cycle anfordern.

## Recovery-Topics

```text
<root_topic>/recovery/powercycle_required
<root_topic>/recovery/powercycle_required_code
<root_topic>/recovery/reason
<root_topic>/recovery/reason_code
<root_topic>/recovery/failure_count
<root_topic>/recovery/state
<root_topic>/recovery/state_code
```

## Power-Cycle Anforderung

```text
<root_topic>/recovery/powercycle_required = true / false
<root_topic>/recovery/powercycle_required_code = 1 / 0
```

```text
0 = kein Power-Cycle erforderlich
1 = Power-Cycle erforderlich
```

Für Loxone-Logik wird `powercycle_required_code` empfohlen.

## Recovery-Zustände

```text
state=idle       state_code=0
state=requested  state_code=1
state=waiting    state_code=2
```

## Waiting bei aktivem Cooldown

Wenn der Schwellwert erreicht ist, aber `external_recovery_cooldown` noch aktiv ist, wird kein sofortiger Power-Cycle ausgelöst. VLX2MQTT veröffentlicht dann:

```text
<root_topic>/recovery/powercycle_required = false
<root_topic>/recovery/powercycle_required_code = 0
<root_topic>/recovery/state = waiting
<root_topic>/recovery/state_code = 2
```

Nach Ablauf des Cooldowns wird automatisch `powercycle_required=true` und `powercycle_required_code=1` gesetzt, wenn die KLF weiterhin nicht verbunden ist.

## Runtime-Recovery

VLX2MQTT erkennt Recovery-Probleme auf zwei Wegen:

- beim Start oder Reconnect zur KLF200
- im laufenden Betrieb, wenn Fahrbefehle oder Regen-/Limitation-Abfragen fehlschlagen

Gewichtung im laufenden Betrieb:

```ini
runtime_recovery_command_weight = 2
runtime_recovery_rain_weight = 1
external_recovery_threshold = 4
```

Ein fehlgeschlagener Fahr-/Positionsbefehl zählt standardmäßig `+2`, eine fehlgeschlagene Regen-/Limitation-Abfrage nach Retry `+1`.

## Rain-Poll während Recovery

Wenn `rain_skip_during_recovery = true` gesetzt ist, wird Rain-Polling während `requested` oder `waiting` pausiert. Dadurch werden unnötige KLF-Zugriffe während einer bekannten Störung reduziert.

---

<p align="center">
  <a href="README.md">Zurück zum Inhalt</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

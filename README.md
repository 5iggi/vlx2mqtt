# VLX2MQTT KLF200 Bridge <img src="icons/icon.svg" width="96">

**VLX2MQTT** ist ein LoxBerry-Plugin und eine Python-basierte MQTT-Bridge für **VELUX KLF200 / Homecontrol IO**.  
Die Bridge verbindet sich direkt mit der KLF200, veröffentlicht Zustände per MQTT und verarbeitet MQTT-Kommandos zur Steuerung von Fenstern und Rollläden.

## Highlights

- MQTT-Bridge für **VELUX KLF200 / Homecontrol IO**
- Steuerung per MQTT: `UP`, `DOWN`, `OPEN`, `CLOSE`, `STOP`, `0..100`
- Zustände per MQTT: `position`, `moving`, optional `rain`, `rain_raw_limit`
- Zwei Identifier-Modi für Topics:
  - `name`
  - `node_id`
- Diagnose- und Health-Topics für Monitoring
- Optionaler Recovery-/Power-Cycle-Trigger
- Startup-Snapshot für Position und `moving`
- Kompaktes, aussagekräftiges Logging bei `verbose = 0`
- Betrieb als `systemd`-Dienst unter LoxBerry

## Voraussetzungen

- LoxBerry
- VELUX KLF200 / Homecontrol IO
- MQTT-Broker
- Netzwerkzugriff zwischen LoxBerry und KLF200

## Konfiguration

Konfigurationsdatei:

```text
/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg
```

## Dokumentation

[README_full.md](README_full.md)

<p align="center">
  <img src="icons/icon.svg" width="120" alt="VLX2MQTT logo">
</p>

<h1 align="center">VLX2MQTT</h1>
<p align="center"><strong>KLF200 Bridge for LoxBerry · MQTT · VELUX Homecontrol IO</strong></p>

<p align="center">
  <a href="README_full_de.md"><img alt="Deutsch" src="https://img.shields.io/badge/Docs-DE-1f6feb?style=for-the-badge"></a>
  <a href="README_full_en.md"><img alt="English" src="https://img.shields.io/badge/Docs-EN-2ea043?style=for-the-badge"></a>
  <a href="README_full.md"><img alt="Hub" src="https://img.shields.io/badge/Docs-Hub-f59e0b?style=for-the-badge"></a>
</p>

---

## 🇩🇪 Deutsch

**VLX2MQTT** ist ein LoxBerry-Plugin und eine Python-basierte MQTT-Bridge für **VELUX KLF200 / Homecontrol IO**.  
Die Bridge verbindet sich direkt mit der KLF200, veröffentlicht Zustände per MQTT und verarbeitet MQTT-Kommandos zur Steuerung von Fenstern und Rollläden.

### Highlights

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

### Voraussetzungen

- LoxBerry
- VELUX KLF200 / Homecontrol IO
- MQTT-Broker
- Netzwerkzugriff zwischen LoxBerry und KLF200

### Konfiguration

Konfigurationsdatei:

```text
/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg
```

### Dokumentation

- Vollständige deutsche Dokumentation: [README_full_de.md](README_full_de.md)
- Dokumentations-Startseite: [README_full.md](README_full.md)

---

## 🇬🇧 English

**VLX2MQTT** is a LoxBerry plugin and a Python-based MQTT bridge for **VELUX KLF200 / Homecontrol IO**.  
The bridge connects directly to the KLF200, publishes states via MQTT, and processes MQTT commands to control windows and shutters.

### Highlights

- MQTT bridge for **VELUX KLF200 / Homecontrol IO**
- MQTT control: `UP`, `DOWN`, `OPEN`, `CLOSE`, `STOP`, `0..100`
- MQTT state topics: `position`, `moving`, optionally `rain`, `rain_raw_limit`
- Two identifier modes for topics:
  - `name`
  - `node_id`
- Diagnostic and health topics for monitoring
- Optional recovery / power-cycle trigger
- Startup snapshot for position and `moving`
- Compact, meaningful logging with `verbose = 0`
- Runs as a `systemd` service on LoxBerry

### Requirements

- LoxBerry
- VELUX KLF200 / Homecontrol IO
- MQTT broker
- Network connectivity between LoxBerry and KLF200

### Configuration

Configuration file:

```text
/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg
```


---

## Documentation

🌐 [Documentation Hub](README_full.md)

---

<p align="center">
  <img src="icons/icon.svg" width="64" alt="VLX2MQTT logo small"><br>
  <strong>VLX2MQTT</strong><br>
  MQTT • LoxBerry • VELUX KLF200
</p>

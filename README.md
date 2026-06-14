# VLX2MQTT KLF200 Bridge <img src="icons/icon.svg" width="96">

**VLX2MQTT** ist ein LoxBerry-Plugin und eine Python-basierte MQTT-Bridge für **VELUX KLF200 / Homecontrol IO**. Die Bridge verbindet sich direkt mit der KLF200, veröffentlicht Zustände per MQTT und verarbeitet MQTT-Kommandos zur Steuerung von Fenstern und Rollläden.

## Highlights

- MQTT-Bridge für **VELUX KLF200 / Homecontrol IO**
- Steuerung per MQTT: `UP`, `DOWN`, `OPEN`, `CLOSE`, `STOP`, `0..100`
- Zustände per MQTT: `position`, `moving`, `rain`, `rain_raw_limit`
- Zwei Identifier-Modi für Topics:
  - `name`
  - `node_id`
- Diagnose- und Health-Topics für Monitoring
- Optionaler Recovery-/Power-Cycle-Trigger
- Betrieb als `systemd`-Dienst unter LoxBerry

## Voraussetzungen

- LoxBerry
- VELUX KLF200 / Homecontrol IO
- MQTT-Broker
- Netzwerkzugriff zwischen LoxBerry und KLF200

## Konfiguration

Konfigurationsdatei:

```ini
/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg
```

Kurzbeispiel:

```ini
[vlx2mqtt]
klf_host = VELUX-KLF-DE3B.fritz.box
klf_pw = DEIN_KLF_PASSWORT
mqtt_host = 127.0.0.1
mqtt_port = 1883
mqtt_user = loxberry
mqtt_pw = DEIN_MQTT_PASSWORT
root_topic = vlx2mqtt
verbose = 0

topic_identifier = node_id
rain_poll_interval = 60
publish_rain_raw_limit = true

external_recovery_enabled = true
external_recovery_threshold = 4
external_recovery_cooldown = 1800
external_recovery_grace = 120
external_recovery_topic = vlx2mqtt/recovery/powercycle_required
preventive_recovery_hours = 24
```

Wichtige Parameter:

- `topic_identifier` → `name` oder `node_id`
- `rain_poll_interval` → Polling-Intervall für den Regensensor
- `publish_rain_raw_limit` → zusätzlicher Rohwert `rain_raw_limit`
- `external_recovery_*` → Recovery-/Power-Cycle-Logik

## MQTT-Topics

### Status / Diagnose

```text
<root_topic>/status
<root_topic>/status_detail
<root_topic>/status_live
<root_topic>/service_status
<root_topic>/service_detail
<root_topic>/error_text
<root_topic>/health
```

### Node-Topics

```text
<root_topic>/<Identifier>/position
<root_topic>/<Identifier>/moving
<root_topic>/<Identifier>/set
<root_topic>/<Identifier>/rain
<root_topic>/<Identifier>/rain_raw_limit
```

> `rain` und `rain_raw_limit` werden nur für unterstützte Fensternodes veröffentlicht.

## Identifier-Modus

Der MQTT-Identifier pro Node kann über `topic_identifier` festgelegt werden:

- `name` → z. B. `vlx2mqtt/Rollladen_links/set`
- `node_id` → z. B. `vlx2mqtt/2/set`

Beispiel-Zuordnung aus einem typischen Setup:

```text
Fenster_links    -> 0
Fenster_rechts   -> 1
Rollladen_links  -> 2
Rollladen_rechts -> 3
```

### Wichtiger Hinweis beim Umschalten

Beim Wechsel zwischen `name` und `node_id` können alte **retained MQTT-Topics** im Broker verbleiben. Diese sollten einmal bereinigt werden, damit keine veralteten Werte in Loxone oder MQTT Explorer sichtbar bleiben.

## Regensensor

Für unterstützte Fenster veröffentlicht VLX2MQTT einen indirekten Regenstatus:

```text
<root_topic>/<Identifier>/rain
<root_topic>/<Identifier>/rain_raw_limit
```

Im `node_id`-Modus z. B.:

```text
vlx2mqtt/0/rain
vlx2mqtt/0/rain_raw_limit
vlx2mqtt/1/rain
vlx2mqtt/1/rain_raw_limit
```

## Weboberfläche

Die LoxBerry-Weboberfläche bietet u. a. folgende Einstellungen:

- KLF200-Verbindung
- MQTT-Zugang
- Root-Topic
- Logging
- `topic_identifier`
- `rain_poll_interval`
- `publish_rain_raw_limit`
- Recovery-/Power-Cycle-Parameter

Zusätzlich sind **Restart**, **Stop** und **Log anzeigen** integriert.

## Dateien / Pfade

```text
/opt/loxberry/bin/plugins/vlx2mqtt/vlx2mqtt.py
/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg
/opt/loxberry/data/plugins/vlx2mqtt/venv
/opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log
/etc/systemd/system/vlx2mqtt.service
```

## Hinweise

- Diese Version arbeitet **bewusst ohne Interpolation** von Bewegungen.
- Im `node_id`-Modus werden Status-Themen numerisch publiziert, eingehende Commands werden weiterhin über `<root_topic>/+/set` entgegengenommen.
- Der Dienst publiziert Diagnose- und Health-Informationen für Loxone / Node-RED.

## Lizenz

MIT License

## Autor

**Siggi**  
GitHub: [5iggi](https://github.com/5iggi)

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

## Inhalt

- [Funktionen](#funktionen)
- [Design-Entscheidungen](#design-entscheidungen)
- [Voraussetzungen](#voraussetzungen)
- [Installation und Betrieb](#installation-und-betrieb)
- [Konfiguration](#konfiguration)
- [Parameter und Bedeutung](#parameter-und-bedeutung)
- [Weboberfläche](#weboberfläche)
- [index.cgi AJAX-/JSON-Endpunkte](#indexcgi-ajax-json-endpunkte)
- [MQTT Topics](#mqtt-topics)
- [Loxone Config Export](#loxone-config-export)
- [Regenstatus](#regenstatus)
- [Logging](#logging)
- [Weitere Dokumentation](#weitere-dokumentation)

## Funktionen

- MQTT-Bridge für **VELUX KLF200 / Homecontrol IO**
- Steuerung per MQTT: `UP`, `DOWN`, `OPEN`, `CLOSE`, `STOP`, `0..100`
- Status per MQTT: `position`, `moving`, optional `rain`, optional `rain_raw_limit`
- Diagnose- und Health-Topics
- numerische `*_code` Status-Topics für Loxone und Visualisierungen
- Topic-Identifier-Modi: `name` oder `node_id`
- optionaler externer Recovery-/Power-Cycle-Trigger
- optionaler präventiver Recovery-Trigger
- Loxone Config Export für Virtual UDP Inputs und Virtual Outputs
- systemd-Dienst unter LoxBerry

## Design-Entscheidungen

### Eventbasierte Positionen

VLX2MQTT hält Positions- und Bewegungsupdates bewusst eventbasiert über den KLF-/pyvlx-Callback-Pfad. Es gibt im normalen Laufzeitpfad kein permanentes Positions-Polling.

### Keine Interpolation

VLX2MQTT interpoliert Bewegungen bewusst nicht, weil die vom KLF gelieferten Restlaufzeiten nicht in allen Situationen zuverlässig genug sind.

## Voraussetzungen

- LoxBerry
- VELUX KLF200 / Homecontrol IO
- MQTT-Broker
- Netzwerkzugriff zwischen LoxBerry und KLF200
- Python 3 mit `pyvlx` und `paho-mqtt`

## Installation und Betrieb

Dienststatus prüfen:

```bash
sudo systemctl status vlx2mqtt.service
```

Dienst neu starten:

```bash
sudo systemctl restart vlx2mqtt.service
```

## Konfiguration

Typische Konfigurationsdatei:

```text
/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg
```

Beispiel:

```ini
[vlx2mqtt]

# KLF200
klf_host = VELUX-KLF.fritz.box
klf_pw = KLF_WiFi_PASSWORT

# MQTT
mqtt_host = 127.0.0.1
mqtt_port = 1883
mqtt_user = loxberry
mqtt_pw = MQTT_PASSWORT
root_topic = vlx2mqtt

# Runtime
initial_delay = 2.5
connect_timeout = 30.0
moving_timeout = 60.0
backoff_max = 30.0
verbose = false
logfile = /opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log
topic_identifier = name

# Rain / Event Monitor
rain_poll_interval = 300
rain_read_timeout = 15.0
rain_skip_during_recovery = true
publish_rain_raw_limit = false
event_monitor_interval = 60
event_stale_warn_seconds = 900

# Recovery / Power-Cycle
external_recovery_enabled = false
external_recovery_threshold = 4
runtime_recovery_command_weight = 2
runtime_recovery_rain_weight = 1
external_recovery_cooldown = 1800
external_recovery_grace = 120
external_recovery_topic = vlx2mqtt/recovery/powercycle_required
preventive_recovery_hours = 0
```


## Parameter und Bedeutung

| Parameter | Bedeutung |
|---|---|
| `klf_host` | Hostname oder IP-Adresse der KLF200 |
| `klf_pw` | WiFi-Passwort der KLF200 |
| `mqtt_host` | Hostname oder IP-Adresse des MQTT-Brokers |
| `mqtt_port` | MQTT-Port, normalerweise `1883` |
| `mqtt_user` | MQTT-Benutzername |
| `mqtt_pw` | MQTT-Passwort |
| `root_topic` | Oberstes MQTT-Topic, Standard `vlx2mqtt` |
| `initial_delay` | Wartezeit nach Start bis zum initialen Snapshot |
| `connect_timeout` | Timeout für den KLF-Verbindungsaufbau |
| `moving_timeout` | Watchdog-Zeit für laufende Bewegungen |
| `backoff_max` | Maximale Wartezeit zwischen Wiederverbindungsversuchen |
| `verbose` | `0` = kompakter Log, `1` = Debug-Logging |
| `logfile` | Pfad zur Logdatei |
| `topic_identifier` | MQTT-Identifier pro Node: `name` oder `node_id` |
| `rain_poll_interval` | Polling-Intervall für indirekten Regenstatus in Sekunden |
| `rain_read_timeout` | Timeout je Regen-/Limitation-Abfrage; verhindert lange KLF-/SSL-Hänger im normalen Log |
| `rain_skip_during_recovery` | Überspringt Rain-Polling während `recovery/state=requested` oder `waiting` |
| `publish_rain_raw_limit` | Veröffentlicht zusätzlich `rain_raw_limit` |
| `event_monitor_interval` | Diagnoseintervall zur Prüfung von KLF-Node-Events |
| `event_stale_warn_seconds` | Warnschwelle, wenn keine KLF-Node-Events eintreffen |
| `external_recovery_enabled` | Aktiviert externen Recovery-/Power-Cycle-Trigger |
| `external_recovery_threshold` | Anzahl relevanter Fehler bis Recovery angefordert wird |
| `external_recovery_cooldown` | Mindestabstand zwischen Recovery-Anforderungen |
| `external_recovery_grace` | Wartezeit nach externer Recovery |
| `external_recovery_topic` | MQTT-Topic für externen Power-Cycle-Trigger |
| `preventive_recovery_hours` | Optionaler präventiver Recovery-Trigger nach X Stunden, `0` = deaktiviert |

## Weboberfläche

Die LoxBerry-Weboberfläche bietet:

- KLF-Konfiguration
- MQTT-Konfiguration
- Topic-Identifier-Auswahl
- Regen-Polling-Einstellungen inkl. `rain_read_timeout` und Recovery-Skip
- Recovery-Einstellungen
- Event-Monitor-Diagnose
- Servicefunktionen: Restart, Stop, Log anzeigen, LoxBerry-Logs
- Loxone Config Export


### Logansichten

Die Weboberfläche unterscheidet zwei Logzugänge:

- **Log anzeigen** öffnet das direkte Daemon-/KLF-Log `vlx2mqtt.log` im LoxBerry Log Viewer.
- **LoxBerry-Logs** öffnet die von LoxBerry erzeugte Logliste über `showlog=sessions` und `loglist_html()`.

Die LoxBerry-Logliste wird nicht als eigene Dateiliste nachgebaut. Die Ausgabe stammt aus der LoxBerry-Logverwaltung und bleibt deshalb für Collapsible-Bereiche, Log-Level-Auswahl, Sprache und Log-Viewer-Links systemkonform. Systemseitig erzeugte Schaltflächen oder Beschriftungen der LoxBerry-Logliste werden nicht durch VLX2MQTT übersetzt oder mit eigenen Icons überschrieben.

## index.cgi AJAX-/JSON-Endpunkte

Zusätzlich zur normalen Weboberfläche stellt `index.cgi` einfache AJAX-/JSON-Endpunkte bereit.

### Service-Status abfragen

```text
index.cgi?ajax=statusvlx
```

Liefert unter anderem:

```json
{
  "error": 0,
  "pid": "1234",
  "state": "active",
  "message": "OK",
  "klf_status": "klf_connected"
}
```

### Dienst neu starten

```text
index.cgi?ajax=restartvlx
```

Startet `vlx2mqtt.service` neu.

### Dienst stoppen

```text
index.cgi?ajax=stopvlx
```

Stoppt `vlx2mqtt.service`.

### MQTT-Topic einmalig lesen

```text
index.cgi?ajax=gettopic&topic=vlx2mqtt/status_live
```

Liest ein MQTT-Topic einmalig und liefert die Payload als JSON zurück.

### Optional: Secure PIN

Wenn verwendet, kann ein Secure-PIN-Parameter ergänzt werden:

```text
index.cgi?ajax=statusvlx&secpin=1234
```

### Unterstützte `ajax`-Werte

```text
statusvlx
restartvlx
stopvlx
gettopic
```

## MQTT Topics

Die vollständige Topic-Referenz steht in [MQTT_TOPICS.md](MQTT_TOPICS.md).

## Loxone Config Export

Die vollständige Loxone-Dokumentation steht in [LOXONE.md](LOXONE.md).

Kurzfassung:

```text
VIU_VLX2MQTT.xml   virtuelle UDP-Eingänge
VO_VLX2MQTT.xml    virtuelle Ausgänge
README             Hinweise und erkannte Nodes
ZIP                alles zusammen
```

## Regenstatus

Für unterstützte Fenster kann VLX2MQTT einen indirekten Regenstatus veröffentlichen. Die Abfrage nutzt `rain_read_timeout`, damit eine hängende KLF-/SSL-Verbindung nicht lange blockiert. Während einer externen Recovery (`requested` oder `waiting`) kann Rain-Polling mit `rain_skip_during_recovery = true` pausiert werden.

```text
<root_topic>/<node>/rain
<root_topic>/<node>/rain_raw_limit
```

## Logging

Bei `verbose = 0` werden bekannte KLF-/pyvlx-Netzwerkfehler kompakt geloggt. Vollständige Stacktraces bleiben bei `verbose = 1` verfügbar.


```text
/opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log
```

### Daemon-Log und LoxBerry-Logliste

Das laufende Python-Programm schreibt weiterhin in die feste Logdatei:

```text
/opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log
```

Damit diese Datei auch in der LoxBerry-Logliste erscheint, wird sie bei Installation oder Upgrade über das LoxBerry Logging SDK registriert. Die Registrierung erfolgt über:

```text
/opt/loxberry/bin/plugins/vlx2mqtt/register_daemon_log.sh
```

Dieses Skript ist kein dauerhaft laufender Dienst. Es dient der Log-Registrierung während Installation/Upgrade und kann bei Bedarf manuell erneut ausgeführt werden, zum Beispiel wenn die LoxBerry-Logdatenbank bereinigt oder neu aufgebaut wurde.

Der systemd-Dienst startet VLX2MQTT über einen kleinen Wrapper:

```text
/opt/loxberry/bin/plugins/vlx2mqtt/vlx2mqtt_daemon.pl
```

Der Wrapper hält den Dienststart einheitlich und startet anschließend den Python-Daemon. Die Logregistrierung ist bewusst nicht an jeden Daemon-Start gekoppelt.

Der direkte Daemon-Logviewer wird ohne `only=once` geöffnet, damit die Auto-Scroll-Funktion des LoxBerry Log Viewers erhalten bleibt.

## Weitere Dokumentation

- [MQTT Topics](MQTT_TOPICS.md)
- [Loxone Config Export](LOXONE.md)
- [Recovery / Power-Cycle](RECOVERY.md)
- [Troubleshooting](TROUBLESHOOTING.md)

---

<p align="center">
  <a href="README.md">Zurück zum Inhalt</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

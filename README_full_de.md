<p align="center">
  <img src="icons/icon.svg" width="160" alt="VLX2MQTT logo">

# VLX2MQTT KLF200 Bridge LoxBerry Plugin 
</p>

**VLX2MQTT** ist ein LoxBerry-Plugin und eine Python-basierte MQTT-Bridge für die **VELUX KLF200 / Homecontrol IO**.

Das Plugin verbindet sich direkt mit der KLF200, liest Positionen und Zustände von Fenstern und Rollläden aus, veröffentlicht diese per MQTT und verarbeitet MQTT-Kommandos zur Steuerung.

---

<a id="inhalt"></a>
<details>
<summary><strong>Inhaltsverzeichnis</strong></summary>

- [Funktionen](#funktionen)
- [Wichtige Design-Entscheidungen](#wichtige-design-entscheidungen)
- [Voraussetzungen](#voraussetzungen)
- [Konfiguration](#konfiguration)
  - [Beispiel](#beispiel)
  - [Wichtige Parameter](#wichtige-parameter)
- [MQTT-Topics](#mqtt-topics)
  - [Status / Diagnose](#status--diagnose)
  - [Node-Topics](#node-topics)
  - [Recovery-Topics](#recovery-topics)
- [Bedeutung der wichtigsten Status-Topics](#bedeutung-der-wichtigsten-status-topics)
  - [`<root_topic>/status`](#root_topicstatus)
  - [`<root_topic>/status_detail`](#root_topicstatus_detail)
  - [`<root_topic>/status_live`](#root_topicstatus_live)
- [Bedeutung der Node-Topics](#bedeutung-der-node-topics)
- [Steuerung per MQTT](#steuerung-per-mqtt)
- [Identifier-Modus: `name` oder `node_id`](#identifier-modus-name-oder-node_id)
- [Regensensor](#regensensor)
- [Recovery / Power-Cycle](#recovery--power-cycle)
  - [Empfehlung](#empfehlung)
  - [Warum gibt es einen präventiven Recovery-Trigger?](#warum-gibt-es-einen-präventiven-recovery-trigger)
    - [Empfohlene Verwendung](#empfohlene-verwendung)
    - [Hintergrund / Quellen](#hintergrund--quellen)
- [Logging](#logging)
- [Dateien und Verzeichnisse](#dateien-und-verzeichnisse)
- [Weboberfläche](#weboberfläche)
- [Template-System / LoxBerry-Einbindung](#template-system--loxberry-einbindung)
- [index.cgi API](#indexcgi-api)
  - [Frontend](#frontend)
  - [AJAX-Endpunkte](#ajax-endpunkte)
    - [Service-Status abfragen](#service-status-abfragen)
    - [Dienst neu starten](#dienst-neu-starten)
    - [Dienst stoppen](#dienst-stoppen)
    - [MQTT-Topic einmalig lesen](#mqtt-topic-einmalig-lesen)
  - [Optional: Secure PIN](#optional-secure-pin)
  - [Unterstützte `ajax`-Werte](#unterstützte-ajax-werte)
- [Bekannte Eigenheiten](#bekannte-eigenheiten)
- [Sinnvolle Tests](#sinnvolle-tests)
- [Deinstallation](#deinstallation)
- [Status des Projekts](#status-des-projekts)
- [Lizenz](#lizenz)
- [Autor](#autor)

</details>

---

## Funktionen

- MQTT-Bridge für **VELUX KLF200 / Homecontrol IO**
- Liest Positionen, Zustände und Bewegungsstatus von Fenstern und Rollläden
- Steuert Fenster und Rollläden per MQTT
- Unterstützt folgende MQTT-Kommandos:
  - `UP` / `OPEN`
  - `DOWN` / `CLOSE`
  - `STOP`
  - numerische Zielpositionen `0..100`
- Veröffentlicht Diagnose- und Statusinformationen per MQTT
- Unterstützt zwei Topic-Identifier-Modi:
  - `name`
  - `node_id`
- Veröffentlicht optional einen Regenstatus für unterstützte Fenster per MQTT
- Optionaler externer **Recovery-/Power-Cycle-Trigger** bei KLF-Verbindungsproblemen
- Optionaler **präventiver Recovery-Trigger** nach konfigurierbarer Laufzeit
- Startup-Snapshot für Position und `moving`
- Aussagekräftiges kompakteres Logging bei `verbose = 0`

[Zurück zum Inhalt](#inhalt)

---

## Wichtige Design-Entscheidungen

### Keine Interpolation in dieser Version

Diese Version arbeitet **bewusst ohne Interpolation** von Bewegungen.

**Grund:**  
Die vom KLF gelieferten Restlaufzeiten (`remaining_time`) sind im aktuellen Zusammenspiel mit `pyvlx` nicht in allen Situationen zuverlässig genug verfügbar, um daraus stabile Zwischenpositionen abzuleiten.

**Vorteile dieser Entscheidung:**

- robusterer Betrieb
- weniger falsche Zwischenwerte
- stabilere `moving`-Logik
- besser nachvollziehbares Verhalten im Fehlerfall

[Zurück zum Inhalt](#inhalt)

---

## Voraussetzungen

- **LoxBerry**
- **VELUX KLF200 / Homecontrol IO**
- MQTT-Broker
- Netzwerkzugriff zwischen LoxBerry und KLF200
- Python 3 mit `pyvlx` und `paho-mqtt`

[Zurück zum Inhalt](#inhalt)

---

## Konfiguration

Die zentrale Konfigurationsdatei liegt typischerweise unter:

```text
/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg
```

### Beispiel

```ini
[vlx2mqtt]
klf_host = VELUX-KLF-DE3B.fritz.box
klf_pw = KLF_WiFi_PASSWORT
mqtt_host = 127.0.0.1
mqtt_port = 1883
mqtt_user = loxberry
mqtt_pw = DEIN_MQTT_PASSWORT
root_topic = vlx2mqtt
initial_delay = 2.5
connect_timeout = 30.0
moving_timeout = 60.0
backoff_max = 30.0
verbose = 0
logfile = /opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log

topic_identifier = name
rain_poll_interval = 300
publish_rain_raw_limit = false

external_recovery_enabled = false
external_recovery_threshold = 4
external_recovery_cooldown = 1800
external_recovery_grace = 120
external_recovery_topic = vlx2mqtt/recovery/powercycle_required
preventive_recovery_hours = 0
```

### Wichtige Parameter

| Parameter | Bedeutung |
|---|---|
| `klf_host` | Hostname oder IP-Adresse der KLF200 |
| `klf_pw` | WiFi-Passwort der KLF200 |
| `mqtt_host` | MQTT-Broker |
| `mqtt_port` | MQTT-Port |
| `mqtt_user` | MQTT-Benutzername |
| `mqtt_pw` | MQTT-Passwort |
| `root_topic` | Oberstes MQTT-Topic |
| `initial_delay` | Verzögerung bis zum initialen Snapshot |
| `connect_timeout` | Timeout für den KLF-Verbindungsaufbau |
| `moving_timeout` | Watchdog-Zeit für Bewegungen |
| `backoff_max` | Maximale Reconnect-Wartezeit |
| `verbose` | `1` = Debug-Logging, `0` = kompakter Log |
| `logfile` | Pfad zur Logdatei |
| `topic_identifier` | MQTT-Identifier pro Node: `name` oder `node_id` |
| `rain_poll_interval` | Polling-Intervall für die Regenabfrage in Sekunden |
| `publish_rain_raw_limit` | veröffentlicht zusätzlich den Rohwert `rain_raw_limit` |
| `external_recovery_enabled` | aktiviert externen Recovery-/Power-Cycle-Trigger |
| `external_recovery_threshold` | Anzahl relevanter Fehler bis Recovery angefordert wird |
| `external_recovery_cooldown` | Mindestabstand zwischen zwei Recovery-Anforderungen |
| `external_recovery_grace` | Wartezeit nach externer Recovery |
| `external_recovery_topic` | MQTT-Topic für den externen Power-Cycle-Trigger |
| `preventive_recovery_hours` | präventiver Recovery-Trigger nach X Stunden (`0` = deaktiviert) |

[Zurück zum Inhalt](#inhalt)

---

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

### Recovery-Topics

```text
<root_topic>/recovery/powercycle_required
<root_topic>/recovery/reason
<root_topic>/recovery/failure_count
<root_topic>/recovery/state
```

[Zurück zum Inhalt](#inhalt)

---

## Bedeutung der wichtigsten Status-Topics

### `<root_topic>/status`
<a id="root_topicstatus"></a>

Ein **einfacher Gesamtstatus** für Logik und Visualisierung.

**Werte:**

- `ok`
- `error`

---

### `<root_topic>/status_detail`
<a id="root_topicstatus_detail"></a>

Ein **stabiler Detailstatus** für Automatisierung, Diagnose und History.

`status_detail` ist **dienstorientiert**:

- wenn der Dienst **nicht** läuft, z. B. `service_starting`, `service_stopped`, `service_lost`
- wenn der Dienst läuft, entspricht er typischerweise dem aktuellen KLF-Status, z. B. `klf_connected`, `klf_connecting`, `klf_connection_refused`, `klf_auth_failed`, `klf_unreachable`

---

### `<root_topic>/status_live`
<a id="root_topicstatus_live"></a>

Ein **roher Live-Status** der KLF-Verbindung.

`status_live` bildet immer direkt den aktuellen KLF-Zustand ab.

[Zurück zum Inhalt](#inhalt)

---

## Bedeutung der Node-Topics

### `<root_topic>/<Identifier>/position`
Rückmeldung der aktuellen Geräteposition.

### `<root_topic>/<Identifier>/set`
Befehlseingang für die Steuerung des Geräts. Unterstützt `UP`, `DOWN`, `STOP`, `OPEN`, `CLOSE` sowie numerische Zielpositionen `0..100`.

### `<root_topic>/<Identifier>/moving`
Vom Skript abgeleiteter Bewegungsstatus.

### `<root_topic>/<Identifier>/rain`
Binärer Regenstatus für unterstützte Fenster (`true` / `false`).

### `<root_topic>/<Identifier>/rain_raw_limit`
Optionaler Rohwert der indirekten Regen-Erkennung über die Öffnungsbegrenzung.

[Zurück zum Inhalt](#inhalt)

---

## Steuerung per MQTT

### Beispiele im `name`-Modus

```text
vlx2mqtt/Rollladen_links/set -> DOWN
vlx2mqtt/Rollladen_links/set -> STOP
vlx2mqtt/Rollladen_links/set -> 65
```

### Beispiele im `node_id`-Modus

```text
vlx2mqtt/2/set -> DOWN
vlx2mqtt/2/set -> STOP
vlx2mqtt/2/set -> 65
```

[Zurück zum Inhalt](#inhalt)

---

## Identifier-Modus: `name` oder `node_id`

Über `topic_identifier` kann festgelegt werden, welcher Identifier im MQTT-Topic verwendet wird:

- `name` → Geräte-/Knotennamen, z. B. `Rollladen_links`
- `node_id` → numerische KLF-Node-ID, z. B. `2`

Wenn von `name` auf `node_id` (oder umgekehrt) umgestellt wird, können **alte retained Topics** im MQTT-Broker sichtbar bleiben.

[Zurück zum Inhalt](#inhalt)

---

## Regensensor

Für unterstützte Fenster wird ein indirekter Regenstatus veröffentlicht:

```text
<root_topic>/<Identifier>/rain
<root_topic>/<Identifier>/rain_raw_limit
```

Der Regenstatus wird **indirekt über die Öffnungsbegrenzung** des Fensters ermittelt und periodisch abgefragt.

### Technischer Hinweis

Je nach verwendeter `pyvlx`-Version bzw. Node-Repräsentation stehen die dafür benötigten Informationen über unterschiedliche APIs zur Verfügung. VLX2MQTT unterstützt dafür beide Varianten:

- `get_limitation_min()`
- `get_limitation()`

### Heuristik

- `raw_limit < 89` → kein Regen erkannt
- `raw_limit >= 89` → Regen erkannt

### Wichtige Hinweise

- Regenstatus wird **nur für Nodes veröffentlicht**, die die nötigen Limitation-Daten bereitstellen.
- Die Veröffentlichung hängt **nicht** vom Gerätenamen ab.
- `rain_raw_limit` ist optional und wird nur publiziert, wenn `publish_rain_raw_limit = true` gesetzt ist.
- `rain` ist ein **Status-Topic**, kein Steuertopic.

[Zurück zum Inhalt](#inhalt)

---

## Recovery / Power-Cycle

Bei wiederholten Fehlerzuständen wie z. B. `klf_connection_refused` kann das Plugin optional einen externen Recovery-/Power-Cycle-Trigger per MQTT veröffentlichen.

### Empfehlung

- **kein Reboot beim normalen Stop** des Dienstes
- externe Recovery nur bei echten Verbindungsproblemen nutzen
- präventive Recovery bewusst und konservativ konfigurieren

### Warum gibt es einen präventiven Recovery-Trigger?

Die KLF200 ist in der Praxis nicht immer dauerhaft stabil, wenn viele oder wiederholte Verbindungsaufbauten stattfinden. Aus diesem Grund unterstützt VLX2MQTT optional einen **präventiven Recovery-Trigger**.

[Zurück zum Inhalt](#inhalt)

---

## Logging

Logdatei:

```text
/opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log
```

### Logging-Modus

- `verbose = 1` → ausführliches Debug-Logging
- `verbose = 0` → reduziertes Logging für den produktiven Betrieb

### Beispiele für kompaktes Logging (`verbose = 0`)

```text
Fenster_links rain: false (raw_limit=0)
Fenster_rechts rain: true (raw_limit=100)
```

[Zurück zum Inhalt](#inhalt)

---

## Dateien und Verzeichnisse

### Typische Pfade unter LoxBerry

```text
/opt/loxberry/bin/plugins/vlx2mqtt/vlx2mqtt.py
/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg
/opt/loxberry/data/plugins/vlx2mqtt/venv
/opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log
/etc/systemd/system/vlx2mqtt.service
/opt/loxberry/webfrontend/htmlauth/plugins/vlx2mqtt/index.cgi
/opt/loxberry/templates/plugins/vlx2mqtt/index.html
/opt/loxberry/templates/plugins/vlx2mqtt/lang/language_de.ini
/opt/loxberry/templates/plugins/vlx2mqtt/lang/language_en.ini
```

[Zurück zum Inhalt](#inhalt)

---

## Weboberfläche

Das Plugin enthält eine LoxBerry-Weboberfläche zur Konfiguration von:

- KLF200-Verbindung
- MQTT-Zugang
- Root-Topic
- Logging
- Topic-Identifier (`name` / `node_id`)
- Regen-Polling (`rain_poll_interval`)
- optionalem `rain_raw_limit`
- Recovery-/Power-Cycle-Einstellungen

Zusätzlich sind Servicefunktionen wie **Restart**, **Stop** und **Log anzeigen** integriert.

[Zurück zum Inhalt](#inhalt)

---

## Template-System / LoxBerry-Einbindung

Die Weboberfläche nutzt das LoxBerry-Template-System mit `HTML::Template`.

Wichtige Hinweise:

- `index.cgi` wird im authentifizierten Plugin-Webfrontend abgelegt.
- Das eigentliche HTML-Template liegt im Template-Verzeichnis des Plugins.
- Die Seite wird über `LoxBerry::Web::lbheader()` und `LoxBerry::Web::lbfooter()` in das LoxBerry-Layout eingebunden.
- Eigene Templates sollten **kein eigenes `<html>`, `<head>` oder `<body>`** erzeugen.
- Sprachdateien liegen typischerweise unter `templates/.../lang/` und werden über `readlanguage()` eingebunden.

[Zurück zum Inhalt](#inhalt)

---

## index.cgi API

Neben dem normalen Frontend stellt `index.cgi` auch einfache AJAX-/JSON-Endpunkte für Statusabfragen und Serviceaktionen bereit.

### Frontend

Normale Weboberfläche:

```text
/admin/plugins/vlx2mqtt/index.cgi
```

### AJAX-Endpunkte

#### Service-Status abfragen

```text
index.cgi?ajax=statusvlx
```

Liefert den aktuellen Dienststatus als JSON zurück, typischerweise mit Feldern wie `error`, `pid`, `state`, `message` und `klf_status`.

#### Dienst neu starten

```text
index.cgi?ajax=restartvlx
```

Startet den Dienst `vlx2mqtt.service` neu.

#### Dienst stoppen

```text
index.cgi?ajax=stopvlx
```

Stoppt den Dienst `vlx2mqtt.service`.

#### MQTT-Topic einmalig lesen

```text
index.cgi?ajax=gettopic&topic=<root_topic>/status
```

Liest einmalig ein MQTT-Topic aus und liefert die Payload als JSON zurück.

### Optional: Secure PIN

Optional kann zusätzlich ein Secure-PIN-Parameter mitgegeben werden:

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

[Zurück zum Inhalt](#inhalt)

---

## Bekannte Eigenheiten

- Beim Start kann kurz ein alter `moving=true`-Zustand aus retained MQTT-Daten sichtbar sein, bevor der Initialstatus ihn korrigiert.
- Beim Umschalten zwischen `topic_identifier = name` und `topic_identifier = node_id` können alte retained Topics im Broker verbleiben.
- KLF-interne Zeitstempel in empfangenen Frames können von der realen Systemzeit abweichen.
- Rain-Polling ist abhängig von der `pyvlx`-/Node-Unterstützung.
- `rain` und `rain_raw_limit` werden nur für unterstützte Fensternodes veröffentlicht.

[Zurück zum Inhalt](#inhalt)

---

## Sinnvolle Tests

1. Plugin starten
2. Prüfen, ob `status = ok` und `status_detail = klf_connected` gesetzt werden
3. Im gewünschten Identifier-Modus testen
4. MQTT-Befehl `DOWN` oder `100` senden
5. MQTT-Befehl `STOP` senden
6. numerische Position anfahren
7. Prüfen, ob Fenster-Regenstatus (`.../rain`) publiziert wird
8. Optional `publish_rain_raw_limit = true` aktivieren und `.../rain_raw_limit` beobachten
9. Dienst sauber stoppen und prüfen, dass **kein KLF-Reboot** ausgelöst wird
10. Optional Recovery-Topic mit externer Steckdose / Loxone testen

[Zurück zum Inhalt](#inhalt)

---

## Deinstallation

Beim Entfernen des Plugins räumt das Uninstall-Skript insbesondere den extern angelegten `systemd`-Dienst wieder auf.

[Zurück zum Inhalt](#inhalt)

---

## Status des Projekts

Das Plugin ist bewusst auf **robusten, nachvollziehbaren Betrieb** ausgelegt. Schwerpunkt ist eine stabile MQTT-Anbindung der KLF200 unter LoxBerry mit klarer Status- und Recovery-Logik.

[Zurück zum Inhalt](#inhalt)

---

## Lizenz

MIT License

[Zurück zum Inhalt](#inhalt)

---

## Autor

**Siggi**  
GitHub: [5iggi](https://github.com/5iggi)

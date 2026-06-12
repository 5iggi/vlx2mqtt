# VLX2MQTT KLF200 Bridge LoxBerry Plugin <img src="icons/icon.svg" width="120">

**VLX2MQTT** ist ein LoxBerry-Plugin und eine Python-basierte MQTT-Bridge für die **VELUX KLF200 / Homecontrol IO**.

Das Plugin verbindet sich direkt mit der KLF200, liest Positionen und Zustände von Fenstern und Rollläden aus, veröffentlicht diese per MQTT und verarbeitet MQTT-Kommandos zur Steuerung.

---

<a id="inhalt"></a>
<details>
<summary><strong>Inhaltsverzeichnis</strong></summary>

- [Funktionen](#funktionen)
- [Wichtige Design-Entscheidungen](#wichtige-design-entscheidungen)
  - [Keine Interpolation in dieser Version](#keine-interpolation-in-dieser-version)
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
  - [Kurz gesagt](#kurz-gesagt)
- [Bedeutung der Node-Topics](#bedeutung-der-node-topics)
- [Steuerung per MQTT](#steuerung-per-mqtt)
- [Recovery / Power-Cycle](#recovery--power-cycle)
  - [Empfehlung](#empfehlung)
  - [Warum gibt es einen präventiven Recovery-Trigger?](#warum-gibt-es-einen-präventiven-recovery-trigger)
    - [Empfohlene Verwendung](#empfohlene-verwendung)
    - [Hintergrund / Quellen](#hintergrund--quellen)
- [Logging](#logging)
- [Dateien und Verzeichnisse](#dateien-und-verzeichnisse)
- [Weboberfläche](#weboberfläche)
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
- Optionaler externer **Recovery-/Power-Cycle-Trigger** bei KLF-Verbindungsproblemen
- Optionaler **präventiver Recovery-Trigger** nach konfigurierbarer Laufzeit
- Betrieb als `systemd`-Dienst unter LoxBerry

[Zurück zum Inhalt](#inhalt)

---

## Wichtige Design-Entscheidungen

### Keine Interpolation in dieser Version
Diese Version arbeitet **bewusst ohne Interpolation** von Bewegungen.

Grund:  
Die vom KLF gelieferten Restlaufzeiten (`remaining_time`) sind im aktuellen Zusammenspiel mit `pyvlx` nicht in allen Situationen zuverlässig genug verfügbar, um daraus stabile Zwischenpositionen abzuleiten.

Vorteile dieser Entscheidung:

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

Während der Plugin-Installation werden automatisch:

- die Plugin-Dateien in die LoxBerry-Verzeichnisse kopiert
- die Konfiguration unter `config/plugins/vlx2mqtt/` angelegt
- eine Python-Umgebung unter `data/plugins/vlx2mqtt/venv` erstellt
- die Python-Abhängigkeiten installiert
- der `systemd`-Dienst `vlx2mqtt.service` erzeugt und aktiviert

[Zurück zum Inhalt](#inhalt)

---

## Konfiguration

Die zentrale Konfigurationsdatei liegt unter:

```text
/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg
```

### Beispiel

```ini
[vlx2mqtt]
klf_host = VELUX-KLF-DE3B.fritz.box
klf_pw = DEIN_KLF_PASSWORT
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

external_recovery_enabled = true
external_recovery_threshold = 4
external_recovery_cooldown = 1800
external_recovery_grace = 120
external_recovery_topic = vlx2mqtt/recovery/powercycle_required
preventive_recovery_hours = 24
```

### Wichtige Parameter

| Parameter | Bedeutung |
|---|---|
| `klf_host` | Hostname oder IP-Adresse der KLF200 |
| `klf_pw` | WiFi-Passwort der KLF200 |
| `mqtt_host` | MQTT-Broker |
| `root_topic` | Oberstes MQTT-Topic |
| `moving_timeout` | Watchdog-Zeit für Bewegungen |
| `backoff_max` | Maximale Reconnect-Wartezeit |
| `verbose` | `1` = Debug-Logging, `0` = kompakter Log |
| `external_recovery_enabled` | aktiviert externen Recovery-/Power-Cycle-Trigger |
| `external_recovery_threshold` | Anzahl aufeinanderfolgender `klf_connection_refused`, bevor Recovery angefordert wird |
| `external_recovery_cooldown` | Mindestabstand zwischen zwei Recovery-Anforderungen |
| `external_recovery_grace` | Wartezeit nach externer Recovery |
| `external_recovery_topic` | MQTT-Topic für den externen Power-Cycle-Trigger |
| `preventive_recovery_hours` | präventiver Recovery-Trigger nach X Stunden; veröffentlicht eine vorsorgliche externe Reboot-/Power-Cycle-Anforderung für die KLF200, um Verbindungsproblemen vorzubeugen (`0` = deaktiviert) |

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
<root_topic>/<NodeName>/position
<root_topic>/<NodeName>/moving
<root_topic>/<NodeName>/set
```

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

Werte:

- `ok`
- `error`

Typische Verwendung:

- Ampelstatus in Loxone
- einfache Sammelfehler-Erkennung

---

### `<root_topic>/status_detail`
<a id="root_topicstatus_detail"></a>
Ein **stabiler Detailstatus** für Automatisierung, Diagnose und History.

`status_detail` ist **dienstorientiert**:

- Wenn der Dienst **nicht** läuft, liefert er z. B.:
  - `service_starting`
  - `service_stopped`
  - `service_lost`
- Wenn der Dienst läuft, entspricht er dem aktuellen KLF-Status, z. B.:
  - `klf_connected`
  - `klf_connecting`
  - `klf_connection_refused`
  - `klf_auth_failed`
  - `klf_unreachable`

Typische Verwendung:

- klare Auswertung in Loxone / Node-RED
- Historie „war der Dienst aus oder war die KLF nicht erreichbar?"
- Fehlerursachen unterscheiden

---

### `<root_topic>/status_live`
<a id="root_topicstatus_live"></a>
Ein **roher Live-Status** der KLF-Verbindung.

`status_live` bildet immer direkt den aktuellen KLF-Zustand ab, also z. B.:

- `starting`
- `klf_connecting`
- `klf_connected`
- `klf_connection_refused`
- `stopped`

Im Gegensatz zu `status_detail` ist `status_live` **nicht service-abstrahiert**, sondern zeigt den **unmittelbaren aktuellen KLF-Livezustand**.

Typische Verwendung:

- Live-Diagnose
- Technisches Monitoring
- Anzeige aktueller Übergangszustände

---

### Kurz gesagt

- **`status`** = grob: `ok` / `error`
- **`status_detail`** = stabiler, dienstbewusster Detailstatus
- **`status_live`** = aktueller roher Live-Status der KLF-Verbindung

Beispiel:

```text
service_status = running
status = error
status_detail = klf_connection_refused
status_live = klf_connection_refused
```

oder beim Start:

```text
service_status = starting
status = error
status_detail = service_starting
status_live = starting
```

[Zurück zum Inhalt](#inhalt)

---

## Bedeutung der Node-Topics

### `<root_topic>/<NodeName>/position`
Rückmeldung der aktuellen Geräteposition.  
Der Wert wird aus den von der KLF / `pyvlx` gelieferten Zustandsdaten übernommen.

### `<root_topic>/<NodeName>/set`
Befehlseingang für die Steuerung des Geräts.  
Unterstützt `UP`, `DOWN`, `STOP`, `OPEN`, `CLOSE` sowie numerische Zielpositionen `0..100`.

### `<root_topic>/<NodeName>/moving`
Vom Skript abgeleiteter Bewegungsstatus.  
Der Wert wird aus KLF-Rückmeldungen, Run-Status, Ziel-/Positionswerten und interner Bewegungslogik berechnet.

[Zurück zum Inhalt](#inhalt)

---

## Steuerung per MQTT

Beispiele:

```text
vlx2mqtt/Rollladen_links/set -> DOWN
vlx2mqtt/Rollladen_links/set -> STOP
vlx2mqtt/Rollladen_links/set -> 65
```

Unterstützte Werte:

- `UP`
- `OPEN`
- `DOWN`
- `CLOSE`
- `STOP`
- numerische Positionen `0..100`

[Zurück zum Inhalt](#inhalt)

---

## Recovery / Power-Cycle

Bei wiederholtem Fehlerzustand

```text
klf_connection_refused
```

kann das Plugin optional einen externen Recovery-/Power-Cycle-Trigger per MQTT veröffentlichen.

Beispiel:

```text
vlx2mqtt/recovery/powercycle_required = true
vlx2mqtt/recovery/reason = klf_connection_refused
```

Damit kann z. B. in **Loxone** eine schaltbare Steckdose genutzt werden, um die KLF200 stromlos zu machen und neu zu starten.

### Empfehlung

- **kein Reboot beim normalen Stop** des Dienstes
- externe Recovery nur bei echten Verbindungsproblemen nutzen
- präventive Recovery bewusst und konservativ konfigurieren

---

## Warum gibt es einen präventiven Recovery-Trigger?

Die KLF200 ist in der Praxis nicht immer dauerhaft stabil, wenn viele oder wiederholte Verbindungsaufbauten stattfinden.  
Aus Community-Berichten rund um Home Assistant und `pyvlx` ergibt sich immer wieder folgendes Muster:

- die KLF200 nimmt nach einer gewissen Laufzeit oder nach mehreren TCP-/SSL-Verbindungen keine neuen Verbindungen mehr sauber an
- SSL-Handshakes können hängen bleiben
- es treten `Connect call failed` oder `Connection refused` auf
- in manchen Fällen hilft danach nur noch ein **Power-Cycle** oder ein gezielter **Gateway-Reboot**

Aus diesem Grund unterstützt VLX2MQTT optional einen **präventiven Recovery-Trigger**.

Dieser Mechanismus soll die KLF200 **vorsorglich stabilisieren**, bevor sie in einen Zustand gelangt, in dem keine Verbindung mehr aufgebaut werden kann oder nur noch ein Neustart hilft.

Wichtig:

- VLX2MQTT rebootet die KLF200 **nicht direkt selbst**
- das Plugin veröffentlicht stattdessen einen **externen MQTT-Trigger**
- dieser Trigger kann z. B. von **Loxone**, **Node-RED** oder einer **schaltbaren Steckdose** ausgewertet werden

### Empfohlene Verwendung

- Für den normalen Betrieb vorzugsweise **reaktive Recovery** bei echten Fehlern verwenden
- Präventive Recovery nur bewusst aktivieren
- Präventive Trigger eher konservativ wählen (z. B. 24 h oder mehr)

### Hintergrund / Quellen

Die Funktion basiert auf regelmäßig berichteten KLF200-Problemen in der Praxis, unter anderem:

- KLF200 nimmt nach mehreren TCP/IP-Verbindungen keine neuen Verbindungen mehr an
- Workaround über `velux.reboot_gateway`
- Power-Cycle als zuverlässigste Wiederherstellung
- `pyvlx`-Berichte über festlaufende Verbindungen bei längerer Laufzeit

Beispielquellen:

- Home Assistant Community: Velux KLF 200 integration  
  https://community.home-assistant.io/t/velux-klf-200-integration/677087
- Home Assistant Community: Restart velux integration?  
  https://community.home-assistant.io/t/restart-velux-integration/531585
- pyvlx GitHub Issue: Keeping connection open freezes KLF  
  https://github.com/Julius2342/pyvlx/issues/30
- Home Assistant Velux documentation  
  https://www.home-assistant.io/integrations/velux/

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
```

[Zurück zum Inhalt](#inhalt)

---

## Weboberfläche

Das Plugin enthält eine LoxBerry-Weboberfläche zur Konfiguration von:

- KLF200-Verbindung
- MQTT-Zugang
- Root-Topic
- Logging
- Recovery-/Power-Cycle-Einstellungen

Zusätzlich sind Servicefunktionen wie

- **Restart**
- **Stop**
- **Log anzeigen**

integriert.

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

Liefert den aktuellen Dienststatus als JSON, typischerweise mit:

- `error`
- `pid`
- `state`
- `message`
- `klf_status`

Beispiel:

```json
{
  "error": 0,
  "pid": "12345",
  "state": "active",
  "message": "OK",
  "klf_status": "klf_connected"
}
```

---

#### Dienst neu starten

```text
index.cgi?ajax=restartvlx
```

Startet den Dienst `vlx2mqtt.service` neu und liefert den Status der Aktion als JSON zurück.

---

#### Dienst stoppen

```text
index.cgi?ajax=stopvlx
```

Stoppt den Dienst `vlx2mqtt.service` und liefert den Status der Aktion als JSON zurück.

---

#### MQTT-Topic einmalig lesen

```text
index.cgi?ajax=gettopic&topic=<root_topic>/status
```

Liest einmalig ein MQTT-Topic aus und liefert dessen Payload als JSON zurück.

Beispiel:

```json
{
  "error": 0,
  "topic": "vlx2mqtt/status",
  "payload": "ok",
  "message": "ok"
}
```

---

### Optional: Secure PIN

Optional kann zusätzlich ein Secure-PIN-Parameter mitgegeben werden:

```text
index.cgi?ajax=statusvlx&secpin=1234
```

---

### Unterstützte `ajax`-Werte

```text
statusvlx
restartvlx
stopvlx
gettopic
```

Unbekannte Aktionen werden mit einer JSON-Fehlermeldung quittiert.

[Zurück zum Inhalt](#inhalt)

---

## Bekannte Eigenheiten

- Beim Start kann kurz ein alter `moving=true`-Zustand aus retained MQTT-Daten sichtbar sein, bevor der Initialstatus ihn korrigiert.
- Während der Node-Erkennung kann `NodeUpdater: Received state frame for unknown node_id ...` kurz auftauchen. Das ist in der Regel unkritisch.
- Heartbeat-/Statusabfragen können Target-Werte im Log aktualisieren, ohne dass ein echter Fahrbefehl ausgelöst wurde.

[Zurück zum Inhalt](#inhalt)

---

## Sinnvolle Tests

1. Plugin starten
2. Prüfen, ob `status = ok` und `status_detail = klf_connected` gesetzt werden
3. MQTT-Befehl `DOWN` senden
4. MQTT-Befehl `STOP` senden
5. numerische Position, z. B. `65`, anfahren
6. Dienst sauber stoppen und prüfen, dass **kein KLF-Reboot** ausgelöst wird
7. optional Recovery-Topic mit externer Steckdose / Loxone testen

[Zurück zum Inhalt](#inhalt)

---

## Deinstallation

Beim Entfernen des Plugins räumt das Uninstall-Skript insbesondere den extern angelegten `systemd`-Dienst wieder auf.

Die pluginbezogenen Standardverzeichnisse entfernt LoxBerry automatisch.

[Zurück zum Inhalt](#inhalt)

---

## Status des Projekts

Das Plugin ist bewusst auf **robusten, nachvollziehbaren Betrieb** ausgelegt.

Schwerpunkt ist eine stabile MQTT-Anbindung der KLF200 unter LoxBerry mit klarer Status- und Recovery-Logik.

[Zurück zum Inhalt](#inhalt)

---

## Lizenz

- MIT
- GPLv3
- proprietär / privat

[Zurück zum Inhalt](#inhalt)

---

## Autor

**Siggi**  
GitHub: [5iggi](https://github.com/5iggi)

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

# MQTT Topics

Diese Datei beschreibt die wichtigsten MQTT-Topics von VLX2MQTT.

## Platzhalter

```text
<root_topic>   Standard: vlx2mqtt
<node>         Gerätename oder node_id, abhängig von topic_identifier
```

Beispiele:

```text
vlx2mqtt/Fenster_links/position
vlx2mqtt/0/position
```

## Status- und Diagnose-Topics

```text
<root_topic>/status
<root_topic>/status_code
<root_topic>/status_detail
<root_topic>/status_detail_code
<root_topic>/status_live
<root_topic>/status_live_code
<root_topic>/service_status
<root_topic>/service_status_code
<root_topic>/service_detail
<root_topic>/error_text
<root_topic>/health
```

## Numerische Statuscodes

Die `*_code` Topics liefern numerische Werte für Loxone und andere Visualisierungen.  
Die zugehörigen Text-Topics bleiben zusätzlich erhalten.

### `status_code`

Gehört zu:

```text
<root_topic>/status
<root_topic>/status_code
```

```text
ok=1
error=0
```

### `status_detail_code`

Gehört zu:

```text
<root_topic>/status_detail
<root_topic>/status_detail_code
```

`status_detail` ist der stabile Detailstatus. Wenn der Dienst läuft, entspricht der Wert normalerweise dem KLF-Status. Wenn der Dienst nicht läuft oder startet, kann der Wert dienstbezogen sein.

```text
klf_connected=1
klf_connecting=2
klf_disconnected=3
klf_unreachable=4
klf_connection_refused=5
klf_auth_failed=6
klf_error=7
starting=8
unknown=99

service_running=1
service_starting=2
service_stopped=0
service_lost=0
service_error=0
```

### `status_live_code`

Gehört zu:

```text
<root_topic>/status_live
<root_topic>/status_live_code
```

`status_live` ist der rohe Live-Status der KLF-Verbindung.

```text
klf_connected=1
klf_connecting=2
klf_disconnected=3
klf_unreachable=4
klf_connection_refused=5
klf_auth_failed=6
klf_error=7
starting=8
unknown=99
```

### `service_status_code`

Gehört zu:

```text
<root_topic>/service_status
<root_topic>/service_status_code
```

```text
running=1
starting=2
stopped=0
lost=0
error=0
unknown=99
```

## Node-Topics

```text
<root_topic>/<node>/position
<root_topic>/<node>/moving
<root_topic>/<node>/set
<root_topic>/<node>/rain
<root_topic>/<node>/rain_raw_limit
```

### `position`

Aktuelle Position des Geräts in Prozent.

```text
0..100
```

### `moving`

Abgeleiteter Bewegungsstatus.

```text
true
false
```

### `rain`

Indirekter Regenstatus für unterstützte Fenster.

```text
true
false
```

### `rain_raw_limit`

Optionaler Rohwert der indirekten Regen-Erkennung. Wird nur veröffentlicht, wenn `publish_rain_raw_limit = true` gesetzt ist.

## Steuerung per MQTT

```text
<root_topic>/<node>/set = UP
<root_topic>/<node>/set = DOWN
<root_topic>/<node>/set = OPEN
<root_topic>/<node>/set = CLOSE
<root_topic>/<node>/set = STOP
<root_topic>/<node>/set = 0..100
```

Beispiele:

```text
vlx2mqtt/Fenster_links/set = DOWN
vlx2mqtt/Fenster_links/set = STOP
vlx2mqtt/Fenster_links/set = 65
```


## Rain-Polling und Log-Cleanup

Für die indirekte Regen-/Limitation-Abfrage stehen zusätzlich diese Konfigurationswerte zur Verfügung:

```ini
rain_read_timeout = 15.0
rain_skip_during_recovery = true
```

`rain_read_timeout` begrenzt eine einzelne KLF-/pyvlx-Limitation-Abfrage. Bekannte KLF-/Netzwerkfehler werden bei `verbose = 0` kompakt geloggt; vollständige Stacktraces bleiben bei `verbose = 1` verfügbar.

Wenn `rain_skip_during_recovery = true` gesetzt ist, wird Rain-Polling während `recovery/state=requested` oder `recovery/state=waiting` übersprungen.

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

### `recovery/powercycle_required_code`

Gehört zu:

```text
<root_topic>/recovery/powercycle_required
<root_topic>/recovery/powercycle_required_code
```

```text
power-cycle required=0
power-cycle required=1
```

### `recovery/state_code`

Gehört zu:

```text
<root_topic>/recovery/state
<root_topic>/recovery/state_code
```

```text
idle=0
requested=1
waiting=2
```

### `recovery/reason_code`

Gehört zu:

```text
<root_topic>/recovery/reason
<root_topic>/recovery/reason_code
```

```text
none=0
klf_connected=1
klf_connecting=2
klf_disconnected=3
klf_unreachable=4
klf_connection_refused=5
klf_auth_failed=6
klf_error=7
preventive_recovery=10
preventive_interval=10
unknown=99
```

`preventive_interval` ist der aktuell publizierte Recovery-Grund, wenn die präventive Recovery durch `preventive_recovery_hours` ausgelöst wurde.  
`preventive_recovery` bleibt als kompatibler Alias mit demselben Code dokumentiert.

### Runtime-Recovery-Gewichtung

Im laufenden Betrieb werden Recovery-relevante Fehler gewichtet gezählt:

```ini
runtime_recovery_command_weight = 2
runtime_recovery_rain_weight = 1
```

Standardmäßig zählt ein fehlgeschlagener Fahr-/Positionsbefehl `+2`, eine fehlgeschlagene Regen-/Limitation-Abfrage nach Retry `+1`.

### `recovery/state = waiting`

`waiting` bedeutet: Der Recovery-Schwellwert wurde erreicht, aber `external_recovery_cooldown` ist noch aktiv. Währenddessen bleibt `powercycle_required=false`. Nach Ablauf des Cooldowns wird automatisch `powercycle_required=true` gesetzt, wenn die KLF weiterhin nicht verbunden ist.

## Health JSON

`<root_topic>/health` enthält eine JSON-Zusammenfassung mit Status, Servicezustand, KLF-Zustand, Recovery-Informationen und Zählern.

Beispiel:

```json
{
  "status": "ok",
  "status_code": 1,
  "status_detail": "klf_connected",
  "status_detail_code": 1,
  "status_live": "klf_connected",
  "status_live_code": 1,
  "service_state": "running",
  "service_status_code": 1,
  "recovery_requested": false,
  "recovery_waiting": false,
  "recovery_waiting_until": null,
  "recovery_reason": null,
  "recovery_reason_code": 0,
  "failure_count": 0
}
```

---

<p align="center">
  <a href="README.md">Zurück zum Inhalt</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

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

# Troubleshooting

## Dienststatus prüfen

```bash
sudo systemctl status vlx2mqtt.service
```

## Dienst neu starten

```bash
sudo systemctl restart vlx2mqtt.service
```

## Log anzeigen

```bash
tail -f /opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log
```

## MQTT prüfen

```bash
mosquitto_sub -v -t 'vlx2mqtt/#'
```

Mit Zugangsdaten:

```bash
mosquitto_sub -v -t 'vlx2mqtt/#' -u loxberry -P 'MQTT_PASSWORT'
```

## Erwartete Grundtopics

```text
vlx2mqtt/status
vlx2mqtt/status_code
vlx2mqtt/status_detail
vlx2mqtt/status_detail_code
vlx2mqtt/status_live
vlx2mqtt/status_live_code
vlx2mqtt/service_status
vlx2mqtt/service_status_code
vlx2mqtt/health
```

## Loxone ZIP lässt sich nicht öffnen

- Aktuelle `index.cgi` installiert?
- Browser-Cache geleert?
- Einzel-Downloads getestet?

Workaround:

```text
VIU XML einzeln herunterladen
VO XML einzeln herunterladen
README einzeln herunterladen
```

## Keine Positionsupdates

VLX2MQTT arbeitet bewusst eventbasiert. Wenn keine Positionsupdates kommen:

1. KLF-Verbindung prüfen.
2. MQTT prüfen.
3. Log auf KLF-/pyvlx-Fehler prüfen.
4. Event-Monitor-Warnungen prüfen.
5. Gerät real bewegen und MQTT-Ausgabe beobachten.

## Alte MQTT-Topics sichtbar

Beim Wechsel von `topic_identifier = name` auf `node_id` oder umgekehrt können alte retained Topics im Broker verbleiben.

## Recovery löst nicht aus

Prüfen:

```ini
external_recovery_enabled = true
external_recovery_threshold = 4
external_recovery_topic = vlx2mqtt/recovery/powercycle_required
```

Relevante Fehler:

```text
klf_connection_refused
klf_disconnected
klf_unreachable
```

---

<p align="center">
  <a href="README.md">Zurück zum Inhalt</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

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

# Loxone Config Export

VLX2MQTT kann direkt aus der Weboberfläche Loxone-Config-Vorlagen erzeugen.

## Export-Dateien

```text
VIU_VLX2MQTT.xml
VO_VLX2MQTT.xml
README_Loxone_Export.txt
VLX2MQTT_Loxone_Templates.zip
```

## `VIU_VLX2MQTT.xml`

Virtuelle UDP-Eingänge für Loxone Config.

Enthält typischerweise:

```text
Position
Moving
Rain
status_code
status_detail_code
status_live_code
service_status_code
recovery/state_code
recovery/reason_code
```

## `VO_VLX2MQTT.xml`

Virtuelle Ausgänge für Loxone Config.

Enthält pro erkanntem Node Steuerbefehle wie:

```text
UP
DOWN
STOP
SET 0..100
```

## Import in Loxone Config

1. VLX2MQTT-Weboberfläche öffnen.
2. Bereich **Loxone Config Export** öffnen.
3. `VirtualInUdp XML` herunterladen.
4. In Loxone Config als virtuelle UDP-Eingänge importieren.
5. `VirtualOut XML` herunterladen.
6. In Loxone Config als virtuelle Ausgänge importieren.
7. Optional README herunterladen und prüfen.

## Empfohlene Status-Topics für Loxone

```text
vlx2mqtt/status_code
vlx2mqtt/status_detail_code
vlx2mqtt/status_live_code
vlx2mqtt/service_status_code
vlx2mqtt/recovery/state_code
vlx2mqtt/recovery/reason_code
```

Beispiel:

```text
vlx2mqtt/status_live      = klf_connected
vlx2mqtt/status_live_code = 1
```

## Statuscode-Übersicht

```text
ok=1
error=0

klf_connected=1
klf_connecting=2
klf_disconnected=3
klf_unreachable=4
klf_connection_refused=5
klf_auth_failed=6
klf_error=7
starting=8
unknown=99

running=1
starting=2
stopped=0
lost=0
error=0

idle=0
requested=1
waiting=2
```

## Textwerte und Statuscodes

Für neue Loxone-Integrationen werden die numerischen `*_code` Topics empfohlen. Textwerte wie `klf_connected` bleiben zusätzlich erhalten und können weiterhin für Diagnose oder eigene Logik verwendet werden.

## UDP-Ports

```text
Virtual UDP Inputs: 11883
Virtual Outputs:    11884
```

## Hinweise

- Wenn `mqtt_host = 127.0.0.1` oder `localhost` gesetzt ist, verwendet der Export die LoxBerry-IP als Hostadresse.
- Wird `topic_identifier` geändert, können alte retained Topics im Broker sichtbar bleiben.
- Nach Änderungen im Plugin sollte der Loxone-Export neu erzeugt und erneut importiert werden.

---

<p align="center">
  <a href="README.md">Zurück zum Inhalt</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

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

## Verwendung

1. VLX2MQTT-Weboberfläche öffnen.
2. Bereich **Loxone Config Export** öffnen.
3. `VIU_VLX2MQTT.xml` für virtuelle UDP-Eingänge herunterladen und in Loxone Config importieren.
4. `VO_VLX2MQTT.xml` für virtuelle Ausgänge herunterladen und in Loxone Config importieren.
5. Optional `README_Loxone_Export.txt` oder das ZIP herunterladen.

## Empfohlene Topics für Loxone

Für Loxone-Integrationen werden die numerischen `*_code` Topics empfohlen. Sie liefern stabile Zahlenwerte und eignen sich besser für Logik und Statusbausteine als reine Text-/Boolean-Werte.

```text
<root_topic>/status_code
<root_topic>/status_detail_code
<root_topic>/status_live_code
<root_topic>/service_status_code
<root_topic>/recovery/powercycle_required_code
<root_topic>/recovery/state_code
<root_topic>/recovery/reason_code
<root_topic>/<node>/rain_code
```

## Power-Cycle Anforderung

Für die externe Steckdose wird empfohlen:

```text
<root_topic>/recovery/powercycle_required_code
```

```text
0 = kein Power-Cycle erforderlich
1 = Power-Cycle erforderlich
```

Das bestehende Text-/Boolean-Topic bleibt zusätzlich verfügbar:

```text
<root_topic>/recovery/powercycle_required = true / false
```

## Regenstatus

Für Regenlogik in Loxone wird empfohlen:

```text
<root_topic>/<node>/rain_code
```

```text
0 = kein Regen
1 = Regen erkannt
```

Das bestehende Text-/Boolean-Topic bleibt zusätzlich verfügbar:

```text
<root_topic>/<node>/rain = true / false
```

## Hinweis

Die Boolean-Konvertierung im LoxBerry MQTT Gateway kann weiterhin verwendet werden. Für neue Loxone-Logiken sind die numerischen `*_code` Topics jedoch robuster und eindeutiger.

---

<p align="center">
  <a href="README.md">Zurück zum Inhalt</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

<p align="center">
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo" width="100">
</p>

<h1 align="center">VLX2MQTT</h1>

<p align="center">
  <strong>LoxBerry · MQTT · VELUX KLF200 · Loxone Config Export</strong>
</p>

<p align="center">
  <img alt="English" src="https://img.shields.io/badge/Language-English-66AA00?style=flat-square">
  <img alt="LoxBerry" src="https://img.shields.io/badge/LoxBerry-Plugin-66AA00?style=flat-square">
  <img alt="MQTT" src="https://img.shields.io/badge/MQTT-Bridge-blue?style=flat-square">
  <img alt="Loxone" src="https://img.shields.io/badge/Loxone-Export-orange?style=flat-square">
</p>

# Loxone Config Export

VLX2MQTT can generate Loxone Config templates directly from the web interface.

## Export files

```text
VIU_VLX2MQTT.xml
VO_VLX2MQTT.xml
README_Loxone_Export.txt
VLX2MQTT_Loxone_Templates.zip
```

## Usage

1. Open the VLX2MQTT web interface.
2. Open **Loxone Config Export**.
3. Download `VIU_VLX2MQTT.xml` for virtual UDP inputs and import it into Loxone Config.
4. Download `VO_VLX2MQTT.xml` for virtual outputs and import it into Loxone Config.
5. Optionally download `README_Loxone_Export.txt` or the ZIP file.

## Recommended topics for Loxone

For Loxone integrations, the numeric `*_code` topics are recommended. They provide stable numeric values and are better suited for logic and status blocks than text or boolean values.

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

## Power-cycle request

For the external power plug, this topic is recommended:

```text
<root_topic>/recovery/powercycle_required_code
```

```text
0 = no power-cycle required
1 = power-cycle required
```

The existing text / boolean topic remains available as well:

```text
<root_topic>/recovery/powercycle_required = true / false
```

## Rain state

For rain logic in Loxone, this topic is recommended:

```text
<root_topic>/<node>/rain_code
```

```text
0 = no rain
1 = rain detected
```

The existing text / boolean topic remains available as well:

```text
<root_topic>/<node>/rain = true / false
```

## Note

Boolean conversion in the LoxBerry MQTT Gateway can still be used. For new Loxone logic, the numeric `*_code` topics are more robust and explicit.

---

<p align="center">
  <a href="README.md">Back to contents</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

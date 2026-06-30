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

## `VIU_VLX2MQTT.xml`

Virtual UDP inputs for Loxone Config.

Typically contains:

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

Virtual outputs for Loxone Config.

Contains control commands per detected node, for example:

```text
UP
DOWN
STOP
SET 0..100
```

## Import into Loxone Config

1. Open the VLX2MQTT web interface.
2. Open the **Loxone Config Export** section.
3. Download `VirtualInUdp XML`.
4. Import it into Loxone Config as virtual UDP inputs.
5. Download `VirtualOut XML`.
6. Import it into Loxone Config as virtual outputs.
7. Optionally download and review the README.

## Recommended status topics for Loxone

```text
vlx2mqtt/status_code
vlx2mqtt/status_detail_code
vlx2mqtt/status_live_code
vlx2mqtt/service_status_code
vlx2mqtt/recovery/state_code
vlx2mqtt/recovery/reason_code
```

Example:

```text
vlx2mqtt/status_live      = klf_connected
vlx2mqtt/status_live_code = 1
```

## Status-code overview

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

## Text values and status codes

For new Loxone integrations, the numeric `*_code` topics are recommended. Text values such as `klf_connected` are still published and can still be used for diagnostics or custom logic.

## UDP ports

```text
Virtual UDP Inputs: 11883
Virtual Outputs:    11884
```

## Notes

- If `mqtt_host = 127.0.0.1` or `localhost` is set, the export uses the LoxBerry IP as host address.
- If `topic_identifier` is changed, old retained topics may remain visible in the broker.
- After plugin changes, regenerate and re-import the Loxone export.

---

<p align="center">
  <a href="README.md">Back to contents</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

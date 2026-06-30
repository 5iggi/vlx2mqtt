<p align="center">
  <img src="icons/icon.svg" alt="VLX2MQTT logo" width="120">
</p>

<h1 align="center">VLX2MQTT</h1>

<p align="center">
  <strong>MQTT bridge for VELUX KLF200 / Homecontrol IO running as a LoxBerry plugin</strong>
</p>

<p align="center">
  <img alt="LoxBerry" src="https://img.shields.io/badge/LoxBerry-Plugin-66AA00?style=flat-square">
  <img alt="MQTT" src="https://img.shields.io/badge/MQTT-Bridge-blue?style=flat-square">
  <img alt="VELUX KLF200" src="https://img.shields.io/badge/VELUX-KLF200-red?style=flat-square">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.x-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square">
</p>

VLX2MQTT connects a LoxBerry system directly to a VELUX KLF200 / Homecontrol IO gateway, publishes device states via MQTT and accepts MQTT commands for windows, shutters and blinds.

## Documentation

- [Documentation hub](docs/README.md)
- [Deutsch](docs/de/README.md)
- [English](docs/en/README.md)

## Key features

- MQTT bridge for **VELUX KLF200 / Homecontrol IO**
- Runs as a **LoxBerry plugin** and `systemd` service
- Publishes positions, movement states and diagnostics via MQTT
- Controls devices with `UP`, `DOWN`, `OPEN`, `CLOSE`, `STOP` and numeric target positions `0..100`
- Supports topic identifiers by device `name` or numeric `node_id`
- Optional indirect rain status for supported windows
- Optional external recovery / power-cycle trigger for unstable KLF connections
- Numeric `*_code` status topics for Loxone and other visualization systems
- Loxone Config export for `VIU_VLX2MQTT.xml` and `VO_VLX2MQTT.xml`

## Quick MQTT example

```text
vlx2mqtt/Fenster_links/position
vlx2mqtt/Fenster_links/moving
vlx2mqtt/Fenster_links/set
```

```text
vlx2mqtt/Fenster_links/set = DOWN
vlx2mqtt/Fenster_links/set = STOP
vlx2mqtt/Fenster_links/set = 65
```

## Quick Loxone overview

The web frontend can export Loxone Config templates:

```text
VIU_VLX2MQTT.xml
VO_VLX2MQTT.xml
README_Loxone_Export.txt
VLX2MQTT_Loxone_Templates.zip
```

For Loxone visualization, prefer the numeric `*_code` topics:

```text
vlx2mqtt/status_code
vlx2mqtt/status_detail_code
vlx2mqtt/status_live_code
vlx2mqtt/service_status_code
vlx2mqtt/recovery/state_code
vlx2mqtt/recovery/reason_code
```

## License

MIT License

---

<p align="center">
  <img src="icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  MQTT · LoxBerry · VELUX KLF200
</p>

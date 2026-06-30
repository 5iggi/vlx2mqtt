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

# Troubleshooting

## Check service status

```bash
sudo systemctl status vlx2mqtt.service
```

## Restart service

```bash
sudo systemctl restart vlx2mqtt.service
```

## Show log

```bash
tail -f /opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log
```

## Check MQTT

```bash
mosquitto_sub -v -t 'vlx2mqtt/#'
```

With credentials:

```bash
mosquitto_sub -v -t 'vlx2mqtt/#' -u loxberry -P 'MQTT_PASSWORD'
```

## Expected basic topics

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

## Loxone ZIP cannot be opened

- Is the current `index.cgi` installed?
- Was the browser cache cleared?
- Have the single downloads been tested?

Workaround:

```text
Download VIU XML separately
Download VO XML separately
Download README separately
```

## No position updates

VLX2MQTT intentionally works event-driven. If no position updates arrive:

1. Check KLF connection.
2. Check MQTT.
3. Check log for KLF / pyvlx errors.
4. Check event monitor warnings.
5. Move a device physically and observe MQTT output.

## Old MQTT topics remain visible

When switching from `topic_identifier = name` to `node_id` or vice versa, old retained topics may remain in the broker.

## Recovery does not trigger

Check:

```ini
external_recovery_enabled = true
external_recovery_threshold = 4
external_recovery_topic = vlx2mqtt/recovery/powercycle_required
```

Relevant errors:

```text
klf_connection_refused
klf_disconnected
klf_unreachable
```

---

<p align="center">
  <a href="README.md">Back to contents</a><br><br>
  <img src="../../icons/icon.svg" alt="VLX2MQTT logo small" width="42"><br>
  <strong>VLX2MQTT</strong><br>
  LoxBerry · MQTT · VELUX KLF200
</p>

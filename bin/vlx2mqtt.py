#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vlx2mqtt.py
"""

import configparser
import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from logging.handlers import WatchedFileHandler
from typing import Any, Optional

import paho.mqtt.client as mqtt
from pyvlx import OpeningDevice, PyVLX

# ============================================================
# pyvlx payload patch
# ============================================================

def apply_pyvlx_patch():
    try:
        from pyvlx.api.frames.frame_command_send import FrameCommandSendRequest

        def patched_get_payload(self):
            assert self.session_id is not None

            ret = bytearray()
            ret += bytes([self.session_id >> 8 & 0xFF, self.session_id & 0xFF])
            ret += bytes([self.originator.value])
            ret += bytes([self.priority.value])
            ret += bytes([self.active_parameter])
            ret += bytes([self.fpi1])
            ret += bytes([self.fpi2])

            # Hauptparameter robust bestimmen
            param = 0
            try:
                param = int(self.parameter)
            except Exception:
                try:
                    raw = getattr(self.parameter, "position_percent", None)
                    if raw is not None:
                        raw = int(raw)
                        if raw == 100:
                            param = 200
                        elif raw == 0:
                            param = 0
                        else:
                            param = int(raw * 2)
                except Exception:
                    param = 0

            ret += bytes([param & 0xFF])
            ret += bytes([0, 0, 0])
            ret += bytes(30)
            ret += bytes([len(self.node_ids)])
            ret += bytes(self.node_ids)
            ret += bytes(20 - len(self.node_ids))
            ret += bytes([0])
            ret += bytes([0, 0])
            ret += bytes([0])

            if len(ret) != 66:
                raise RuntimeError(f"Payload len wrong: {len(ret)} (expected 66)")

            return bytes(ret)

        FrameCommandSendRequest.get_payload = patched_get_payload
        logging.info("Applied pyvlx payload patch")
    except Exception:
        logging.exception("Failed to apply pyvlx patch")


apply_pyvlx_patch()

# ============================================================
# Konfiguration
# ============================================================
DEFAULT_CFG = {
    "klf_host": "VELUX-KLF-DE3B.fritz.box",
    "klf_pw": "",
    "mqtt_host": "127.0.0.1",
    "mqtt_port": 1883,
    "mqtt_user": "loxberry",
    "mqtt_pw": "",
    "root_topic": "vlx2mqtt",
    "initial_delay": 2.5,
    "connect_timeout": 30.0,
    "moving_timeout": 60.0,
    "backoff_max": 30.0,
    "verbose": False,
    "logfile": "/opt/loxberry/log/plugins/vlx2mqtt/vlx2mqtt.log",
    "external_recovery_enabled": False,
    "external_recovery_threshold": 4,
    "external_recovery_cooldown": 1800.0,
    "external_recovery_grace": 120.0,
    "external_recovery_topic": "vlx2mqtt/recovery/powercycle_required",
    "preventive_recovery_hours": 0.0,
    "topic_identifier": "name",
    "rain_poll_interval": 300,
    "publish_rain_raw_limit": False,
}

LOGFORMAT = "%(asctime)-15s %(levelname)s %(message)s"


def _cfg_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def load_cfg_file(path: str) -> dict:
    cfg = DEFAULT_CFG.copy()

    parser = configparser.ConfigParser()
    read_files = parser.read(path, encoding="utf-8")

    if not read_files:
        print(f"WARNING: config file not found or unreadable: {path}", file=sys.stderr)
        return cfg

    section = "vlx2mqtt" if parser.has_section("vlx2mqtt") else "DEFAULT"
    sec = parser[section]

    cfg["klf_host"] = sec.get("klf_host", fallback=cfg["klf_host"])
    cfg["klf_pw"] = sec.get("klf_pw", fallback=cfg["klf_pw"])
    cfg["mqtt_host"] = sec.get("mqtt_host", fallback=cfg["mqtt_host"])
    cfg["mqtt_port"] = sec.getint("mqtt_port", fallback=cfg["mqtt_port"])
    cfg["mqtt_user"] = sec.get("mqtt_user", fallback=cfg["mqtt_user"])
    cfg["mqtt_pw"] = sec.get("mqtt_pw", fallback=cfg["mqtt_pw"])
    cfg["root_topic"] = sec.get("root_topic", fallback=cfg["root_topic"]).strip().strip("/")
    cfg["initial_delay"] = sec.getfloat("initial_delay", fallback=cfg["initial_delay"])
    cfg["connect_timeout"] = sec.getfloat("connect_timeout", fallback=cfg["connect_timeout"])
    cfg["moving_timeout"] = sec.getfloat("moving_timeout", fallback=cfg["moving_timeout"])
    cfg["backoff_max"] = sec.getfloat("backoff_max", fallback=cfg["backoff_max"])
    cfg["verbose"] = _cfg_bool(
        sec.get("verbose", fallback=str(cfg["verbose"])),
        default=cfg["verbose"],
    )
    cfg["logfile"] = sec.get("logfile", fallback=cfg["logfile"])
    cfg["external_recovery_enabled"] = _cfg_bool(
        sec.get("external_recovery_enabled", fallback=str(cfg["external_recovery_enabled"])),
        default=cfg["external_recovery_enabled"],
    )
    cfg["external_recovery_threshold"] = sec.getint(
        "external_recovery_threshold", fallback=cfg["external_recovery_threshold"]
    )
    cfg["external_recovery_cooldown"] = sec.getfloat(
        "external_recovery_cooldown", fallback=cfg["external_recovery_cooldown"]
    )
    cfg["external_recovery_grace"] = sec.getfloat(
        "external_recovery_grace", fallback=cfg["external_recovery_grace"]
    )
    cfg["external_recovery_topic"] = sec.get(
        "external_recovery_topic", fallback=cfg["external_recovery_topic"]
    )
    cfg["preventive_recovery_hours"] = sec.getfloat(
        "preventive_recovery_hours", fallback=cfg["preventive_recovery_hours"]
    )
    cfg["topic_identifier"] = sec.get(
        "topic_identifier", fallback=cfg["topic_identifier"]
    ).strip().lower()
    if cfg["topic_identifier"] not in ("name", "node_id"):
        cfg["topic_identifier"] = DEFAULT_CFG["topic_identifier"]
    cfg["rain_poll_interval"] = sec.getint(
        "rain_poll_interval", fallback=cfg["rain_poll_interval"]
    )
    cfg["publish_rain_raw_limit"] = _cfg_bool(
        sec.get("publish_rain_raw_limit", fallback=str(cfg["publish_rain_raw_limit"])),
        default=cfg["publish_rain_raw_limit"],
    )

    return cfg


CFG_PATH = sys.argv[1] if len(sys.argv) > 1 else "/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg"
CFG = load_cfg_file(CFG_PATH)
LOGFILE = CFG["logfile"]

# ============================================================
# Hilfsfunktionen
# ============================================================

def normalize_from_device(raw: Any) -> Optional[int]:
    """VELUX-Rohwerte sicher in 0..100 umwandeln."""
    try:
        txt = str(raw).replace("%", "").strip()
        if txt.upper() in ("UNKNOWN", "CURRENT", ""):
            return None
        v = int(float(txt))
    except Exception:
        return None

    # bekannter Ghost-Rohwert -> unterdrücken
    if v == 124:
        return None

    # Velux liefert oft 0..200
    if v > 100:
        v = int(v / 2)

    if v < 0:
        v = 0
    elif v > 100:
        v = 100

    return v


def scale_to_device(v_raw: Any) -> Optional[int]:
    try:
        v = int(round(float(v_raw)))
    except Exception:
        return None
    if v < 0 or v > 100:
        return None
    return int(v * 2)


def parse_target(node, st: dict) -> Optional[int]:
    """
    Liest das Ziel
    """
    target = None

    try:
        target_raw = getattr(node.target, "position_percent", None)
        if target_raw is not None:
            raw_upper = str(target_raw).upper().strip()
            if raw_upper == "CURRENT":
                return None
            target = normalize_from_device(target_raw)
    except Exception:
        target = None

    # Nur wenn kein STOP aktiv ist, darf pending_target als Fallback dienen
    if target is None and not st.get("stop_in_progress", False):
        cmd_ts = st.get("command_ts")
        if cmd_ts and (time.time() - cmd_ts) < 5.0:
            pt = st.get("pending_target")
            if isinstance(pt, int):
                target = pt

    return target


def parse_position(node) -> Optional[int]:
    try:
        raw = getattr(node.position, "position_percent", None)
        return normalize_from_device(raw)
    except Exception:
        return None


def get_run_status(node) -> str:
    try:
        rs = getattr(node, "last_frame_run_status", None)
        return str(rs) if rs is not None else ""
    except Exception:
        return ""


def get_state(node) -> str:
    try:
        st = getattr(node, "last_frame_state", None)
        return str(st).upper() if st is not None else ""
    except Exception:
        return ""


def should_be_moving(st: dict, pos: Optional[int], target: Optional[int], run_status: str, state_str: str) -> bool:
    """
    Stabile moving-Logik ohne Interpolation.
    """
    rs = str(run_status).upper()
    state_u = str(state_str).upper()

    recent_cmd = False
    cmd_ts = st.get("command_ts")
    if cmd_ts:
        recent_cmd = (time.time() - cmd_ts) < 5.0

    active = any(k in rs for k in (
        "EXECUTION_ACTIVE",
        "EXECUTING",
        "RUNNING",
        "IN_PROGRESS",
        "ACTIVE",
    ))

    completed = any(k in rs for k in (
        "EXECUTION_COMPLETED",
        "COMMAND_COMPLETED_OK",
        "COMPLETED",
        "DONE",
    )) or ("DONE" in state_u)

    waiting = any(k in state_u for k in ("NOT_USED", "WAIT_FOR_POWER"))

    # Sonderfall STOP/CURRENT
    if st.get("stop_in_progress", False):
        if active or (recent_cmd and waiting):
            return True
        if completed:
            return False
        return True

    # Standardlogik
    if active:
        return True

    if recent_cmd and waiting:
        return True

    if completed and pos is not None and target is not None and abs(pos - target) <= 1:
        return False

    if completed and (target is None or pos is None or abs(pos - target) <= 1):
        return False

    if recent_cmd and pos is not None and target is not None and abs(pos - target) > 1:
        return True

    return False


def sanitize_topic_part(value: Any) -> str:
    txt = str(value).strip()
    txt = txt.replace(" ", "_")
    safe = []
    for ch in txt:
        if ch.isalnum() or ch in ("_", "-"):
            safe.append(ch)
        else:
            safe.append("_")
    return "".join(safe)


def get_topic_identifier_mode() -> str:
    mode = str(CFG.get("topic_identifier", "name")).strip().lower()
    return "node_id" if mode == "node_id" else "name"


def get_node_state_key(node) -> str:
    node_id = getattr(node, "node_id", None)
    if node_id is not None:
        return f"id:{node_id}"
    return f"name:{getattr(node, 'name', '')}"


def get_node_topic_id(node) -> str:
    """
    Gibt den Identifier zurück, der im MQTT-Topic verwendet wird:
    - node.name
    - oder node.node_id
    """
    if get_topic_identifier_mode() == "node_id":
        node_id = getattr(node, "node_id", None)
        if node_id is not None:
            return str(node_id)

    name = getattr(node, "name", None)
    if name:
        return sanitize_topic_part(name)

    node_id = getattr(node, "node_id", None)
    if node_id is not None:
        return str(node_id)

    return "unknown"


def build_node_topic(node, suffix: str) -> str:
    return f"{CFG['root_topic']}/{get_node_topic_id(node)}/{suffix}"


def node_matches_identifier(node, identifier: str) -> bool:
    """
    Prüft, ob ein empfangener Identifier zu diesem Node passt.
    """
    ident = str(identifier).strip()
    mode = get_topic_identifier_mode()

    if mode == "node_id":
        node_id = getattr(node, "node_id", None)
        return node_id is not None and ident == str(node_id)

    # name-Modus
    name = getattr(node, "name", None)
    if name and ident == sanitize_topic_part(name):
        return True

    # Toleranter Fallback im name-Modus:
    node_id = getattr(node, "node_id", None)
    if node_id is not None and ident == str(node_id):
        return True

    return False


def find_node_by_identifier(identifier: str):
    for node in getattr(pyvlx, "nodes", []):
        if not isinstance(node, OpeningDevice):
            continue
        if node_matches_identifier(node, identifier):
            return node
    return None


async def read_rain_state(node) -> tuple[Optional[bool], Optional[int]]:
    """
    Ermittelt Regenstatus indirekt über die Öffnungsbegrenzung.
    Heuristik wie in Home Assistant:
    limitation_min >= 89 => Regen erkannt
    """
    try:
        if not hasattr(node, "get_limitation_min"):
            logging.debug(
                "read_rain_state: node %s has no get_limitation_min",
                getattr(node, "name", ""),
            )
            return None, None

        limitation = await node.get_limitation_min()
        logging.debug(
            "read_rain_state: limitation for %s -> %r",
            getattr(node, "name", ""),
            limitation,
        )

        if limitation is None:
            return None, None

        raw = getattr(limitation, "position_percent", None)
        if raw is None:
            raw = getattr(limitation, "min_value", None)

        logging.debug(
            "read_rain_state: raw limitation for %s -> %r",
            getattr(node, "name", ""),
            raw,
        )

        if raw is None:
            return None, None

        raw_int = int(raw)
        return (raw_int >= 89), raw_int

    except Exception:
        logging.exception("read_rain_state failed for %s", getattr(node, "name", ""))
        return None, None



# ============================================================
# Logging
# ============================================================

def setup_logging() -> None:
    loglevel = logging.DEBUG if CFG.get("verbose", False) else logging.INFO

    try:
        logdir = os.path.dirname(LOGFILE)
        if logdir and not os.path.isdir(logdir):
            os.makedirs(logdir, exist_ok=True)
    except Exception:
        pass

    handler = WatchedFileHandler(
        LOGFILE,
        mode="a",
        encoding="utf-8",
        delay=False,
    )
    handler.setFormatter(logging.Formatter(LOGFORMAT))
    handler.setLevel(loglevel)

    root = logging.getLogger()
    root.setLevel(loglevel)

    for h in list(root.handlers):
        try:
            h.flush()
            h.close()
        except Exception:
            pass
        root.removeHandler(h)

    root.addHandler(handler)

    if CFG.get("verbose", False):
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter(LOGFORMAT))
        ch.setLevel(loglevel)
        root.addHandler(ch)

    # Fremdlogger an unser Verbose-Setting koppeln
    for logger_name in ("pyvlx", "asyncio"):
        lib_logger = logging.getLogger(logger_name)
        lib_logger.setLevel(loglevel)

        # Falls Bibliotheken eigene Handler mitbringen:
        for h in list(lib_logger.handlers):
            try:
                h.flush()
                h.close()
            except Exception:
                pass
            lib_logger.removeHandler(h)

        lib_logger.propagate = True

    logging.info("Using config file: %s", CFG_PATH)


setup_logging()
logging.info("Starting vlx2mqtt_rebuild")

# ============================================================
# Globale Laufzeitdaten
# ============================================================
mqtt_connected = False
PUBLISH_QUEUE = []
NODE_STATE = {}
pyvlx = None
LAST_KLF_ERROR = None
LAST_KLF_OK_TS = None
KLF_RECONNECT_IN = None
KLF_STATE = "starting"
SERVICE_STATE = "starting"
SERVICE_DETAIL = None
KLF_REFUSED_COUNT = 0
LAST_EXTERNAL_RECOVERY_TS = None
WAIT_UNTIL_AFTER_RECOVERY = None
RECOVERY_REQUESTED = False
RECOVERY_REASON = None
MAIN_LOOP = None
LAST_PUBLISHED = {}

# ============================================================
# MQTT
# ============================================================
mqttc = mqtt.Client(client_id=f"vlx2mqtt_{os.getpid()}", clean_session=False)
if CFG["mqtt_user"]:
    mqttc.username_pw_set(CFG["mqtt_user"], CFG["mqtt_pw"])

mqttc.will_set(
    f"{CFG['root_topic']}/service_status",
    payload="lost",
    qos=1,
    retain=True,
)


def mqtt_publish(topic: str, payload: Any, qos: int = 1, retain: bool = True):
    global PUBLISH_QUEUE, mqtt_connected
    payload_str = "" if payload is None else str(payload)

    try:
        if mqtt_connected:
            mqttc.publish(topic, payload_str, qos=qos, retain=retain)
            if CFG.get("verbose", False):
                logging.debug("mqtt_publish sent topic=%s payload=%s", topic, payload_str)
        else:
            # Für retained Topics immer nur den letzten Wert pro Topic in der Queue behalten
            if retain:
                PUBLISH_QUEUE = [item for item in PUBLISH_QUEUE if item[0] != topic]

            # Sicherheitslimit
            if len(PUBLISH_QUEUE) > 200:
                PUBLISH_QUEUE.pop(0)

            PUBLISH_QUEUE.append((topic, payload_str, qos, retain))

            if CFG.get("verbose", False):
                logging.debug(
                    "mqtt_publish queued topic=%s payload=%s queue_len=%d",
                    topic, payload_str, len(PUBLISH_QUEUE)
                )

    except Exception:
        logging.exception("mqtt_publish failed")

        if retain:
            PUBLISH_QUEUE = [item for item in PUBLISH_QUEUE if item[0] != topic]

        if len(PUBLISH_QUEUE) > 200:
            PUBLISH_QUEUE.pop(0)

        PUBLISH_QUEUE.append((topic, payload_str, qos, retain))


def classify_klf_error(exc: Exception) -> tuple[str, str]:
    """
    Ordnet KLF-Verbindungs-/Authentifizierungsfehlern einen klaren Status zu.
    Rückgabe:
        (klf_state, klf_error_text)
    """
    txt = ""

    # 1) Beschreibung bevorzugen, falls pyvlx sie als Attribut trägt
    try:
        desc = getattr(exc, "description", None)
        if desc:
            txt = str(desc).strip()
    except Exception:
        pass

    # 2) Normales str(exc)
    if not txt:
        try:
            txt = str(exc).strip()
        except Exception:
            txt = ""

    # 3) repr(exc) als letzter sinnvoller Fallback
    if not txt:
        try:
            txt = repr(exc).strip()
        except Exception:
            txt = ""

    # 4) Ganz harter Fallback
    if not txt:
        txt = "unknown klf error"

    txt_u = txt.upper()

    # Passwort / Auth fehlgeschlagen
    if (
        "FAILED TO AUTHENTICATE" in txt_u
        or "AUTHENTICATE" in txt_u
        or "PASSWORD" in txt_u
        or "PASSWORDENTERCONFIRMATIONSTATUS.AUTHENTICATIONFAILED" in txt_u
        or "LOGIN TO KLF 200 FAILED" in txt_u
        or "CHECK CREDENTIALS" in txt_u
        or "CREDENTIAL" in txt_u
    ):
        return "klf_auth_failed", txt

    # Host erreichbar, Port lehnt aktiv ab
    if (
        "ERRNO 111" in txt_u
        or "CONNECTION REFUSED" in txt_u
        or "CONNECT CALL FAILED" in txt_u
    ):
        return "klf_connection_refused", txt

    # Timeout / nicht erreichbar / DNS / Netzwerk
    if (
        "TIMED OUT" in txt_u
        or "ETIMEDOUT" in txt_u
        or "NAME OR SERVICE NOT KNOWN" in txt_u
        or "TEMPORARY FAILURE IN NAME RESOLUTION" in txt_u
        or "NO ROUTE TO HOST" in txt_u
        or "NETWORK IS UNREACHABLE" in txt_u
        or "HOST UNREACHABLE" in txt_u
    ):
        return "klf_unreachable", txt

    return "klf_disconnected", txt


def mqtt_publish_if_changed(topic: str, payload: Any, qos: int = 1, retain: bool = True):
    """Publiziert nur bei Wertänderung."""
    global LAST_PUBLISHED
    payload_str = "" if payload is None else str(payload)
    if LAST_PUBLISHED.get(topic) == payload_str:
        return
    LAST_PUBLISHED[topic] = payload_str
    mqtt_publish(topic, payload_str, qos=qos, retain=retain)


def compute_status_detail() -> str:
    """Stabiler Detailstatus für Loxone / Diagnose."""
    if SERVICE_STATE != "running":
        return f"service_{SERVICE_STATE}"
    return KLF_STATE


def compute_overall_status() -> str:
    """
    Einfacher Loxone-Status: ok / error
    """
    if SERVICE_STATE == "stopped":
        return "ok"

    if SERVICE_STATE == "running" and KLF_STATE == "klf_connected":
        return "ok"

    return "error"


def submit_coro_from_thread(coro, description: str = ""):
    """
    Plant eine Coroutine thread-sicher auf dem main asyncio loop ein.
    Wird z. B. aus MQTT-Callbacks (Paho-Thread) verwendet.
    """
    global MAIN_LOOP

    if MAIN_LOOP is None or MAIN_LOOP.is_closed():
        logging.error("submit_coro_from_thread: no running MAIN_LOOP for %s", description or coro)
        try:
            coro.close()
        except Exception:
            pass
        return None

    future = asyncio.run_coroutine_threadsafe(coro, MAIN_LOOP)

    def _done_callback(fut):
        try:
            fut.result()
        except Exception:
            logging.exception("Coroutine failed: %s", description or coro)

    future.add_done_callback(_done_callback)
    return future


def publish_service_status():
    """Publiziert den Zustand des Python-Dienstes selbst."""
    try:
        mqtt_publish_if_changed(
            f"{CFG['root_topic']}/service_status",
            SERVICE_STATE,
            qos=1,
            retain=True,
        )

        detail_payload = "" if SERVICE_DETAIL is None else str(SERVICE_DETAIL)
        mqtt_publish_if_changed(
            f"{CFG['root_topic']}/service_detail",
            detail_payload,
            qos=1,
            retain=True,
        )
    except Exception:
        logging.exception("publish_service_status failed")


def publish_bridge_status():
    """
    Publiziert:
      - status         -> ok / error (für Loxone)
      - status_detail  -> stabiler Detailstatus
      - status_live    -> aktueller KLF-Livezustand (inkl. klf_connecting)
      - error_text     -> letzter lesbarer Fehlertext
      - health         -> ausführliches JSON
    """
    try:
        overall_status = compute_overall_status()
        detail_status = compute_status_detail()
        live_status = KLF_STATE

        error_text = ""
        if LAST_KLF_ERROR:
            error_text = str(LAST_KLF_ERROR)
        elif SERVICE_DETAIL:
            error_text = str(SERVICE_DETAIL)

        mqtt_publish_if_changed(
            f"{CFG['root_topic']}/status",
            overall_status,
            qos=1,
            retain=True,
        )

        mqtt_publish_if_changed(
            f"{CFG['root_topic']}/status_detail",
            detail_status,
            qos=1,
            retain=True,
        )

        mqtt_publish_if_changed(
            f"{CFG['root_topic']}/status_live",
            live_status,
            qos=1,
            retain=True,
        )

        mqtt_publish_if_changed(
            f"{CFG['root_topic']}/error_text",
            error_text,
            qos=1,
            retain=True,
        )

        payload = json.dumps({
            "bridge": "running",
            "service": SERVICE_STATE,
            "service_detail": SERVICE_DETAIL,
            "status": overall_status,
            "status_detail": detail_status,
            "status_live": live_status,
            "klf": KLF_STATE,
            "mqtt": "connected" if mqtt_connected else "disconnected",
            "nodes": len(getattr(pyvlx, "nodes", [])) if pyvlx else 0,
            "last_klf_ok_ts": LAST_KLF_OK_TS,
            "last_klf_error": LAST_KLF_ERROR,
            "reconnect_in": KLF_RECONNECT_IN,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        mqtt_publish(f"{CFG['root_topic']}/health", payload, qos=1, retain=True)

    except Exception:
        logging.exception("publish_bridge_status failed")

def publish_recovery_status():
    """
    Publiziert den Status für eine externe Recovery (z. B. Loxone + schaltbare Steckdose).
    """
    try:
        mqtt_publish_if_changed(
            CFG["external_recovery_topic"],
            "true" if RECOVERY_REQUESTED else "false",
            qos=1,
            retain=True,
        )
        mqtt_publish_if_changed(
            f"{CFG['root_topic']}/recovery/reason",
            "" if RECOVERY_REASON is None else str(RECOVERY_REASON),
            qos=1,
            retain=True,
        )
        mqtt_publish_if_changed(
            f"{CFG['root_topic']}/recovery/failure_count",
            KLF_REFUSED_COUNT,
            qos=1,
            retain=True,
        )
        mqtt_publish_if_changed(
            f"{CFG['root_topic']}/recovery/state",
            "requested" if RECOVERY_REQUESTED else "idle",
            qos=1,
            retain=True,
        )
    except Exception:
        logging.exception("publish_recovery_status failed")


def publish_node_metadata():
    """
    Publiziert Zuordnung name <-> node_id als retained Topics.
    Hilfreich für Loxone / Debugging.
    """
    try:
        for node in getattr(pyvlx, "nodes", []):
            if not isinstance(node, OpeningDevice):
                continue

            node_id = getattr(node, "node_id", None)
            node_name = getattr(node, "name", "")

            if node_id is None:
                continue

            mqtt_publish_if_changed(
                f"{CFG['root_topic']}/{node_id}/name",
                node_name,
                qos=1,
                retain=True,
            )

            mqtt_publish_if_changed(
                f"{CFG['root_topic']}/{node_id}/node_id",
                node_id,
                qos=1,
                retain=True,
            )

            mqtt_publish_if_changed(
                f"{CFG['root_topic']}/name_map/{sanitize_topic_part(node_name)}",
                node_id,
                qos=1,
                retain=True,
            )

    except Exception:
        logging.exception("publish_node_metadata failed")


def request_external_recovery(reason: str):
    """
    Fordert eine externe Recovery an (typisch: Loxone schaltet Steckdose aus/ein).
    """
    global RECOVERY_REQUESTED, RECOVERY_REASON, LAST_EXTERNAL_RECOVERY_TS, WAIT_UNTIL_AFTER_RECOVERY, SERVICE_DETAIL

    now = time.time()
    RECOVERY_REQUESTED = True
    RECOVERY_REASON = reason
    LAST_EXTERNAL_RECOVERY_TS = now
    WAIT_UNTIL_AFTER_RECOVERY = now + float(CFG["external_recovery_grace"])

    SERVICE_DETAIL = f"external recovery requested: {reason}"
    publish_service_status()
    publish_bridge_status()
    publish_recovery_status()


def clear_external_recovery():
    """
    Setzt den externen Recovery-Status zurück.
    """
    global RECOVERY_REQUESTED, RECOVERY_REASON, WAIT_UNTIL_AFTER_RECOVERY
    RECOVERY_REQUESTED = False
    RECOVERY_REASON = None
    WAIT_UNTIL_AFTER_RECOVERY = None
    publish_recovery_status()


def any_node_moving() -> bool:
    for st in NODE_STATE.values():
        if st.get("moving"):
            return True
    return False


def mqtt_on_connect(client, userdata, flags, rc, properties=None):
    global mqtt_connected
    mqtt_connected = (rc == 0)

    if mqtt_connected:
        logging.info("MQTT connected rc=%s", rc)
        try:
            sub_topic = f"{CFG['root_topic']}/+/set"
            client.subscribe(sub_topic)
            logging.debug("MQTT subscribed to %s", sub_topic)
        except Exception:
            logging.exception("subscribe failed")

        while PUBLISH_QUEUE:
            topic, payload, qos, retain = PUBLISH_QUEUE.pop(0)
            try:
                client.publish(topic, payload, qos=qos, retain=retain)
                if CFG.get("verbose", False):
                    logging.debug("mqtt_publish flushed topic=%s payload=%s", topic, payload)
            except Exception:
                logging.exception("publish queue flush failed")
                PUBLISH_QUEUE.insert(0, (topic, payload, qos, retain))
                break

        publish_service_status()
        publish_bridge_status()
        publish_recovery_status()
    else:
        logging.warning("MQTT connect failed rc=%s", rc)


def mqtt_on_disconnect(client, userdata, rc, properties=None):
    global mqtt_connected
    mqtt_connected = False
    logging.warning("MQTT disconnected rc=%s", rc)


def mqtt_on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode().strip()
    except Exception:
        payload = str(msg.payload)

    topic = str(msg.topic).strip()
    root = str(CFG["root_topic"]).strip()

    if not topic.startswith(root + "/"):
        return

    if not topic.endswith("/set"):
        return

    rel = topic[len(root) + 1:]
    parts = rel.split("/")

    if len(parts) < 2 or parts[-1] != "set":
        logging.warning("Ignoring unsupported command topic: %s", topic)
        return

    identifier = "/".join(parts[:-1]).strip()
    node = find_node_by_identifier(identifier)
    if node is None:
        logging.warning("No matching node found for topic identifier '%s' (topic=%s)", identifier, topic)
        return

    stkey = get_node_state_key(node)
    st = NODE_STATE.setdefault(stkey, {})
    st["node_name"] = getattr(node, "name", "")
    st["node_id"] = getattr(node, "node_id", None)
    st["topic_id"] = get_node_topic_id(node)

    value_u = payload.strip().upper()

    try:
        if value_u in ("UP", "OPEN"):
            submit_coro_from_thread(
                node.open(wait_for_completion=False),
                description=f"open:{st.get('topic_id') or getattr(node, 'name', '')}",
            )
            st["command_ts"] = time.time()
            st["pending_target"] = 0

        elif value_u in ("DOWN", "CLOSE"):
            submit_coro_from_thread(
                node.close(wait_for_completion=False),
                description=f"close:{st.get('topic_id') or getattr(node, 'name', '')}",
            )
            st["command_ts"] = time.time()
            st["pending_target"] = 100

        elif value_u == "STOP":
            submit_coro_from_thread(
                node.stop(),
                description=f"stop:{st.get('topic_id') or getattr(node, 'name', '')}",
            )
            st["command_ts"] = time.time()

        else:
            try:
                pos = int(float(payload))
            except Exception:
                logging.warning("Unsupported command payload '%s' for topic %s", payload, topic)
                return

            submit_coro_from_thread(
                safe_set_position(
                    node,
                    pos,
                    st.get("topic_id") or getattr(node, "name", ""),
                    st,
                ),
                description=f"set_position:{st.get('topic_id') or getattr(node, 'name', '')}:{pos}",
            )

    except Exception:
        logging.exception("mqtt_on_message failed for topic=%s payload=%s", topic, payload)


def mqtt_on_publish(client, userdata, mid):
    if CFG.get("verbose", False):
        logging.debug("mqtt_on_publish mid=%s", mid)


mqttc.on_connect = mqtt_on_connect
mqttc.on_message = mqtt_on_message
mqttc.on_publish = mqtt_on_publish
mqttc.on_disconnect = mqtt_on_disconnect

# ============================================================
# KLF / pyvlx
# ============================================================

async def connect_pyvlx(stop_event: asyncio.Event):
    global pyvlx
    global LAST_KLF_ERROR, LAST_KLF_OK_TS, KLF_RECONNECT_IN, KLF_STATE
    global SERVICE_STATE, SERVICE_DETAIL
    global KLF_REFUSED_COUNT, LAST_EXTERNAL_RECOVERY_TS, WAIT_UNTIL_AFTER_RECOVERY

    backoff = 1.0
    attempt = 0

    while True:
        if WAIT_UNTIL_AFTER_RECOVERY is not None:
            remaining = WAIT_UNTIL_AFTER_RECOVERY - time.time()
            if remaining > 0:
                SERVICE_STATE = "running"
                SERVICE_DETAIL = f"waiting after external recovery ({remaining:.0f}s)"
                publish_service_status()
                publish_bridge_status()
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=min(remaining, 5.0))
                    logging.info("connect_pyvlx aborted during recovery wait")
                    return False
                except asyncio.TimeoutError:
                    pass
                continue
            else:
                WAIT_UNTIL_AFTER_RECOVERY = None
                
        if stop_event.is_set():
            logging.info("connect_pyvlx aborted by stop request")
            return False

        attempt += 1

        SERVICE_STATE = "running"
        SERVICE_DETAIL = "waiting for KLF"

        KLF_STATE = "klf_connecting"
        KLF_RECONNECT_IN = None
        publish_service_status()
        publish_bridge_status()

        try:
            logging.info("pyvlx connect attempt %d", attempt)
            pyvlx = PyVLX(host=CFG["klf_host"], password=CFG["klf_pw"])
            await asyncio.wait_for(pyvlx.load_nodes(), timeout=CFG["connect_timeout"])

            LAST_KLF_ERROR = None
            LAST_KLF_OK_TS = datetime.now(timezone.utc).isoformat()
            KLF_RECONNECT_IN = None
            KLF_STATE = "klf_connected"

            SERVICE_STATE = "running"
            SERVICE_DETAIL = None

            logging.info("pyvlx: nodes loaded %d", len(pyvlx.nodes))
            publish_service_status()
            publish_bridge_status()
            KLF_REFUSED_COUNT = 0
            clear_external_recovery()
            return True

        except Exception as e:
            pyvlx = None

            klf_state, err_text = classify_klf_error(e)
            KLF_STATE = klf_state
            LAST_KLF_ERROR = err_text
            
            if klf_state == "klf_connection_refused":
                KLF_REFUSED_COUNT += 1
            else:
                KLF_REFUSED_COUNT = 0

            publish_recovery_status()

            if CFG.get("external_recovery_enabled", False):
                if klf_state == "klf_connection_refused" and KLF_REFUSED_COUNT >= int(CFG["external_recovery_threshold"]):
                    cooldown_ok = (
                        LAST_EXTERNAL_RECOVERY_TS is None
                        or (time.time() - LAST_EXTERNAL_RECOVERY_TS) >= float(CFG["external_recovery_cooldown"])
                    )
                    if cooldown_ok and not RECOVERY_REQUESTED:
                        logging.warning(
                            "Requesting external recovery after %d refused connections",
                            KLF_REFUSED_COUNT,
                        )
                        request_external_recovery("klf_connection_refused")

            wait_s = min(backoff, CFG["backoff_max"])
            KLF_RECONNECT_IN = wait_s

            SERVICE_STATE = "running"
            if not RECOVERY_REQUESTED:
                SERVICE_DETAIL = f"KLF retry in {wait_s:.1f}s"

            logging.warning("pyvlx connect failed: %r", e)
            logging.debug("pyvlx connect error text: %s", err_text)
            logging.debug("classified KLF error as: %s", klf_state)
            logging.debug("reconnect in %.1fs", wait_s)

            publish_service_status()
            publish_bridge_status()

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=wait_s)
                logging.info("connect_pyvlx interrupted during backoff")
                return False
            except asyncio.TimeoutError:
                pass

            backoff = min(backoff * 2, CFG["backoff_max"])


async def poll_rain_sensors_once():
    """
    Pollt den indirekten Regenstatus genau einmal.
    """
    logging.debug("poll_rain_sensors_once: start")

    for node in getattr(pyvlx, "nodes", []):
        if not isinstance(node, OpeningDevice):
            continue

        node_name = getattr(node, "name", "")
        node_id = getattr(node, "node_id", None)

        type_candidates = {
            "node_type": getattr(node, "node_type", None),
            "type": getattr(node, "type", None),
            "sub_type": getattr(node, "sub_type", None),
            "node_type_subtype": getattr(node, "node_type_subtype", None),
            "product_group": getattr(node, "product_group", None),
            "product_type": getattr(node, "product_type", None),
        }

        logging.debug(
            "poll_rain_sensors_once: node=%s node_id=%s type_candidates=%r",
            node_name,
            node_id,
            type_candidates,
        )

        if not str(node_name).lower().startswith("fenster"):
            logging.debug(
                "poll_rain_sensors_once: skip node name=%s node_id=%s (not a window by name)",
                node_name,
                node_id,
            )
            continue

        logging.debug(
            "poll_rain_sensors_once: reading rain state for name=%s node_id=%s",
            node_name,
            node_id,
        )

        rain, raw_limit = await read_rain_state(node)

        logging.debug(
            "poll_rain_sensors_once: result name=%s node_id=%s rain=%s raw_limit=%s",
            node_name,
            node_id,
            rain,
            raw_limit,
        )

        if rain is None:
            continue

        mqtt_publish_if_changed(
            build_node_topic(node, "rain"),
            "true" if rain else "false",
            qos=1,
            retain=True,
        )

        if _cfg_bool(CFG.get("publish_rain_raw_limit", False), False) and raw_limit is not None:
            mqtt_publish_if_changed(
                build_node_topic(node, "rain_raw_limit"),
                raw_limit,
                qos=1,
                retain=True,
            )


async def poll_rain_sensors():
    """
    Pollt den indirekten Regenstatus nur für Fensternodes mit Regensensor.
    """
    interval = max(60, int(float(CFG.get("rain_poll_interval", 300))))

    while True:
        try:
            await poll_rain_sensors_once()
        except Exception:
            logging.exception("poll_rain_sensors failed")

        await asyncio.sleep(interval)


# ============================================================
# Hintergrundtasks
# ============================================================

async def publish_initial_snapshot():
    await asyncio.sleep(CFG["initial_delay"])

    for node in getattr(pyvlx, "nodes", []):
        if not isinstance(node, OpeningDevice):
            continue

        try:
            stkey = get_node_state_key(node)
            st = NODE_STATE.setdefault(stkey, {})
            st["node_name"] = getattr(node, "name", "")
            st["node_id"] = getattr(node, "node_id", None)
            st["topic_id"] = get_node_topic_id(node)

            pos = parse_position(node)
            if pos is not None:
                st["last_published_pos"] = pos
                st["last_pos"] = pos
                mqtt_publish_if_changed(
                    build_node_topic(node, "position"),
                    pos,
                )

            mqtt_publish_if_changed(
                build_node_topic(node, "moving"),
                "true" if st.get("moving") else "false",
            )

        except Exception:
            logging.exception(
                "publish_initial_snapshot failed for %s",
                getattr(node, "name", ""),
            )


async def publish_health_task():
    await asyncio.sleep(60)

    while True:
        try:
            publish_bridge_status()
        except Exception:
            logging.exception("publish_health_task error")
        await asyncio.sleep(60)


async def moving_watchdog():
    while True:
        try:
            now = time.time()
            for stkey, st in list(NODE_STATE.items()):
                if not st.get("moving"):
                    continue
                cmd_ts = st.get("command_ts")
                if not cmd_ts:
                    continue
                if now - cmd_ts > CFG["moving_timeout"]:
                    st["moving"] = False
                    st["pending_target"] = None
                    mqtt_publish(f"{CFG['root_topic']}/{name}/moving", "false")
                    node_label = st.get("topic_id") or st.get("node_name") or stkey
                    logging.warning("watchdog: %s forced to moving=false after timeout", node_label)
        except Exception:
            logging.exception("moving_watchdog error")
        await asyncio.sleep(1.0)


# ============================================================
# Node-Update-Handler
# ============================================================
async def on_node_update(node):
    try:
        stkey = get_node_state_key(node)
        st = NODE_STATE.setdefault(stkey, {})
        st["node_name"] = getattr(node, "name", "")
        st["node_id"] = getattr(node, "node_id", None)
        st["topic_id"] = get_node_topic_id(node)
        st["last_update_ts"] = time.time()

        pos = parse_position(node)
        target = parse_target(node, st)
        run_status = get_run_status(node)
        state_str = get_state(node)

        node_label = st.get("topic_id") or st.get("node_name") or stkey

        if pos is not None:
            last_pub = st.get("last_published_pos")
            if pos != last_pub:
                st["last_published_pos"] = pos
                st["last_pos"] = pos
                mqtt_publish_if_changed(
                    build_node_topic(node, "position"),
                    pos,
                )

        if target is not None:
            st["last_target"] = target

        if run_status:
            st["last_run_status"] = run_status

        # STOP/CURRENT / COMMAND_OVERRULED sauber behandeln
        is_overruled = False
        last_reply_str = ""

        try:
            last_reply = getattr(node, "last_frame_status_reply", None)
            last_reply_str = str(last_reply).upper() if last_reply is not None else ""
            is_overruled = "OVERRULED" in last_reply_str
        except Exception:
            last_reply_str = ""
            is_overruled = False

        if "OVERRULED" in last_reply_str and st.get("stop_in_progress", False):
            logging.debug("%s: COMMAND_OVERRULED during stop_in_progress", node_label)

        try:
            raw_target_field = getattr(node.target, "position_percent", None)
            if raw_target_field is not None and str(raw_target_field).upper().strip() == "CURRENT":
                logging.debug("%s: CURRENT target observed", node_label)
        except Exception:
            pass

        # Sonderfall STOP
        if st.get("stop_in_progress", False) and is_overruled:
            moving = True
        else:
            moving = should_be_moving(st, pos, target, run_status, state_str)

        prev_moving = st.get("moving", False)
        st["moving"] = moving

        # STOP-Übergang sauber abschließen
        rs_upper = str(run_status or "").upper()
        if st.get("stop_in_progress", False):
            raw_target_field = None
            try:
                raw_target_field = getattr(node.target, "position_percent", None)
            except Exception:
                raw_target_field = None

            raw_target_upper = str(raw_target_field).upper().strip() if raw_target_field is not None else ""

            final_stop_done = (
                pos is not None
                and (
                    "DONE" in state_str
                    or "COMPLETED" in rs_upper
                    or "COMMAND_COMPLETED_OK" in rs_upper
                )
                and raw_target_upper != "CURRENT"
            )

            if final_stop_done:
                st["last_target"] = pos
                st["pending_target"] = None
                st["stop_in_progress"] = False

        # Wenn Ziel erreicht/completed -> pending_target löschen
        if pos is not None and target is not None:
            if abs(pos - target) <= 1 and (
                "DONE" in state_str
                or "COMPLETED" in rs_upper
                or "COMMAND_COMPLETED_OK" in rs_upper
            ):
                st["pending_target"] = None

        if prev_moving != moving:
            mqtt_publish_if_changed(
                build_node_topic(node, "moving"),
                "true" if st.get("moving") else "false",
            )
            logging.info(
                "%s moving: %s (run_status=%s target=%s pos=%s)",
                node_label,
                moving,
                run_status,
                target,
                pos,
            )

    except Exception:
        logging.exception("on_node_update")



# ============================================================
# Befehle
# ============================================================
async def safe_set_position(device, value: int, name: str, st: dict):
    v = scale_to_device(value)
    if v is None:
        logging.warning("safe_set_position: invalid value for %s: %s", name, value)
        mqtt_publish(f"{CFG['root_topic']}/{name}/set/ack", f"ERROR:INVALID:{value}", qos=1, retain=False)
        return False

    try:
        await device.set_position(v, wait_for_completion=False)
        logging.debug(
            "safe_set_position ok for %s: requested=%s device=%s",
            name,
            value,
            v,
        )
        return True
    except Exception:
        logging.exception("safe_set_position failed for %s", name)

    # Fallback für Grenzen
    try:
        if value == 0:
            await device.open(wait_for_completion=False)
            return True
        if value == 100:
            await device.close(wait_for_completion=False)
            return True
    except Exception:
        logging.exception("safe_set_position fallback failed for %s", name)

    mqtt_publish(f"{CFG['root_topic']}/{name}/set/ack", f"ERROR:{value}", qos=1, retain=False)
    return False


async def preventive_recovery_task():
    """
    Optionaler präventiver Recovery-Request alle X Stunden.
    Standardmäßig deaktiviert (preventive_recovery_hours = 0).
    Nur wenn KLF verbunden ist und gerade nichts fährt.
    """
    hours = float(CFG.get("preventive_recovery_hours", 0.0))
    if hours <= 0:
        return

    interval = hours * 3600.0
    last_request_ts = time.time()

    while True:
        try:
            await asyncio.sleep(60)

            if not CFG.get("external_recovery_enabled", False):
                continue
            if RECOVERY_REQUESTED:
                continue
            if KLF_STATE != "klf_connected":
                continue
            if any_node_moving():
                continue

            if (time.time() - last_request_ts) >= interval:
                logging.warning("Requesting preventive external recovery")
                request_external_recovery("preventive_interval")
                last_request_ts = time.time()

        except asyncio.CancelledError:
            return
        except Exception:
            logging.exception("preventive_recovery_task error")


# ============================================================
# Main
# ============================================================
async def main():
    global pyvlx
    global SERVICE_STATE, SERVICE_DETAIL, KLF_STATE
    global MAIN_LOOP

    SERVICE_STATE = "starting"
    SERVICE_DETAIL = "initializing"

    tasks = []
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    MAIN_LOOP = loop

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    try:
        logging.debug("KLF host: %s", CFG["klf_host"])
        logging.debug("MQTT broker: %s:%s", CFG["mqtt_host"], CFG["mqtt_port"])
        logging.debug("Topic identifier mode: %s", get_topic_identifier_mode())

        mqttc.loop_start()
        try:
            mqttc.connect_async(CFG["mqtt_host"], CFG["mqtt_port"], 60)
        except Exception:
            logging.exception("mqtt connect_async failed")

        clear_external_recovery()
        publish_service_status()
        publish_bridge_status()

        SERVICE_STATE = "running"
        SERVICE_DETAIL = "connecting to KLF"

        ok = await connect_pyvlx(stop_event)
        if not ok:
            logging.info("Stopping before KLF connection completed")
            return

        SERVICE_STATE = "running"
        SERVICE_DETAIL = None
        publish_service_status()
        clear_external_recovery()

        # Nodes vorbereiten / überwachen
        for node in pyvlx.nodes:
            if not isinstance(node, OpeningDevice):
                continue

            stkey = get_node_state_key(node)
            st = NODE_STATE.setdefault(stkey, {
                "node_name": getattr(node, "name", ""),
                "node_id": getattr(node, "node_id", None),
                "topic_id": get_node_topic_id(node),
                "last_pos": None,
                "last_target": None,
                "pending_target": None,
                "moving": False,
                "command_ts": None,
                "last_run_status": None,
                "last_published_pos": None,
                "last_update_ts": 0.0,
                "stop_in_progress": False,
            })

            st["node_name"] = getattr(node, "name", "")
            st["node_id"] = getattr(node, "node_id", None)
            st["topic_id"] = get_node_topic_id(node)

            try:
                node.register_device_updated_cb(
                    lambda _n, _node=node: asyncio.create_task(on_node_update(_node))
                )
            except Exception:
                logging.exception(
                    "register_device_updated_cb failed for %s",
                    getattr(node, "name", ""),
                )

            logging.debug(
                "watching node: name=%s node_id=%s topic_id=%s",
                getattr(node, "name", ""),
                getattr(node, "node_id", None),
                get_node_topic_id(node),
            )

        try:
            publish_node_metadata()
        except Exception:
            logging.exception("publish_node_metadata failed during startup")

        try:
            await poll_rain_sensors_once()
        except Exception:
            logging.exception("initial rain poll failed")

        tasks = [
            asyncio.create_task(publish_initial_snapshot()),
            asyncio.create_task(publish_health_task()),
            asyncio.create_task(moving_watchdog()),
            asyncio.create_task(poll_rain_sensors()),
            asyncio.create_task(preventive_recovery_task()),
        ]

        # Hauptloop: nur auf Stop warten
        while not stop_event.is_set():
            await asyncio.sleep(0.5)

        logging.info("shutdown requested")

    except asyncio.CancelledError:
        logging.info("main loop cancelled, exiting")
        SERVICE_STATE = "stopping"
        SERVICE_DETAIL = "cancelled"
        publish_service_status()
        publish_bridge_status()
        clear_external_recovery()

    except Exception:
        logging.exception("Unexpected error in main loop")
        SERVICE_STATE = "stopping"
        SERVICE_DETAIL = "unexpected error"
        publish_service_status()
        publish_bridge_status()
        clear_external_recovery()

    finally:
        for task in tasks:
            task.cancel()
        try:
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception:
            pass

        # pyvlx sauber trennen, aber OHNE Gateway-Reboot
        try:
            if pyvlx is not None:
                conn = getattr(pyvlx, "connection", None)
                if conn is not None:
                    disconnect = getattr(conn, "disconnect", None)
                    if callable(disconnect):
                        result = disconnect(notify_callbacks=False)
                        if asyncio.iscoroutine(result):
                            await result

                pyvlx = None

        except Exception:
            logging.debug("pyvlx connection disconnect during shutdown failed", exc_info=True)

        try:
            KLF_STATE = "stopped"
            SERVICE_STATE = "stopped"
            SERVICE_DETAIL = None
            clear_external_recovery()
            publish_service_status()
            publish_bridge_status()
            await asyncio.sleep(0.2)
        except Exception:
            pass

        try:
            mqttc.loop_stop()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Interrupted by user, exiting")
    except Exception:
        logging.exception("Fatal error in main")

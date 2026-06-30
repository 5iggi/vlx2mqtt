#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vlx2mqtt.py
"""

import configparser
import concurrent.futures
import asyncio
import json
import logging
import os
import re
import signal
import sys
import time
from datetime import datetime, timezone
from logging.handlers import WatchedFileHandler
from typing import Any, Optional

import paho.mqtt.client as mqtt
from pyvlx import OpeningDevice, PyVLX
from pyvlx.exception import PyVLXException

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
        logging.ok("Applied pyvlx payload patch")
    except Exception:
        logging.exception("Failed to apply pyvlx patch")



# ============================================================
# Configuration
# ============================================================
DEFAULT_CFG = {
    "klf_host": "VELUX-KLF.fritz.box",
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
    "event_monitor_interval": 60,
    "event_stale_warn_seconds": 900,
}

LOGFORMAT = "%(asctime)-15s <%(levelname)s> %(message)s"

# LoxBerry Log Manager recognizes tags like <INFO>, <OK>, <WARNING>, <ERROR>.
OK_LEVEL = 25
logging.addLevelName(OK_LEVEL, "OK")

def log_ok(message: str, *args, **kwargs) -> None:
    logging.getLogger().log(OK_LEVEL, message, *args, **kwargs)

setattr(logging, "ok", log_ok)


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
    cfg["event_monitor_interval"] = sec.getint(
        "event_monitor_interval", fallback=cfg["event_monitor_interval"]
    )
    cfg["event_stale_warn_seconds"] = sec.getint(
        "event_stale_warn_seconds", fallback=cfg["event_stale_warn_seconds"]
    )

    return cfg


CFG_PATH = sys.argv[1] if len(sys.argv) > 1 else "/opt/loxberry/config/plugins/vlx2mqtt/vlx2mqtt.cfg"
CFG = load_cfg_file(CFG_PATH)
LOGFILE = CFG["logfile"]

# ============================================================
# Help functions
# ============================================================

def normalize_from_device(raw: Any) -> Optional[int]:
    """Convert raw VELUX values safely to 0..100."""
    try:
        txt = str(raw).replace("%", "").strip()
        if txt.upper() in ("UNKNOWN", "CURRENT", ""):
            return None
        v = int(float(txt))
    except Exception:
        return None

    # Known ghost raw value -> suppress
    if v == 124:
        return None

    # Velux often delivers 0..200
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
    Read target position robustly.
    """
    target = None

    try:
        target_raw = getattr(node.target, "position_percent", None)
        if target_raw is not None:
            raw_upper = str(target_raw).upper().strip()
            if raw_upper != "CURRENT":
                target = normalize_from_device(target_raw)
    except Exception:
        target = None

    if st.get("stop_in_progress", False):
        return target

    if target is None:
        pt = st.get("pending_target")
        if isinstance(pt, int):
            target = pt

    if target is None:
        lt = st.get("last_target")
        if isinstance(lt, int):
            target = lt

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

def parse_state_code(node) -> Optional[int]:
    """
    Read numeric KLF state (e.g. 2/3/4/5) from the node.
    """
    candidates = [
        getattr(node, "last_frame_state", None),
        getattr(node, "state", None),
    ]

    for cand in candidates:
        if cand is None:
            continue

        try:
            if isinstance(cand, (int, float)):
                return int(cand)
        except Exception:
            pass

        try:
            txt = str(cand).strip()
        except Exception:
            continue

        if not txt:
            continue

        if txt.isdigit():
            try:
                return int(txt)
            except Exception:
                pass

        m = re.search(r"(?<!\d)(\d+)(?!\d)", txt)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass

    return None


def parse_remaining_time(node) -> Optional[int]:
    """
    Read remaining_time from the node.
    """
    candidates = [
        getattr(node, "remaining_time", None),
        getattr(node, "last_frame_remaining_time", None),
        getattr(getattr(node, "position", None), "remaining_time", None),
        getattr(getattr(node, "target", None), "remaining_time", None),
    ]

    for cand in candidates:
        if cand is None:
            continue

        try:
            if isinstance(cand, (int, float)):
                v = int(cand)
                if v >= 0:
                    return v
                continue
        except Exception:
            pass

        try:
            txt = str(cand).strip()
        except Exception:
            continue

        if not txt:
            continue

        m = re.search(r"(-?\d+)", txt)
        if not m:
            continue

        try:
            v = int(m.group(1))
            if v >= 0:
                return v
        except Exception:
            continue

    return None


def should_be_moving(st: dict, pos: Optional[int], target: Optional[int], run_status: str, state_str: str) -> bool:
    """
    Robust moving state logic.
    """
    rs = str(run_status or "").upper()
    state_u = str(state_str or "").upper().strip()

    cmd_ts = st.get("command_ts")
    recent_cmd = False
    if cmd_ts:
        recent_cmd = (time.time() - cmd_ts) < 20.0

    if state_u in ("2", "3", "4"):
        return True

    if state_u == "5":
        return False

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

    if st.get("stop_in_progress", False):
        stop_request_pos = st.get("stop_request_pos")

        if pos is not None and target is not None and abs(pos - target) <= 1:
            return False

        if (
            stop_request_pos is not None
            and pos is not None
            and pos != stop_request_pos
        ):
            return False

        if completed:
            return False

        return True

    if active:
        return True

    if pos is not None and target is not None:
        if abs(pos - target) <= 1:
            return False
        return True

    if completed:
        return False

    if recent_cmd and target is not None and pos is not None and abs(pos - target) > 1:
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
    Identifier: node.name / node.node_id
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
    Check whether a received identifier matches this node.
    """
    ident = str(identifier).strip()
    mode = get_topic_identifier_mode()

    if mode == "node_id":
        node_id = getattr(node, "node_id", None)
        return node_id is not None and ident == str(node_id)

    name = getattr(node, "name", None)
    if name and ident == sanitize_topic_part(name):
        return True

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
    Determine rain status indirectly via the opening limit.
    """
    node_name = getattr(node, "name", "")

    async def _read_once() -> tuple[Optional[bool], Optional[int]]:
        limitation = None
        raw = None

        if hasattr(node, "get_limitation_min"):
            limitation = await node.get_limitation_min()
            logging.debug(
                "read_rain_state: get_limitation_min() for %s -> %r",
                node_name,
                limitation,
            )
            if limitation is not None:
                raw = getattr(limitation, "position_percent", None)
                if raw is None:
                    raw = getattr(limitation, "min_value", None)

        elif hasattr(node, "get_limitation"):
            limitation = await node.get_limitation()
            logging.debug(
                "read_rain_state: get_limitation() for %s -> %r",
                node_name,
                limitation,
            )
            if limitation is not None:
                raw = getattr(limitation, "min_value", None)
                if raw is None:
                    raw = getattr(limitation, "position_percent", None)
        else:
            logging.debug(
                "read_rain_state: node %s supports neither get_limitation_min nor get_limitation",
                node_name,
            )
            return None, None

        logging.debug(
            "read_rain_state: raw limitation for %s -> %r",
            node_name,
            raw,
        )

        if raw is None:
            return None, None

        raw_int = normalize_from_device(raw)
        if raw_int is None:
            return None, None

        return (raw_int >= 89), raw_int

    # Short retry for transient KLF / pyvlx send problems
    retry_delays = (0.0, 0.6)
    last_exc: Optional[Exception] = None

    for attempt, delay in enumerate(retry_delays, start=1):
        try:
            if delay > 0:
                await asyncio.sleep(delay)
            return await _read_once()
        except PyVLXException as exc:
            last_exc = exc
            if "Unable to send command" in str(exc):
                if attempt < len(retry_delays):
                    logging.warning(
                        "read_rain_state transient send failure for %s (attempt %s/%s) - retrying",
                        node_name,
                        attempt,
                        len(retry_delays),
                    )
                    continue
                logging.warning(
                    "read_rain_state failed for %s after retry: %s",
                    node_name,
                    exc,
                )
                return None, None
            logging.exception("read_rain_state failed for %s", node_name)
            return None, None
        except Exception as exc:
            last_exc = exc
            logging.exception("read_rain_state failed for %s", node_name)
            return None, None

    if last_exc is not None:
        logging.warning("read_rain_state failed for %s: %s", node_name, last_exc)
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

    # Tie third-party loggers to the local verbose setting
    for logger_name in ("pyvlx", "asyncio"):
        lib_logger = logging.getLogger(logger_name)
        lib_logger.setLevel(loglevel)

        # Remove handlers attached by libraries
        for h in list(lib_logger.handlers):
            try:
                h.flush()
                h.close()
            except Exception:
                pass
            lib_logger.removeHandler(h)

        lib_logger.propagate = True

    logging.info("Using config file: %s", CFG_PATH)
    logging.info("Verbose logging: %s", "on" if CFG.get("verbose", False) else "off")
    logging.info(
        "External recovery config: enabled=%s threshold=%s cooldown=%.0fs grace=%.0fs topic=%s trigger_states=%s",
        _cfg_bool(CFG.get("external_recovery_enabled", False), False),
        CFG.get("external_recovery_threshold"),
        float(CFG.get("external_recovery_cooldown", 0)),
        float(CFG.get("external_recovery_grace", 0)),
        CFG.get("external_recovery_topic"),
        ("klf_connection_refused", "klf_disconnected", "klf_unreachable"),
    )


setup_logging()
apply_pyvlx_patch()
logging.info("Starting vlx2mqtt_rebuild")

# ============================================================
# Global runtime data
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
# Recovery trigger states: count repeated KLF API failures that may be fixed by a power cycle.
# Kept as KLF_REFUSED_COUNT for MQTT/backward compatibility.
KLF_RECOVERY_TRIGGER_STATES = (
    "klf_connection_refused",
    "klf_disconnected",
    "klf_unreachable",
)
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
            if retain:
                PUBLISH_QUEUE = [item for item in PUBLISH_QUEUE if item[0] != topic]

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
    Assign a clear status to KLF connection/authentication errors.
        (klf_state, klf_error_text)
    """
    txt = ""

    try:
        desc = getattr(exc, "description", None)
        if desc:
            txt = str(desc).strip()
    except Exception:
        pass

    if not txt:
        try:
            txt = str(exc).strip()
        except Exception:
            txt = ""

    if not txt:
        try:
            txt = repr(exc).strip()
        except Exception:
            txt = ""

    if not txt:
        txt = "unknown klf error"

    txt_u = txt.upper()

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

    if (
        "ERRNO 111" in txt_u
        or "CONNECTION REFUSED" in txt_u
        or "CONNECT CALL FAILED" in txt_u
    ):
        return "klf_connection_refused", txt

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
    """Published only when a value changes."""
    global LAST_PUBLISHED
    payload_str = "" if payload is None else str(payload)
    if LAST_PUBLISHED.get(topic) == payload_str:
        return
    LAST_PUBLISHED[topic] = payload_str
    mqtt_publish(topic, payload_str, qos=qos, retain=retain)


def compute_status_detail() -> str:
    """Stable Detail Status for Loxone / Diagnostics."""
    if SERVICE_STATE != "running":
        return f"service_{SERVICE_STATE}"
    return KLF_STATE


def compute_overall_status() -> str:
    """
    Simple Loxone status: ok / error
    """
    if SERVICE_STATE == "stopped":
        return "ok"

    if SERVICE_STATE == "running" and KLF_STATE == "klf_connected":
        return "ok"

    return "error"


def submit_coro_from_thread(coro, description: str = ""):
    """
    Schedules a coroutine thread-safely on the main asyncio loop.
    """
    global MAIN_LOOP

    if MAIN_LOOP is None or MAIN_LOOP.is_closed():
        logging.error(
            "submit_coro_from_thread: no running MAIN_LOOP for %s",
            description or coro,
        )
        try:
            coro.close()
        except Exception:
            pass
        return None

    future = asyncio.run_coroutine_threadsafe(coro, MAIN_LOOP)

    def _parse_description(desc: str):
        """
        Parses descriptions like:
          open:Window_left; close:Window_right;
          stop:Window_left; finalize_stop:Window_left
        into (cmd, label).
        """
        txt = str(desc or "").strip()
        if ":" not in txt:
            return txt.upper(), ""

        cmd, label = txt.split(":", 1)
        return cmd.strip().upper(), label.strip()

    def _compact_error_from_description(desc: str) -> str:
        """
        Converts internal descriptions into concise log texts for `verbose=0`.
        """
        cmd, label = _parse_description(desc)

        if cmd == "OPEN":
            return f"{label} command failed: OPEN"
        if cmd == "CLOSE":
            return f"{label} command failed: CLOSE"
        if cmd == "STOP":
            return f"{label} command failed: STOP"
        if cmd == "FINALIZE_STOP":
            return f"{label} STOP finalizer failed"

        return f"Coroutine failed: {desc or coro}"

    def _compact_success_from_description(desc: str) -> Optional[str]:
        """
        Returns a compact success message for simple operation logs.
        """
        cmd, label = _parse_description(desc)

        if cmd == "OPEN":
            return f"{label} command ok: OPEN"
        if cmd == "CLOSE":
            return f"{label} command ok: CLOSE"
        if cmd == "STOP":
            return f"{label} command ok: STOP"

        return None

    def _done_callback(fut):
        try:
            fut.result()

            if not CFG.get("verbose", False):
                success_msg = _compact_success_from_description(description)
                if success_msg:
                    logging.info(success_msg)

        except (asyncio.CancelledError, concurrent.futures.CancelledError):
            return

        except Exception:
            if CFG.get("verbose", False):
                logging.exception("Coroutine failed: %s", description or coro)
            else:
                logging.error(_compact_error_from_description(description))

    future.add_done_callback(_done_callback)
    return future


def publish_service_status():
    """Publish Python service state."""
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
    Published:
      - status         -> ok / error (for Loxone)
      - status_detail  -> stable detailed status
      - status_live    -> current KLF live status (including klf_connecting)
      - error_text     -> last readable error message
      - health         -> detailed JSON
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
    Publishes the status for an external recovery (e.g., Loxone + smart plug).
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



# ============================================================
# Numeric status codes for Loxone / MQTT gateways
# ============================================================
# Existing readable text topics are kept. The additional *_code topics are
# intended for Loxone Config and other consumers that prefer numeric values.

STATUS_CODE_MAP = {
    "ok": 1,
    "error": 0,
}

KLF_STATUS_CODE_MAP = {
    "klf_connected": 1,
    "klf_connecting": 2,
    "klf_disconnected": 3,
    "klf_unreachable": 4,
    "klf_connection_refused": 5,
    "klf_auth_failed": 6,
    "klf_error": 7,
    "starting": 8,
    "unknown": 99,
}

SERVICE_STATUS_CODE_MAP = {
    "running": 1,
    "starting": 2,
    "stopped": 0,
    "lost": 0,
    "error": 0,
    "unknown": 99,
    "service_running": 1,
    "service_starting": 2,
    "service_stopped": 0,
    "service_lost": 0,
    "service_error": 0,
}

RECOVERY_STATUS_CODE_MAP = {
    "idle": 0,
    "requested": 1,
    "waiting": 2,
}

RECOVERY_REASON_CODE_MAP = {
    "": 0,
    "none": 0,
    "klf_connected": 1,
    "klf_connecting": 2,
    "klf_disconnected": 3,
    "klf_unreachable": 4,
    "klf_connection_refused": 5,
    "klf_auth_failed": 6,
    "klf_error": 7,
    "preventive_recovery": 10,
    "unknown": 99,
}


def state_code(value: Any, mapping: dict, default: int = 99) -> int:
    key = str(value or "").strip().lower()
    return int(mapping.get(key, default))


def mqtt_publish_state_with_code(topic: str, value: Any, mapping: dict, default: int = 99):
    mqtt_publish_if_changed(topic, value, qos=1, retain=True)
    mqtt_publish_if_changed(f"{topic}_code", state_code(value, mapping, default), qos=1, retain=True)


# Override the original publisher functions with code-aware versions.
def publish_service_status():
    """Publish Python service state including numeric code topic."""
    try:
        mqtt_publish_state_with_code(
            f"{CFG['root_topic']}/service_status",
            SERVICE_STATE,
            SERVICE_STATUS_CODE_MAP,
            default=99,
        )
        mqtt_publish_if_changed(
            f"{CFG['root_topic']}/service_detail",
            "" if SERVICE_DETAIL is None else str(SERVICE_DETAIL),
            qos=1,
            retain=True,
        )
    except Exception:
        logging.exception("publish_service_status failed")


def publish_bridge_status():
    """Publish bridge status including numeric *_code topics."""
    try:
        overall_status = compute_overall_status()
        detail_status = compute_status_detail()
        live_status = KLF_STATE
        detail_map = {**KLF_STATUS_CODE_MAP, **SERVICE_STATUS_CODE_MAP}

        mqtt_publish_state_with_code(
            f"{CFG['root_topic']}/status",
            overall_status,
            STATUS_CODE_MAP,
            default=0,
        )
        mqtt_publish_state_with_code(
            f"{CFG['root_topic']}/status_detail",
            detail_status,
            detail_map,
            default=99,
        )
        mqtt_publish_state_with_code(
            f"{CFG['root_topic']}/status_live",
            live_status,
            KLF_STATUS_CODE_MAP,
            default=99,
        )

        error_text = ""
        if LAST_KLF_ERROR:
            error_text = str(LAST_KLF_ERROR)
        elif SERVICE_DETAIL:
            error_text = str(SERVICE_DETAIL)
        mqtt_publish_if_changed(
            f"{CFG['root_topic']}/error_text",
            error_text,
            qos=1,
            retain=True,
        )

        health = {
            "status": overall_status,
            "status_code": state_code(overall_status, STATUS_CODE_MAP, 0),
            "status_detail": detail_status,
            "status_detail_code": state_code(detail_status, detail_map, 99),
            "status_live": live_status,
            "status_live_code": state_code(live_status, KLF_STATUS_CODE_MAP, 99),
            "service_state": SERVICE_STATE,
            "service_status_code": state_code(SERVICE_STATE, SERVICE_STATUS_CODE_MAP, 99),
            "service_detail": SERVICE_DETAIL,
            "klf_state": KLF_STATE,
            "last_klf_error": LAST_KLF_ERROR,
            "last_klf_ok_ts": LAST_KLF_OK_TS,
            "klf_reconnect_in": KLF_RECONNECT_IN,
            "recovery_requested": RECOVERY_REQUESTED,
            "recovery_reason": RECOVERY_REASON,
            "recovery_reason_code": state_code(RECOVERY_REASON, RECOVERY_REASON_CODE_MAP, 0),
            "failure_count": KLF_REFUSED_COUNT,
        }
        mqtt_publish_if_changed(
            f"{CFG['root_topic']}/health",
            json.dumps(health, sort_keys=True, default=str),
            qos=1,
            retain=True,
        )
    except Exception:
        logging.exception("publish_bridge_status failed")


def publish_recovery_status():
    """Publish external recovery state including numeric code topics."""
    try:
        recovery_reason = "" if RECOVERY_REASON is None else str(RECOVERY_REASON)
        recovery_state = "requested" if RECOVERY_REQUESTED else "idle"

        mqtt_publish_if_changed(
            CFG["external_recovery_topic"],
            "true" if RECOVERY_REQUESTED else "false",
            qos=1,
            retain=True,
        )
        mqtt_publish_state_with_code(
            f"{CFG['root_topic']}/recovery/reason",
            recovery_reason,
            RECOVERY_REASON_CODE_MAP,
            default=99,
        )
        mqtt_publish_if_changed(
            f"{CFG['root_topic']}/recovery/failure_count",
            KLF_REFUSED_COUNT,
            qos=1,
            retain=True,
        )
        mqtt_publish_state_with_code(
            f"{CFG['root_topic']}/recovery/state",
            recovery_state,
            RECOVERY_STATUS_CODE_MAP,
            default=99,
        )
    except Exception:
        logging.exception("publish_recovery_status failed")


def publish_node_metadata():
    """
    Publishes the name <-> node_id mapping as retained topics for debugging.
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
    Requests an external recovery (typically: Loxone turns the smart plug off/on).
    """
    global RECOVERY_REQUESTED, RECOVERY_REASON, LAST_EXTERNAL_RECOVERY_TS, WAIT_UNTIL_AFTER_RECOVERY, SERVICE_DETAIL

    now = time.time()
    RECOVERY_REQUESTED = True
    RECOVERY_REASON = reason
    LAST_EXTERNAL_RECOVERY_TS = now
    WAIT_UNTIL_AFTER_RECOVERY = now + float(CFG["external_recovery_grace"])

    SERVICE_DETAIL = f"external recovery requested: {reason}"
    logging.warning(
        "External recovery requested: topic=%s payload=true reason=%s grace=%.0fs mqtt_connected=%s",
        CFG["external_recovery_topic"],
        reason,
        float(CFG["external_recovery_grace"]),
        mqtt_connected,
    )
    publish_service_status()
    publish_bridge_status()
    publish_recovery_status()


def clear_external_recovery():
    """
    Resets the external recovery status.
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
        logging.ok("MQTT connected rc=%s", rc)
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

    logging.info("MQTT set received topic=%s payload=%s", topic, payload)
    
    rel = topic[len(root) + 1:]
    parts = rel.split("/")

    if len(parts) < 2 or parts[-1] != "set":
        logging.warning("Ignoring unsupported command topic: %s", topic)
        return

    identifier = "/".join(parts[:-1]).strip()
    node = find_node_by_identifier(identifier)
    if node is None:
        logging.warning(
            "No matching node found for topic identifier '%s' (topic=%s)",
            identifier,
            topic,
        )
        return

    stkey = get_node_state_key(node)
    st = NODE_STATE.setdefault(stkey, {})
    st["node_name"] = getattr(node, "name", "")
    st["node_id"] = getattr(node, "node_id", None)
    st["topic_id"] = get_node_topic_id(node)

    node_label = st.get("topic_id") or getattr(node, "name", "") or stkey
    value_u = payload.strip().upper()

    try:
        if value_u in ("UP", "OPEN"):
            st["command_ts"] = time.time()
            st["pending_target"] = 0
            st["stop_in_progress"] = False

            old_task = st.get("stop_finalize_task")
            if old_task:
                try:
                    old_task.cancel()
                except Exception:
                    pass
            st["stop_finalize_task"] = None
            st["stop_request_pos"] = None
            st["stop_position_changed"] = False

            if not st.get("moving", False):
                st["moving"] = True
                mqtt_publish_if_changed(
                    build_node_topic(node, "moving"),
                    "true",
                )

                if not CFG.get("verbose", False):
                    logging.info(
                        "%s moving: True (requested target=0)",
                        node_label,
                    )

            submit_coro_from_thread(
                node.open(wait_for_completion=False),
                description=f"open:{st.get('topic_id') or getattr(node, 'name', '')}",
            )

        elif value_u in ("DOWN", "CLOSE"):
            st["command_ts"] = time.time()
            st["pending_target"] = 100
            st["stop_in_progress"] = False

            old_task = st.get("stop_finalize_task")
            if old_task:
                try:
                    old_task.cancel()
                except Exception:
                    pass
            st["stop_finalize_task"] = None
            st["stop_request_pos"] = None
            st["stop_position_changed"] = False

            if not st.get("moving", False):
                st["moving"] = True
                mqtt_publish_if_changed(
                    build_node_topic(node, "moving"),
                    "true",
                )

                if not CFG.get("verbose", False):
                    logging.info(
                        "%s moving: True (requested target=100)",
                        node_label,
                    )

            submit_coro_from_thread(
                node.close(wait_for_completion=False),
                description=f"close:{st.get('topic_id') or getattr(node, 'name', '')}",
            )

        elif value_u == "STOP":
            st["command_ts"] = time.time()
            st["stop_in_progress"] = True
            st["pending_target"] = None
            st["stop_request_pos"] = st.get("last_pos")
            st["stop_position_changed"] = False

            # Cancel any previous STOP finalizer
            old_task = st.get("stop_finalize_task")
            if old_task:
                try:
                    old_task.cancel()
                except Exception:
                    pass

            if not st.get("moving", False):
                st["moving"] = True
                mqtt_publish_if_changed(
                    build_node_topic(node, "moving"),
                    "true",
                )

            submit_coro_from_thread(
                node.stop(),
                description=f"stop:{st.get('topic_id') or getattr(node, 'name', '')}",
            )

            # Robust STOP finalizer
            st["stop_finalize_task"] = submit_coro_from_thread(
                finalize_stop_after_delay(node, stkey),
                description=f"finalize_stop:{st.get('topic_id') or getattr(node, 'name', '')}",
            )

        else:
            try:
                pos = int(float(payload))
            except Exception:
                logging.warning(
                    "Unsupported command payload '%s' for topic %s",
                    payload,
                    topic,
                )
                return

            st["command_ts"] = time.time()
            st["pending_target"] = pos
            st["stop_in_progress"] = False

            if not st.get("moving", False):
                st["moving"] = True
                mqtt_publish_if_changed(
                    build_node_topic(node, "moving"),
                    "true",
                )

                if not CFG.get("verbose", False):
                    logging.info(
                        "%s moving: True (requested target=%s)",
                        node_label,
                        pos,
                    )

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
# KLF / pyvlx cleanup helpers
# ============================================================

async def _await_if_needed(result, timeout: float = 3.0):
    if hasattr(result, "__await__"):
        return await asyncio.wait_for(result, timeout=timeout)
    return result


async def _call_optional_method(obj, method_name: str, *args, timeout: float = 3.0, **kwargs):
    if obj is None:
        return False
    method = getattr(obj, method_name, None)
    if not callable(method):
        return False
    try:
        try:
            result = method(*args, **kwargs)
        except TypeError:
            result = method()
        await _await_if_needed(result, timeout=timeout)
        return True
    except Exception:
        logging.debug("pyvlx cleanup: %s.%s failed", type(obj).__name__, method_name, exc_info=True)
        return False


async def cancel_pyvlx_heartbeat_tasks(reason: str = "") -> None:
    current = asyncio.current_task()
    tasks_to_cancel = []
    for task in asyncio.all_tasks():
        if task is current or task.done():
            continue
        try:
            coro = task.get_coro()
            qualname = getattr(coro, "__qualname__", "") or getattr(getattr(coro, "cr_code", None), "co_qualname", "")
        except Exception:
            qualname = ""
        if "Heartbeat.loop" in str(qualname):
            tasks_to_cancel.append(task)
    if tasks_to_cancel:
        logging.debug(
            "pyvlx cleanup: cancelling %d heartbeat task(s)%s",
            len(tasks_to_cancel),
            f" ({reason})" if reason else "",
        )
        for task in tasks_to_cancel:
            task.cancel()
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)


async def cleanup_pyvlx_instance(instance, reason: str = "") -> None:
    """Best-effort cleanup after failed KLF connect without active API calls."""
    if instance is None:
        await cancel_pyvlx_heartbeat_tasks(reason)
        return
    logging.debug("pyvlx cleanup: start%s", f" ({reason})" if reason else "")
    conn = getattr(instance, "connection", None)

    # Important: do not call PyVLX.disconnect() here, because it may try to send
    # GW_HOUSE_STATUS_MONITOR_DISABLE_REQ and can create another hanging connect.
    await _call_optional_method(conn, "disconnect", notify_callbacks=False)
    await _call_optional_method(conn, "close")

    try:
        transport = getattr(conn, "transport", None)
        if transport is not None and callable(getattr(transport, "close", None)):
            transport.close()
    except Exception:
        logging.debug("pyvlx cleanup: transport close failed", exc_info=True)

    await cancel_pyvlx_heartbeat_tasks(reason)
    await asyncio.sleep(0)
    logging.debug("pyvlx cleanup: done%s", f" ({reason})" if reason else "")


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

            logging.ok("pyvlx: nodes loaded %d", len(pyvlx.nodes))
            publish_service_status()
            publish_bridge_status()
            KLF_REFUSED_COUNT = 0
            clear_external_recovery()
            return True

        except Exception as e:
            failed_pyvlx = pyvlx
            pyvlx = None
            await cleanup_pyvlx_instance(failed_pyvlx, "connect failed")

            klf_state, err_text = classify_klf_error(e)
            KLF_STATE = klf_state
            LAST_KLF_ERROR = err_text
            
            if klf_state in KLF_RECOVERY_TRIGGER_STATES:
                KLF_REFUSED_COUNT += 1
            else:
                KLF_REFUSED_COUNT = 0

            publish_recovery_status()

            recovery_enabled = _cfg_bool(CFG.get("external_recovery_enabled", False), False)
            recovery_threshold = int(CFG["external_recovery_threshold"])

            if klf_state in KLF_RECOVERY_TRIGGER_STATES and KLF_REFUSED_COUNT >= recovery_threshold:
                cooldown_ok = (
                    LAST_EXTERNAL_RECOVERY_TS is None
                    or (time.time() - LAST_EXTERNAL_RECOVERY_TS) >= float(CFG["external_recovery_cooldown"])
                )
                if not recovery_enabled:
                    if KLF_REFUSED_COUNT == recovery_threshold:
                        logging.warning(
                            "Recovery threshold reached but external recovery is disabled: count=%d threshold=%d last=%s topic=%s",
                            KLF_REFUSED_COUNT,
                            recovery_threshold,
                            klf_state,
                            CFG["external_recovery_topic"],
                        )
                elif not cooldown_ok:
                    if CFG.get("verbose", False):
                        logging.debug(
                            "External recovery threshold reached but cooldown is active: count=%d threshold=%d last=%s cooldown=%.0fs",
                            KLF_REFUSED_COUNT,
                            recovery_threshold,
                            klf_state,
                            float(CFG["external_recovery_cooldown"]),
                        )
                elif RECOVERY_REQUESTED:
                    if CFG.get("verbose", False):
                        logging.debug(
                            "External recovery already requested: count=%d threshold=%d last=%s reason=%s",
                            KLF_REFUSED_COUNT,
                            recovery_threshold,
                            klf_state,
                            RECOVERY_REASON,
                        )
                else:
                    logging.warning(
                        "Requesting external recovery after %d KLF connection failures (last=%s)",
                        KLF_REFUSED_COUNT,
                        klf_state,
                    )
                    request_external_recovery(klf_state)

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
    """Poll rain status once."""
    logging.debug("poll_rain_sensors_once: start")

    now = time.time()

    for node in getattr(pyvlx, "nodes", []):
        if not isinstance(node, OpeningDevice):
            continue

        # Only poll nodes that can actually provide limitation/rain info
        if not (hasattr(node, "get_limitation_min") or hasattr(node, "get_limitation")):
            continue

        node_name = getattr(node, "name", "")
        node_id = getattr(node, "node_id", None)
        stkey = get_node_state_key(node)
        st = NODE_STATE.setdefault(stkey, {})
        st["node_name"] = node_name
        st["node_id"] = node_id
        st["topic_id"] = get_node_topic_id(node)

        # Option 2: do not poll rain while the node is moving or very shortly after a command.
        if st.get("moving", False):
            logging.debug(
                "poll_rain_sensors_once: skip rain poll for %s (moving=true)",
                node_name,
            )
            continue

        cmd_ts = st.get("command_ts")
        if cmd_ts and (now - cmd_ts) < 30.0:
            logging.debug(
                "poll_rain_sensors_once: skip rain poll for %s (recent command %.1fs ago)",
                node_name,
                now - cmd_ts,
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

        topic_id = st.get("topic_id") or node_name or stkey
        prev_rain = st.get("last_published_rain")
        prev_raw = st.get("last_published_rain_raw_limit")
        changed = (prev_rain != rain) or (raw_limit is not None and prev_raw != raw_limit)

        mqtt_publish_if_changed(
            build_node_topic(node, "rain"),
            "true" if rain else "false",
            qos=1,
            retain=True,
        )
        st["last_published_rain"] = rain

        if _cfg_bool(CFG.get("publish_rain_raw_limit", False), False) and raw_limit is not None:
            mqtt_publish_if_changed(
                build_node_topic(node, "rain_raw_limit"),
                raw_limit,
                qos=1,
                retain=True,
            )
        if raw_limit is not None:
            st["last_published_rain_raw_limit"] = raw_limit

        if changed and not CFG.get("verbose", False):
            if raw_limit is None:
                logging.info("%s rain: %s", topic_id, "true" if rain else "false")
            else:
                logging.info(
                    "%s rain: %s (raw_limit=%s)",
                    topic_id,
                    "true" if rain else "false",
                    raw_limit,
                )

async def poll_rain_sensors():
    """
    Poll indirect rain status only for window nodes with a rain sensor.
    """
    interval = max(60, int(float(CFG.get("rain_poll_interval", 300))))

    while True:
        try:
            await poll_rain_sensors_once()
        except Exception:
            logging.exception("poll_rain_sensors failed")

        await asyncio.sleep(interval)


# ============================================================
# Background tasks
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

            if not CFG.get("verbose", False):
                topic_id = st.get("topic_id") or getattr(node, "name", "") or stkey
                if pos is not None:
                    logging.info("startup %s position: %s", topic_id, pos)
                logging.info(
                    "startup %s moving: %s",
                    topic_id,
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
                    st["stop_in_progress"] = False
                    st["stop_request_pos"] = None
                    st["stop_position_changed"] = False
                    st["command_ts"] = None

                    node_label = st.get("topic_id") or st.get("node_name") or stkey

                    mqtt_publish_if_changed(
                        f"{CFG['root_topic']}/{node_label}/moving",
                        "false",
                    )

                    logging.warning(
                        "watchdog: %s forced to moving=false after timeout",
                        node_label,
                    )

        except Exception:
            logging.exception("moving_watchdog error")

        await asyncio.sleep(1.0)


async def finalize_stop_after_delay(node, stkey: str, delay: float = 1.5, confirm_gap: float = 0.5):
    """
    Robust STOP Finalizer
    """
    try:
        await asyncio.sleep(delay)

        st = NODE_STATE.setdefault(stkey, {})
        if not st.get("stop_in_progress", False):
            return

        pos1 = parse_position(node)

        await asyncio.sleep(confirm_gap)

        st = NODE_STATE.setdefault(stkey, {})
        if not st.get("stop_in_progress", False):
            return

        pos2 = parse_position(node)

        final_pos = pos2 if pos2 is not None else pos1
        stop_request_pos = st.get("stop_request_pos")

        stable = (pos1 is not None and pos2 is not None and pos1 == pos2)
        changed_since_stop = (
            stop_request_pos is not None
            and final_pos is not None
            and final_pos != stop_request_pos
        )

        if stable or changed_since_stop:
            prev_moving = bool(st.get("moving", False))

            if final_pos is not None:
                last_pub = st.get("last_published_pos")
                if final_pos != last_pub:
                    st["last_published_pos"] = final_pos
                    st["last_pos"] = final_pos
                    st["last_target"] = final_pos
                    mqtt_publish_if_changed(
                        build_node_topic(node, "position"),
                        final_pos,
                    )

            st["moving"] = False
            st["stop_in_progress"] = False
            st["pending_target"] = None
            st["stop_request_pos"] = None
            st["stop_position_changed"] = False

            if prev_moving:
                mqtt_publish_if_changed(
                    build_node_topic(node, "moving"),
                    "false",
                )
                logging.info(
                    "%s moving: False (STOP finalizer pos=%s stable=%s changed_since_stop=%s)",
                    st.get("topic_id") or st.get("node_name") or stkey,
                    final_pos,
                    stable,
                    changed_since_stop,
                )

    except asyncio.CancelledError:
        return
    except Exception:
        logging.exception("finalize_stop_after_delay failed")


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
        remaining_time = parse_remaining_time(node)

        node_label = st.get("topic_id") or st.get("node_name") or stkey

        # Publish position only on change
        position_changed = False

        if pos is not None:
            last_pub = st.get("last_published_pos")
            if pos != last_pub:
                position_changed = True
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

        # Check StatusReply (e.g., STOP / OVERRULED)
        is_overruled = False
        last_reply_str = ""

        try:
            last_reply = getattr(node, "last_frame_status_reply", None)
            last_reply_str = str(last_reply).upper() if last_reply is not None else ""
            is_overruled = "OVERRULED" in last_reply_str
        except Exception:
            last_reply_str = ""
            is_overruled = False

        prev_moving = bool(st.get("moving", False))

        if not st.get("stop_in_progress", False):
            old_task = st.get("stop_finalize_task")
            if old_task:
                try:
                    old_task.cancel()
                except Exception:
                    pass
                st["stop_finalize_task"] = None

        # Base decision
        if st.get("stop_in_progress", False) and is_overruled:
            moving = True
        else:
            moving = should_be_moving(
                st,
                pos,
                target,
                run_status,
                state_str,
            )

        rs_upper = str(run_status or "").upper()
        state_u = str(state_str or "").upper().strip()

        reached_target = (
            pos is not None and target is not None and abs(pos - target) <= 1
        )

        explicit_done = (
            state_u == "5"
            or "DONE" in state_u
            or "COMPLETED" in rs_upper
            or "COMMAND_COMPLETED_OK" in rs_upper
        )

        cmd_ts = st.get("command_ts")
        recent_cmd = False
        if cmd_ts:
            recent_cmd = (time.time() - cmd_ts) < 20.0

        no_active_run = not any(k in rs_upper for k in (
            "EXECUTION_ACTIVE",
            "EXECUTING",
            "RUNNING",
            "IN_PROGRESS",
            "ACTIVE",
        ))

        stable_or_idle = (
            remaining_time in (None, 0)
            or str(remaining_time).strip() in ("", "0")
        )

        stale_target = (
            pos is not None
            and target is not None
            and abs(pos - target) > 1
        )

        # External / manual position adjustment
        external_manual_final = (
            stale_target
            and not recent_cmd
            and no_active_run
            and stable_or_idle
            and (
                position_changed
                or explicit_done
                or state_u == "5"
            )
        )

        stop_request_pos = st.get("stop_request_pos")

        # A changed stable position after STOP means STOP completed
        if (
            st.get("stop_in_progress", False)
            and stop_request_pos is not None
            and pos is not None
            and pos != stop_request_pos
        ):
            st["stop_position_changed"] = True

        stop_finished = (
            st.get("stop_in_progress", False)
            and (
                reached_target
                or explicit_done
                or st.get("stop_position_changed", False)
            )
        )

        if stop_finished:
            st["moving"] = False
            st["stop_in_progress"] = False
            st["pending_target"] = None
            st["stop_request_pos"] = None
            st["stop_position_changed"] = False
            if pos is not None:
                st["last_target"] = pos
            moving = False

        elif external_manual_final:
            st["moving"] = False
            st["pending_target"] = None
            st["stop_in_progress"] = False
            st["stop_request_pos"] = None
            st["stop_position_changed"] = False
            st["command_ts"] = None

            if pos is not None:
                st["last_target"] = pos

            moving = False

            if (
                not CFG.get("verbose", False)
                and pos is not None
                and target is not None
                and abs(pos - target) > 1
            ):
                logging.info(
                    "%s manual position adopted: pos=%s old_target=%s",
                    node_label,
                    pos,
                    target,
                )


        elif reached_target or explicit_done:
            st["moving"] = False
            st["pending_target"] = None
            st["stop_in_progress"] = False
            st["stop_request_pos"] = None
            st["stop_position_changed"] = False
            if pos is not None:
                st["last_target"] = pos
            moving = False

        else:
            st["moving"] = moving

# Publish moving only on change
        if prev_moving != st["moving"]:
            mqtt_publish_if_changed(
                build_node_topic(node, "moving"),
                "true" if st["moving"] else "false",
            )
            if CFG.get("verbose", False):
                logging.info(
                    "%s moving: %s (state=%s run_status=%s target=%s pos=%s pending_target=%s stop_in_progress=%s stop_request_pos=%s stop_position_changed=%s)",
                    node_label,
                    st["moving"],
                    state_str,
                    run_status,
                    target,
                    pos,
                    st.get("pending_target"),
                    st.get("stop_in_progress"),
                    st.get("stop_request_pos"),
                    st.get("stop_position_changed"),
                )
            else:
                if target is not None:
                    logging.info(
                        "%s moving: %s (pos=%s target=%s)",
                        node_label,
                        st["moving"],
                        pos,
                        target,
                    )
                else:
                    logging.info(
                        "%s moving: %s (pos=%s)",
                        node_label,
                        st["moving"],
                        pos,
                    )

        if (
            not CFG.get("verbose", False)
            and position_changed
            and pos is not None
            and (stop_finished or reached_target or explicit_done or not st["moving"])
        ):
            if target is not None:
                logging.info("%s position: %s (target=%s)", node_label, pos, target)
            else:
                logging.info("%s position: %s", node_label, pos)

    except Exception:
        logging.exception("on_node_update")



# ============================================================
# Commands
# ============================================================
async def safe_set_position(device, value: int, name: str, st: dict):
    node_label = st.get("topic_id") or name

    v = scale_to_device(value)
    if v is None:
        logging.warning("safe_set_position: invalid value for %s: %s", node_label, value)
        mqtt_publish(
            f"{CFG['root_topic']}/{name}/set/ack",
            f"ERROR:INVALID:{value}",
            qos=1,
            retain=False,
        )
        return False

    try:
        await device.set_position(v, wait_for_completion=False)

        if CFG.get("verbose", False):
            logging.debug(
                "safe_set_position ok for %s: requested=%s device=%s",
                node_label,
                value,
                v,
            )
        else:
            logging.info("%s command ok: set_position %s", node_label, value)

        return True

    except Exception:
        if CFG.get("verbose", False):
            logging.exception("safe_set_position failed for %s", node_label)
        else:
            logging.error("%s command failed: set_position %s", node_label, value)

    # Fallback for boundary values
    try:
        if value == 0:
            await device.open(wait_for_completion=False)
            if not CFG.get("verbose", False):
                logging.info("%s command ok: OPEN", node_label)
            return True

        if value == 100:
            await device.close(wait_for_completion=False)
            if not CFG.get("verbose", False):
                logging.info("%s command ok: CLOSE", node_label)
            return True

    except Exception:
        if CFG.get("verbose", False):
            logging.exception("safe_set_position fallback failed for %s", node_label)
        else:
            if value == 0:
                logging.error("%s command failed: OPEN", node_label)
            elif value == 100:
                logging.error("%s command failed: CLOSE", node_label)
            else:
                logging.error("%s command failed: fallback for %s", node_label, value)

    mqtt_publish(
        f"{CFG['root_topic']}/{name}/set/ack",
        f"ERROR:{value}",
        qos=1,
        retain=False,
    )
    return False


def _latest_node_update_age() -> Optional[float]:
    """
    Age in seconds of the newest node update we have seen from the KLF.
    Returns None if no node update has been observed yet.
    """
    latest = None
    now = time.time()

    for st in NODE_STATE.values():
        ts = st.get("last_update_ts")
        if not ts:
            continue
        latest = ts if latest is None else max(latest, ts)

    if latest is None:
        return None
    return max(0.0, now - latest)


async def event_stale_monitor_task():
    """
    Diagnostic-only monitor for the event-driven KLF update path.

    This does NOT poll node positions. It only warns if we have not received any
    node update event for a long time while the bridge is otherwise connected.
    Useful to detect a KLF that is connected but stopped delivering updates.
    """
    interval = max(30, int(float(CFG.get("event_monitor_interval", 60))))
    threshold = max(interval * 2, int(float(CFG.get("event_stale_warn_seconds", 900))))
    warned = False

    while True:
        try:
            await asyncio.sleep(interval)

            if KLF_STATE != "klf_connected":
                warned = False
                continue

            if any_node_moving():
                warned = False
                continue

            age = _latest_node_update_age()
            if age is None:
                continue

            if age >= threshold:
                if not warned:
                    logging.warning(
                        "event monitor: no node update received from KLF for %.0fs (threshold=%ss); positions may be stale",
                        age,
                        threshold,
                    )
                    warned = True
            else:
                warned = False

        except asyncio.CancelledError:
            return
        except Exception:
            logging.exception("event_stale_monitor_task failed")


async def preventive_recovery_task():
    """
    Optional preventive recovery request every X hours.
    Disabled by default (preventive_recovery_hours = 0).
    Only if KLF is connected and nothing is moving.
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
        logging.debug(
            "Status mode: positions via KLF events, rain via polling every %ss",
            max(60, int(float(CFG.get("rain_poll_interval", 300)))),
        )

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

        # prepare / monitoring nodes
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

        tasks = [
            asyncio.create_task(publish_initial_snapshot()),
            asyncio.create_task(publish_health_task()),
            asyncio.create_task(moving_watchdog()),
            asyncio.create_task(poll_rain_sensors()),
            asyncio.create_task(preventive_recovery_task()),
            asyncio.create_task(event_stale_monitor_task()),
        ]

        # Main loop: wait until stop is requested
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

        # Disconnect pyvlx cleanly without rebooting the gateway
        try:
            await cleanup_pyvlx_instance(pyvlx, "shutdown")
            pyvlx = None
        except Exception:
            logging.debug("pyvlx cleanup during shutdown failed", exc_info=True)

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

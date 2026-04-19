"""
GhostWire Plugin: Bandwidth Alert
==================================
Demonstrates:
  - Hooking into the event bus (VPN_SESSION_ENDED)
  - Reading plugin config (webhook_url, cap_mb)
  - Sending a webhook POST when a user exceeds a data cap
  - Exposing a FastAPI APIRouter with a /status endpoint

Routes mounted at: /api/plugins/bandwidth-alert/
  GET  /status        — JSON summary of sessions seen since backend start
  GET  /config        — show current plugin config
  POST /test-webhook  — fire a test webhook to verify the URL works

Install:
  1. Zip this folder: zip -r bandwidth-alert.zip bandwidth-alert/
  2. Upload via Admin > Plugins > Upload Plugin
  3. Click Activate
  4. Click Configure and set webhook_url + cap_mb

Config keys (set via Admin > Plugins > Configure):
  webhook_url  — URL to POST to when the cap is exceeded (leave blank to disable)
  cap_mb       — data cap in megabytes, per session (default: 500)
"""

import json
import logging
import threading
import urllib.request
from datetime import datetime, timezone

from fastapi import APIRouter

log = logging.getLogger("ghostwire.plugin.bandwidth_alert")

# ── In-memory session log (reset on backend restart) ─────────────────────────
_sessions: list[dict] = []
_lock = threading.Lock()

# ── Helpers ───────────────────────────────────────────────────────────────────

SLUG = "bandwidth-alert"


def _get_config() -> dict:
    """Read config from DB. Runs in a worker thread — safe to call sync."""
    try:
        from app.infrastructure.db import SessionLocal
        from app.domains.plugins.service import get_plugin_config
        with SessionLocal() as db:
            return get_plugin_config(db, SLUG)
    except Exception as exc:
        log.warning(f"[bandwidth-alert] Could not load config: {exc}")
        return {}


def _send_webhook(url: str, payload: dict) -> None:
    """Fire-and-forget JSON POST to webhook_url."""
    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "GhostWire-Plugin/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            log.info(f"[bandwidth-alert] Webhook sent → {resp.status}")
    except Exception as exc:
        log.warning(f"[bandwidth-alert] Webhook failed: {exc}")


# ── Event bus hook ────────────────────────────────────────────────────────────

def _register_hooks() -> None:
    """Called once when the plugin module is imported (i.e. on activation)."""
    try:
        from app.infrastructure.events.bus import bus, Events

        @bus.on(Events.VPN_SESSION_ENDED)
        def on_session_ended(payload: dict) -> None:
            """
            payload keys (from scheduler.py):
              session_id, username, client_ip, virtual_ip, country_name
            The session bytes are read from the DB here so we always get
            the final value written by the updown hook.
            """
            username   = payload.get("username", "unknown")
            session_id = payload.get("session_id")

            # Read final byte counts from DB
            bytes_in = bytes_out = 0
            try:
                from app.infrastructure.db import SessionLocal
                from app.domains.vpn.models import VPNSession
                with SessionLocal() as db:
                    row = db.query(VPNSession).filter(
                        VPNSession.id == session_id
                    ).first() if session_id else None
                    if row:
                        bytes_in  = row.bytes_in  or 0
                        bytes_out = row.bytes_out or 0
            except Exception as exc:
                log.debug(f"[bandwidth-alert] DB lookup failed: {exc}")

            total_mb = (bytes_in + bytes_out) / (1024 * 1024)
            entry = {
                "username":    username,
                "session_id":  session_id,
                "bytes_in":    bytes_in,
                "bytes_out":   bytes_out,
                "total_mb":    round(total_mb, 2),
                "disconnected": datetime.now(timezone.utc).isoformat(),
            }

            with _lock:
                _sessions.append(entry)
                if len(_sessions) > 500:   # cap memory usage
                    _sessions.pop(0)

            # Check cap
            cfg     = _get_config()
            cap_mb  = float(cfg.get("cap_mb", 500))
            wh_url  = cfg.get("webhook_url", "").strip()

            if total_mb >= cap_mb and wh_url:
                log.info(
                    f"[bandwidth-alert] {username} used {total_mb:.1f} MB "
                    f"(cap={cap_mb} MB) — firing webhook"
                )
                hook_payload = {
                    "event":      "bandwidth_cap_exceeded",
                    "username":   username,
                    "session_id": str(session_id),
                    "total_mb":   round(total_mb, 2),
                    "cap_mb":     cap_mb,
                    "bytes_in":   bytes_in,
                    "bytes_out":  bytes_out,
                    "timestamp":  datetime.now(timezone.utc).isoformat(),
                }
                # Run in a daemon thread so we don't block the event loop
                t = threading.Thread(
                    target=_send_webhook, args=(wh_url, hook_payload), daemon=True
                )
                t.start()
            elif total_mb >= cap_mb:
                log.info(
                    f"[bandwidth-alert] {username} used {total_mb:.1f} MB "
                    f"(cap={cap_mb} MB) — no webhook_url configured, skipping"
                )

        log.info("[bandwidth-alert] Event hooks registered")
    except Exception as exc:
        log.warning(f"[bandwidth-alert] Hook registration failed: {exc}")


# Register hooks the moment this module is imported
_register_hooks()


# ── FastAPI router ────────────────────────────────────────────────────────────

router = APIRouter()


@router.get("/status")
def plugin_status():
    """
    Returns a summary of VPN sessions recorded since the last backend restart.
    Useful for verifying the plugin is working and data caps are tracked.
    """
    with _lock:
        sessions_copy = list(_sessions)

    cfg    = _get_config()
    cap_mb = float(cfg.get("cap_mb", 500))

    exceeded = [s for s in sessions_copy if s["total_mb"] >= cap_mb]

    return {
        "plugin":          "bandwidth-alert",
        "version":         "1.0.0",
        "cap_mb":          cap_mb,
        "webhook_url_set": bool(cfg.get("webhook_url", "").strip()),
        "sessions_tracked": len(sessions_copy),
        "sessions_exceeded_cap": len(exceeded),
        "recent_sessions": sessions_copy[-20:],   # last 20
    }


@router.get("/config")
def show_config():
    """Return the current plugin configuration (webhook_url masked)."""
    cfg = _get_config()
    wh  = cfg.get("webhook_url", "")
    return {
        "cap_mb":      cfg.get("cap_mb", 500),
        "webhook_url": (wh[:12] + "…" if len(wh) > 12 else wh) or "(not set)",
    }


@router.post("/test-webhook")
def test_webhook():
    """
    Fire a test payload to the configured webhook_url so you can verify
    the endpoint is reachable before a real cap event fires.
    """
    cfg = _get_config()
    url = cfg.get("webhook_url", "").strip()
    if not url:
        return {"ok": False, "error": "webhook_url is not configured"}

    test_payload = {
        "event":      "test",
        "plugin":     "bandwidth-alert",
        "message":    "This is a test webhook from GhostWire Bandwidth Alert plugin.",
        "timestamp":  datetime.now(timezone.utc).isoformat(),
    }

    try:
        _send_webhook(url, test_payload)
        return {"ok": True, "message": f"Test webhook sent to {url[:30]}…"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

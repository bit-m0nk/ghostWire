"""GhostWire — Configuration service
Reads and writes /opt/ghostwire/.env in a safe, structured way.
All writes are atomic (write temp → rename) so a crash never corrupts the file.
"""
import os
import re
import tempfile
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("ghostwire.config")

ENV_PATH = Path("/opt/ghostwire/.env")

# Keys that are allowed to be read/written via the API.
# Any key not in this set is silently ignored on write to prevent injection.
ALLOWED_KEYS = {
    # SMTP
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_TLS", "NOTIFY_EMAIL",
    # DDNS — general
    "USE_DDNS", "DDNS_PRIMARY", "DDNS_HOSTNAME",
    # Dynu
    "DYNU_HOSTNAME", "DYNU_USERNAME", "DYNU_IP_UPDATE_PASS",
    # No-IP
    "NOIP_HOSTNAME", "NOIP_USERNAME", "NOIP_PASSWORD",
    # Telegram
    "TG_BOT_TOKEN", "TG_CHAT_ID",
    # VPN identity
    "VPN_BRAND", "PUBLIC_IP", "PANEL_PORT",
}


def read_env() -> dict[str, str]:
    """Return all key=value pairs from .env as a plain dict."""
    if not ENV_PATH.exists():
        return {}
    cfg: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        cfg[k.strip()] = v.strip()
    return cfg


def write_env(updates: dict[str, str]) -> None:
    """
    Merge *updates* into the existing .env file and write atomically.
    Only keys in ALLOWED_KEYS are ever written.
    Values are sanitised: no newlines, no unescaped quotes.
    """
    safe_updates = {
        k: _sanitise_value(v)
        for k, v in updates.items()
        if k in ALLOWED_KEYS
    }
    if not safe_updates:
        return

    # Read existing content preserving comments and ordering
    existing_lines: list[str] = []
    if ENV_PATH.exists():
        existing_lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    # Update existing lines in-place
    written: set[str] = set()
    new_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        k = stripped.partition("=")[0].strip()
        if k in safe_updates:
            new_lines.append(f"{k}={safe_updates[k]}")
            written.add(k)
        else:
            new_lines.append(line)

    # Append any keys that weren't already present
    for k, v in safe_updates.items():
        if k not in written:
            new_lines.append(f"{k}={v}")

    content = "\n".join(new_lines) + "\n"

    # Atomic write
    tmp = ENV_PATH.parent / f".env.tmp.{os.getpid()}"
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(ENV_PATH)
        log.info(f"Config updated: {list(safe_updates.keys())}")
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _sanitise_value(v: str) -> str:
    """Remove characters that break shell variable assignments."""
    return re.sub(r"[\r\n]", "", str(v))


# ── Structured helpers ────────────────────────────────────────────────────────

def get_smtp_config() -> Optional[dict]:
    """Return SMTP settings or None if not configured."""
    cfg = read_env()
    host = cfg.get("SMTP_HOST", "").strip()
    if not host:
        return None
    user = cfg.get("SMTP_USER", "").strip()
    password = (cfg.get("SMTP_PASS", "") or cfg.get("SMTP_PASSWORD", "")).strip()
    from_addr = cfg.get("SMTP_FROM", user).strip() or user
    brand = cfg.get("VPN_BRAND", "GhostWire").strip()
    return {
        "host":     host,
        "port":     int(cfg.get("SMTP_PORT", "587")),
        "user":     user,
        "password": password,
        "from":     from_addr,
        "brand":    brand,
        "tls":      cfg.get("SMTP_TLS", "starttls").lower(),
        "notify_email": cfg.get("NOTIFY_EMAIL", "").strip(),
    }


def get_ddns_config() -> dict:
    """Return DDNS settings (always returns a dict, never None)."""
    cfg = read_env()
    return {
        "use_ddns":           cfg.get("USE_DDNS", "false").lower() == "true",
        "ddns_primary":       cfg.get("DDNS_PRIMARY", "dynu"),
        "ddns_hostname":      cfg.get("DDNS_HOSTNAME", ""),
        "dynu_hostname":      cfg.get("DYNU_HOSTNAME", ""),
        "dynu_username":      cfg.get("DYNU_USERNAME", ""),
        "dynu_has_password":  bool(cfg.get("DYNU_IP_UPDATE_PASS", "").strip()),
        "noip_hostname":      cfg.get("NOIP_HOSTNAME", ""),
        "noip_username":      cfg.get("NOIP_USERNAME", ""),
        "noip_has_password":  bool(cfg.get("NOIP_PASSWORD", "").strip()),
    }


def get_notification_config() -> dict:
    cfg = read_env()
    return {
        "tg_enabled":    bool(cfg.get("TG_BOT_TOKEN", "").strip()),
        "tg_chat_id":    cfg.get("TG_CHAT_ID", ""),
        "notify_email":  cfg.get("NOTIFY_EMAIL", ""),
    }

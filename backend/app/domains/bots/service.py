"""GhostWire — Bot integration service (Phase 4)

Sends notifications to Telegram, Discord, or Slack.
One codebase — platform is picked at runtime from BotConfig.

Public API:
    notify(db, event_type, message) — send to all enabled platforms that
                                      have this event toggled on.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.domains.bots.models import BotConfig, BotMessage

log = logging.getLogger("ghostwire.bots")

# ── Default event toggles ─────────────────────────────────────────────────────
DEFAULT_TOGGLES = {
    "vpn_connect":      True,
    "vpn_disconnect":   True,
    "user_created":     True,
    "user_deleted":     True,
    "login_success":    False,
    "login_failed":     True,
    "node_offline":     True,
    "node_online":      True,
    "dns_blocklist_synced": False,
    "system_alert":     True,
}

ALL_PLATFORMS = ["telegram", "discord", "slack"]
SEND_TIMEOUT  = 8.0


# ── Message formatting helpers ────────────────────────────────────────────────

def _html_to_markdown(text: str) -> str:
    """Convert Telegram HTML tags to Discord/Slack markdown."""
    text = re.sub(r'<b>(.*?)</b>', r'**\1**', text, flags=re.DOTALL)
    text = re.sub(r'<i>(.*?)</i>', r'_\1_', text, flags=re.DOTALL)
    text = re.sub(r'<code>(.*?)</code>', r'`\1`', text, flags=re.DOTALL)
    text = re.sub(r'<pre>(.*?)</pre>', r'```\1```', text, flags=re.DOTALL)
    text = re.sub(r'<a href="(.*?)">(.*?)</a>', r'\2 (\1)', text, flags=re.DOTALL)
    # Strip any remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def _format_for_platform(platform: str, text: str) -> str:
    """Return properly formatted message text for each platform."""
    if platform == "telegram":
        # Telegram uses HTML natively — pass through as-is
        return text
    elif platform == "discord":
        # Discord uses markdown — convert HTML tags
        return _html_to_markdown(text)
    elif platform == "slack":
        # Slack uses its own mrkdwn but *bold* works; convert HTML
        msg = _html_to_markdown(text)
        # Slack uses *bold* not **bold**
        msg = re.sub(r'\*\*(.*?)\*\*', r'*\1*', msg)
        return msg
    return text


# ── Low-level send helpers ────────────────────────────────────────────────────

def _send_telegram(bot_token: str, chat_id: str, text: str) -> Optional[str]:
    """Returns None on success, error string on failure."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        r = httpx.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                       timeout=SEND_TIMEOUT)
        if r.status_code == 200:
            return None
        return f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as exc:
        return str(exc)[:200]


def _send_discord(webhook_url: str, text: str) -> Optional[str]:
    """Returns None on success, error string on failure."""
    try:
        r = httpx.post(webhook_url, json={"content": text}, timeout=SEND_TIMEOUT)
        if r.status_code in (200, 204):
            return None
        return f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as exc:
        return str(exc)[:200]


def _send_slack(webhook_url: str, text: str) -> Optional[str]:
    """Returns None on success, error string on failure."""
    try:
        r = httpx.post(webhook_url, json={"text": text}, timeout=SEND_TIMEOUT)
        if r.status_code == 200:
            return None
        return f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as exc:
        return str(exc)[:200]


# ── Public notify function ────────────────────────────────────────────────────

def notify(db: Session, event_type: str, message: str) -> list[dict]:
    """
    Send `message` to every enabled platform that has `event_type` toggled on.
    Logs each attempt to BotMessage.
    Returns list of result dicts.
    """
    results = []
    configs = db.query(BotConfig).filter(BotConfig.is_enabled == True).all()

    for cfg in configs:
        # Check event toggle
        toggles = DEFAULT_TOGGLES.copy()
        if cfg.event_toggles:
            try:
                toggles.update(json.loads(cfg.event_toggles))
            except Exception:
                pass

        if not toggles.get(event_type, True):
            results.append({"platform": cfg.platform, "status": "skipped"})
            continue

        # Format message appropriately for each platform
        formatted = _format_for_platform(cfg.platform, message)

        error = None
        if cfg.platform == "telegram":
            if cfg.tg_bot_token and cfg.tg_chat_id:
                error = _send_telegram(cfg.tg_bot_token, cfg.tg_chat_id, formatted)
            else:
                error = "Missing token or chat_id"

        elif cfg.platform == "discord":
            if cfg.discord_webhook_url:
                error = _send_discord(cfg.discord_webhook_url, formatted)
            else:
                error = "Missing webhook URL"

        elif cfg.platform == "slack":
            if cfg.slack_webhook_url:
                error = _send_slack(cfg.slack_webhook_url, formatted)
            else:
                error = "Missing webhook URL"

        status = "failed" if error else "sent"
        db.add(BotMessage(
            platform   = cfg.platform,
            event_type = event_type,
            message    = formatted[:2000],
            status     = status,
            error      = error,
        ))
        if error:
            log.warning(f"Bot [{cfg.platform}] send failed for {event_type}: {error}")
        else:
            log.debug(f"Bot [{cfg.platform}] sent: {event_type}")

        results.append({"platform": cfg.platform, "status": status, "error": error})

    if configs:
        db.commit()

    return results


def seed_default_bot_configs(db: Session) -> None:
    """Ensure one BotConfig row per platform exists (idempotent)."""
    for platform in ALL_PLATFORMS:
        exists = db.query(BotConfig).filter(BotConfig.platform == platform).first()
        if not exists:
            db.add(BotConfig(platform=platform, is_enabled=False))
    db.commit()


def config_to_dict(cfg: BotConfig) -> dict:
    toggles = DEFAULT_TOGGLES.copy()
    if cfg.event_toggles:
        try:
            toggles.update(json.loads(cfg.event_toggles))
        except Exception:
            pass
    return {
        "id":         cfg.id,
        "platform":   cfg.platform,
        "is_enabled": cfg.is_enabled,
        "tg_bot_token":         "***" if cfg.tg_bot_token else "",
        "tg_chat_id":           cfg.tg_chat_id or "",
        "discord_webhook_url":  "***" if cfg.discord_webhook_url else "",
        "slack_webhook_url":    "***" if cfg.slack_webhook_url else "",
        "event_toggles":        toggles,
        "updated_at":           cfg.updated_at.isoformat() if cfg.updated_at else None,
    }

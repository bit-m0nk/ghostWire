"""GhostWire — Bot integration router (Phase 4)

Endpoints:
  GET    /bots/                      — list all platform configs (masked secrets)
  PATCH  /bots/{platform}            — update a platform's config
  POST   /bots/{platform}/test       — send a test message to one platform
  GET    /bots/messages              — recent bot message log (paginated)
  GET    /bots/events                — list of known event types + labels
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.domains.users.models import User
from app.domains.bots.models import BotConfig, BotMessage
from app.domains.bots import service as bot_svc
from app.infrastructure.db import get_db
from app.infrastructure.events.bus import bus, Events

log    = logging.getLogger("ghostwire.bots")
router = APIRouter()

PLATFORMS = ["telegram", "discord", "slack"]

# ── Human-readable event labels ───────────────────────────────────────────────
EVENT_LABELS = {
    "vpn_connect":          "VPN: User connected",
    "vpn_disconnect":       "VPN: User disconnected",
    "user_created":         "User: Account created",
    "user_deleted":         "User: Account deleted",
    "login_success":        "Auth: Login success",
    "login_failed":         "Auth: Login failed",
    "node_offline":         "Node: Went offline",
    "node_online":          "Node: Came back online",
    "dns_blocklist_synced": "DNS: Blocklist synced",
    "system_alert":         "System: Alert",
}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class BotUpdate(BaseModel):
    is_enabled:             Optional[bool]  = None
    tg_bot_token:           Optional[str]   = None
    tg_chat_id:             Optional[str]   = None
    discord_webhook_url:    Optional[str]   = None
    slack_webhook_url:      Optional[str]   = None
    event_toggles:          Optional[dict]  = None   # partial merge


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
async def list_bots(
    db:    Session = Depends(get_db),
    admin: User    = Depends(require_admin),
):
    configs = db.query(BotConfig).order_by(BotConfig.platform).all()
    return [bot_svc.config_to_dict(c) for c in configs]


@router.get("/events")
async def list_events(admin: User = Depends(require_admin)):
    """All known event types with human labels."""
    return [
        {"key": k, "label": v, "default": bot_svc.DEFAULT_TOGGLES.get(k, False)}
        for k, v in EVENT_LABELS.items()
    ]


@router.patch("/{platform}")
async def update_bot(
    platform: str,
    data:     BotUpdate,
    db:       Session = Depends(get_db),
    admin:    User    = Depends(require_admin),
):
    if platform not in PLATFORMS:
        raise HTTPException(400, f"Unknown platform '{platform}'. Valid: {PLATFORMS}")

    cfg = db.query(BotConfig).filter(BotConfig.platform == platform).first()
    if not cfg:
        raise HTTPException(404, "Bot config not found (run startup seed)")

    if data.is_enabled is not None:
        cfg.is_enabled = data.is_enabled

    # Only update secret fields if a non-empty value is supplied
    # (empty string = no change; send "CLEAR" to explicitly clear)
    if data.tg_bot_token is not None:
        cfg.tg_bot_token = None if data.tg_bot_token == "CLEAR" else (data.tg_bot_token or cfg.tg_bot_token)
    if data.tg_chat_id is not None:
        cfg.tg_chat_id = data.tg_chat_id
    if data.discord_webhook_url is not None:
        cfg.discord_webhook_url = None if data.discord_webhook_url == "CLEAR" else (data.discord_webhook_url or cfg.discord_webhook_url)
    if data.slack_webhook_url is not None:
        cfg.slack_webhook_url = None if data.slack_webhook_url == "CLEAR" else (data.slack_webhook_url or cfg.slack_webhook_url)

    # Merge event toggles
    if data.event_toggles is not None:
        existing: dict = bot_svc.DEFAULT_TOGGLES.copy()
        if cfg.event_toggles:
            try:
                existing.update(json.loads(cfg.event_toggles))
            except Exception:
                pass
        existing.update(data.event_toggles)
        cfg.event_toggles = json.dumps(existing)

    cfg.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(cfg)
    log.info(f"Bot config updated: {platform}, enabled={cfg.is_enabled}")
    return bot_svc.config_to_dict(cfg)


@router.post("/{platform}/test")
async def test_bot(
    platform: str,
    db:       Session = Depends(get_db),
    admin:    User    = Depends(require_admin),
):
    """Send a test message to the specified platform."""
    if platform not in PLATFORMS:
        raise HTTPException(400, f"Unknown platform '{platform}'")

    cfg = db.query(BotConfig).filter(BotConfig.platform == platform).first()
    if not cfg or not cfg.is_enabled:
        raise HTTPException(400, f"Platform '{platform}' is not enabled")

    test_msg = f"👻 <b>GhostWire test notification</b>\nPlatform: {platform}\nThis is a test message from your GhostWire dashboard."

    # Temporarily force event to pass any toggle check
    original_toggles = cfg.event_toggles
    cfg.event_toggles = json.dumps({**bot_svc.DEFAULT_TOGGLES, "system_alert": True})

    results = bot_svc.notify(db, "system_alert", test_msg)

    cfg.event_toggles = original_toggles
    db.commit()

    result = next((r for r in results if r["platform"] == platform), None)
    if not result or result.get("status") == "failed":
        raise HTTPException(400, result.get("error") if result else "Send failed")

    return {"message": f"Test message sent to {platform}", "result": result}


@router.get("/messages")
async def list_messages(
    platform:   Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit:      int            = Query(50, le=200),
    offset:     int            = Query(0),
    db:         Session        = Depends(get_db),
    admin:      User           = Depends(require_admin),
):
    q = db.query(BotMessage)
    if platform:
        q = q.filter(BotMessage.platform == platform)
    if event_type:
        q = q.filter(BotMessage.event_type == event_type)
    total = q.count()
    rows  = q.order_by(BotMessage.sent_at.desc()).offset(offset).limit(limit).all()
    return {
        "total":  total,
        "offset": offset,
        "items": [
            {
                "id":         r.id,
                "platform":   r.platform,
                "event_type": r.event_type,
                "message":    r.message,
                "status":     r.status,
                "error":      r.error,
                "sent_at":    r.sent_at.isoformat() if r.sent_at else None,
            }
            for r in rows
        ],
    }

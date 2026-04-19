"""GhostWire — Bot integration model (bots domain, Phase 4)

Stores per-platform bot configuration and notification preferences.
One row per platform; admin configures from the Config UI.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer
from app.infrastructure.db import Base


class BotConfig(Base):
    """Bot integration config for one platform (telegram | discord | slack)."""
    __tablename__ = "bot_configs"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    platform    = Column(String(32), unique=True, nullable=False)  # telegram | discord | slack
    is_enabled  = Column(Boolean, default=False)

    # Telegram
    tg_bot_token   = Column(String, nullable=True)
    tg_chat_id     = Column(String, nullable=True)

    # Discord
    discord_webhook_url = Column(String, nullable=True)

    # Slack
    slack_webhook_url   = Column(String, nullable=True)

    # Notification event toggles (JSON blob)
    # e.g. {"vpn_connect": true, "vpn_disconnect": true, "user_created": false, ...}
    event_toggles   = Column(Text, nullable=True, default=None)

    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))


class BotMessage(Base):
    """Log of bot messages sent — for audit + rate-limit debugging."""
    __tablename__ = "bot_messages"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    platform    = Column(String(32), nullable=False, index=True)
    event_type  = Column(String(64), nullable=False)
    message     = Column(Text, nullable=False)
    status      = Column(String(16), default="sent")   # sent | failed | skipped
    error       = Column(Text, nullable=True)
    sent_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

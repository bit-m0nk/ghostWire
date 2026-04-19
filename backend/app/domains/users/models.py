"""GhostWire — User model (users domain)"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer
from app.infrastructure.db import Base


class User(Base):
    __tablename__ = "users"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username        = Column(String(64), unique=True, nullable=False, index=True)
    full_name       = Column(String(128), nullable=False, default="")
    email           = Column(String(256), unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin        = Column(Boolean, default=False)
    is_active       = Column(Boolean, default=True)
    vpn_enabled     = Column(Boolean, default=True)

    # VPN credentials (separate from panel login)
    vpn_username    = Column(String(64), unique=True, nullable=True)
    vpn_password    = Column(String, nullable=True)   # bcrypt hash

    # Metadata
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc))
    last_login      = Column(DateTime, nullable=True)
    notes           = Column(Text, default="")

    # Bandwidth limits (0 = unlimited)
    bandwidth_limit_gb = Column(String, default="0")

    # ── Phase 2: 2FA ──────────────────────────────────────────────────────────
    totp_secret     = Column(String, nullable=True)          # base32 TOTP secret
    totp_enabled    = Column(Boolean, default=False)         # whether TOTP is active

    # ── Phase 2: Custom profile fields ────────────────────────────────────────
    # JSON blob: {"field_key": "value", ...} — schema defined by admin
    custom_fields   = Column(Text, nullable=True, default=None)

    # ── Phase 2: API keys (portal self-service) ───────────────────────────────
    # Separate table UserAPIKey references user.id


class UserAPIKey(Base):
    """Per-user API keys for portal programmatic access (Phase 2)."""
    __tablename__ = "user_api_keys"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id     = Column(String, nullable=False, index=True)     # FK → users.id
    name        = Column(String(64), nullable=False)             # human label
    key_hash    = Column(String, nullable=False)                 # bcrypt hash of raw key
    key_prefix  = Column(String(16), nullable=False)             # first 11 chars for display ("gw_" + 8 hex)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_used   = Column(DateTime, nullable=True)
    is_active   = Column(Boolean, default=True)

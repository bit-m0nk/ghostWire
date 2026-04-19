"""GhostWire — DNS domain models (Phase 3)

Tables:
  dns_events        — every blocked / allowed query captured from dnsmasq logs
  blocklist_sources — upstream blocklist URLs + last-sync metadata
  user_dns_settings — per-user DNS blocking toggle + custom whitelist/blacklist
  dns_overrides     — admin-level global whitelist / blacklist entries
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer, Text, Index
)
from app.infrastructure.db import Base


class DnsEvent(Base):
    """One DNS query event captured from dnsmasq query log."""
    __tablename__ = "dns_events"

    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id    = Column(String, nullable=True, index=True)   # None = unknown client
    domain     = Column(String(253), nullable=False, index=True)
    qtype      = Column(String(8),  default="A")             # A, AAAA, CNAME…
    action     = Column(String(8),  nullable=False, index=True)  # "blocked" | "allowed"
    reason     = Column(String(64), nullable=True)           # e.g. "blocklist:stevenblack"
    client_ip  = Column(String(45), nullable=True)           # VPN tunnel IP
    timestamp  = Column(DateTime,   nullable=False, index=True,
                        default=lambda: datetime.now(timezone.utc))

    # Compound indexes for the most common GraphQL query patterns
    __table_args__ = (
        Index("ix_dns_events_user_ts",   "user_id",  "timestamp"),
        Index("ix_dns_events_action_ts", "action",   "timestamp"),
        Index("ix_dns_events_domain_ts", "domain",   "timestamp"),
    )


class BlocklistSource(Base):
    """Upstream blocklist URL + sync state."""
    __tablename__ = "blocklist_sources"

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name         = Column(String(128), nullable=False)
    url          = Column(String(512), nullable=False, unique=True)
    is_active    = Column(Boolean, default=True)
    domain_count = Column(Integer, default=0)
    last_synced  = Column(DateTime, nullable=True)
    last_error   = Column(Text,     nullable=True)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class UserDnsSettings(Base):
    """Per-user DNS ad-blocking configuration."""
    __tablename__ = "user_dns_settings"

    user_id            = Column(String, primary_key=True)   # FK → users.id
    blocking_enabled   = Column(Boolean, default=True)
    # JSON list: ["ads.example.com", ...] — user-specific additions
    custom_whitelist   = Column(Text, default="[]")   # always allowed
    custom_blacklist   = Column(Text, default="[]")   # always blocked
    updated_at         = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                                onupdate=lambda: datetime.now(timezone.utc))


class DnsOverride(Base):
    """Admin-level global whitelist / blacklist entries."""
    __tablename__ = "dns_overrides"

    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    domain     = Column(String(253), nullable=False, unique=True, index=True)
    action     = Column(String(8),  nullable=False)   # "allow" | "block"
    reason     = Column(String(256), nullable=True)
    created_by = Column(String, nullable=True)         # admin user_id
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

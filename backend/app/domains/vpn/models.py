"""GhostWire — VPN Session model (vpn domain)"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, BigInteger, ForeignKey
from app.infrastructure.db import Base


class VPNSession(Base):
    __tablename__ = "vpn_sessions"

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id      = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    username     = Column(String(64), nullable=False)
    client_ip    = Column(String(64))
    virtual_ip   = Column(String(64))
    country      = Column(String(8), default="??")
    country_name = Column(String(64), default="Unknown")
    device_info  = Column(String(256), default="")
    bytes_in     = Column(BigInteger, default=0)
    bytes_out    = Column(BigInteger, default=0)
    connected_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    disconnected_at = Column(DateTime, nullable=True)
    is_active    = Column(Boolean, default=True)
    session_key  = Column(String, unique=True, nullable=True)   # charon unique id

    # ── Phase 3 placeholder ───────────────────────────────────────────────────
    # dns_blocked_count  — number of DNS requests blocked in this session

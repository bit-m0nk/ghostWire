"""GhostWire — Audit Log model (audit domain)"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text
from app.infrastructure.db import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp  = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    actor      = Column(String(64))       # who did it
    action     = Column(String(128))      # what they did
    target     = Column(String(256))      # who/what it affected
    detail     = Column(Text, default="")
    ip_address = Column(String(64), default="")
    level      = Column(String(16), default="info")   # info / warning / danger

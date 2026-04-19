"""GhostWire — Analytics domain models (Phase 3)

DnsEvent is the raw fact table (lives in dns domain).
DailySummary is the pre-rolled aggregate for fast dashboard queries.
"""
import uuid
from datetime import datetime, timezone, date
from sqlalchemy import Column, String, Integer, Float, Date, DateTime, UniqueConstraint
from app.infrastructure.db import Base


class DailySummary(Base):
    """Pre-rolled daily stats per user (or global when user_id is NULL).

    Background task in scheduler.py writes one row per (user_id, date) at midnight.
    Dashboard widgets query this table instead of scanning dns_events for speed.
    """
    __tablename__ = "dns_daily_summaries"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id         = Column(String, nullable=True, index=True)  # NULL = global
    summary_date    = Column(Date,   nullable=False, index=True)
    total_queries   = Column(Integer, default=0)
    blocked_count   = Column(Integer, default=0)
    allowed_count   = Column(Integer, default=0)
    block_rate      = Column(Float,   default=0.0)
    top_blocked_json = Column(String, default="[]")   # JSON list[{domain, count}]
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "summary_date", name="uq_daily_user_date"),
    )

"""GhostWire — Node model (nodes domain, Phase 4)

Represents remote GhostWire server nodes that can be managed from this
primary dashboard. Each node runs a GhostWire instance with the same
API; this node acts as the management plane.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, Float
from app.infrastructure.db import Base


class ServerNode(Base):
    """A remote GhostWire node managed from this dashboard."""
    __tablename__ = "server_nodes"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name        = Column(String(128), nullable=False)           # human label e.g. "Frankfurt-01"
    hostname    = Column(String(256), nullable=False)           # IP or FQDN
    port        = Column(Integer, default=8080)                 # API port
    api_key     = Column(String, nullable=True)                 # bearer token for remote API
    location    = Column(String(64), default="")               # e.g. "Germany"
    flag        = Column(String(8), default="🌐")               # emoji flag
    is_primary  = Column(Boolean, default=False)                # is this the local/primary node?
    is_enabled  = Column(Boolean, default=True)

    # Health tracking
    status          = Column(String(16), default="unknown")     # online | offline | degraded | unknown
    last_seen       = Column(DateTime, nullable=True)
    last_check_at   = Column(DateTime, nullable=True)
    latency_ms      = Column(Float, nullable=True)
    error_message   = Column(Text, nullable=True)

    # Cached stats from last health check
    active_sessions = Column(Integer, default=0)
    total_users     = Column(Integer, default=0)
    cpu_percent     = Column(Float, nullable=True)
    mem_percent     = Column(Float, nullable=True)
    uptime_seconds  = Column(Integer, nullable=True)

    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))

    # Notes / description
    notes       = Column(Text, default="")


class NodeHealthLog(Base):
    """Time-series health log per node — pruned to last 24h."""
    __tablename__ = "node_health_logs"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    node_id     = Column(String, nullable=False, index=True)
    checked_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status      = Column(String(16), default="unknown")
    latency_ms  = Column(Float, nullable=True)
    active_sessions = Column(Integer, default=0)
    cpu_percent = Column(Float, nullable=True)
    mem_percent = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)

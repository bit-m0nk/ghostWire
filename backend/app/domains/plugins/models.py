"""GhostWire — Plugin domain models (Phase 5)

Plugins are self-contained Python packages dropped into /opt/ghostwire/plugins/.
Each plugin has a ghostwire_plugin.json manifest and an optional router.py that
exposes extra API routes.  The DB table tracks install state and config overrides.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime
from app.infrastructure.db import Base


class Plugin(Base):
    __tablename__ = "plugins"

    id          = Column(Integer, primary_key=True, index=True)
    slug        = Column(String(80), unique=True, nullable=False, index=True)
    name        = Column(String(120), nullable=False)
    version     = Column(String(30), nullable=False)
    author      = Column(String(120), default="")
    description = Column(Text, default="")
    homepage    = Column(String(255), default="")
    # "active" | "inactive" | "error"
    status      = Column(String(20), default="inactive", nullable=False)
    # JSON blob: user-supplied config values for this plugin
    config_json = Column(Text, default="{}")
    # Filesystem path where the plugin folder lives
    install_path = Column(String(512), default="")
    # pip packages the plugin declared as requirements
    pip_deps     = Column(Text, default="")  # newline-separated
    error_msg    = Column(Text, default="")
    installed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

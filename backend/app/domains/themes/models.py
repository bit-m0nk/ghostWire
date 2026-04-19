"""GhostWire — Theme domain models (Phase 5)

Themes are stored as rows in the DB.  Each theme is a JSON blob of CSS
variable overrides that get injected into the dashboard at runtime.

Built-in themes (indigo, midnight, forest, rose, amber) are seeded on startup.
Users can also save custom themes.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime
from app.infrastructure.db import Base


class Theme(Base):
    __tablename__ = "themes"

    id          = Column(Integer, primary_key=True, index=True)
    slug        = Column(String(80), unique=True, nullable=False, index=True)
    name        = Column(String(120), nullable=False)
    description = Column(Text, default="")
    # JSON blob: { "--accent": "#6366f1", "--bg1": "#0a0c14", ... }
    variables   = Column(Text, nullable=False, default="{}")
    is_builtin  = Column(Boolean, default=False)
    is_active   = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))


# ─── Built-in theme definitions ──────────────────────────────────────────────

BUILTIN_THEMES = [
    {
        "slug": "indigo",
        "name": "Indigo (Default)",
        "description": "The default GhostWire dark theme — indigo-purple accents",
        "is_builtin": True,
        "is_active": True,
        "variables": {
            "--bg1": "#0a0c14",
            "--bg2": "#111827",
            "--bg3": "#1a2035",
            "--bg4": "#1e2a40",
            "--border": "#1e2a3a",
            "--text": "#e2e8f0",
            "--text2": "#94a3b8",
            "--text3": "#64748b",
            "--accent": "#6366f1",
            "--accent2": "#4f46e5",
            "--accent3": "rgba(99,102,241,0.15)",
            "--success": "#34d399",
            "--warning": "#fbbf24",
            "--danger": "#f87171",
            "--info": "#60a5fa",
            "--radius": "12px",
            "--radius-sm": "8px",
        },
    },
    {
        "slug": "midnight",
        "name": "Midnight Blue",
        "description": "Deep navy with cyan accents",
        "is_builtin": True,
        "is_active": False,
        "variables": {
            "--bg1": "#060b18",
            "--bg2": "#0d1526",
            "--bg3": "#132038",
            "--bg4": "#1a2b4a",
            "--border": "#1a2d48",
            "--text": "#e0ecff",
            "--text2": "#7fa8d4",
            "--text3": "#4a6c8c",
            "--accent": "#22d3ee",
            "--accent2": "#0891b2",
            "--accent3": "rgba(34,211,238,0.12)",
            "--success": "#4ade80",
            "--warning": "#facc15",
            "--danger": "#fb7185",
            "--info": "#818cf8",
            "--radius": "12px",
            "--radius-sm": "8px",
        },
    },
    {
        "slug": "forest",
        "name": "Forest",
        "description": "Dark green with emerald highlights",
        "is_builtin": True,
        "is_active": False,
        "variables": {
            "--bg1": "#070d09",
            "--bg2": "#0d1a0f",
            "--bg3": "#132616",
            "--bg4": "#1a3320",
            "--border": "#1a321e",
            "--text": "#dcf5e4",
            "--text2": "#80b892",
            "--text3": "#4a7a57",
            "--accent": "#10b981",
            "--accent2": "#059669",
            "--accent3": "rgba(16,185,129,0.12)",
            "--success": "#34d399",
            "--warning": "#fbbf24",
            "--danger": "#f87171",
            "--info": "#60a5fa",
            "--radius": "12px",
            "--radius-sm": "8px",
        },
    },
    {
        "slug": "rose",
        "name": "Rose",
        "description": "Dark mode with rose-pink accents",
        "is_builtin": True,
        "is_active": False,
        "variables": {
            "--bg1": "#120a0d",
            "--bg2": "#1d1014",
            "--bg3": "#2a151a",
            "--bg4": "#381a21",
            "--border": "#3a1a22",
            "--text": "#fde8ec",
            "--text2": "#cf8d98",
            "--text3": "#8a5560",
            "--accent": "#fb7185",
            "--accent2": "#e11d48",
            "--accent3": "rgba(251,113,133,0.12)",
            "--success": "#34d399",
            "--warning": "#fbbf24",
            "--danger": "#f87171",
            "--info": "#60a5fa",
            "--radius": "12px",
            "--radius-sm": "8px",
        },
    },
    {
        "slug": "amber",
        "name": "Amber",
        "description": "Deep warm dark theme with amber accents",
        "is_builtin": True,
        "is_active": False,
        "variables": {
            "--bg1": "#0f0c04",
            "--bg2": "#1a1508",
            "--bg3": "#261f0d",
            "--bg4": "#332a12",
            "--border": "#352b10",
            "--text": "#fef3c7",
            "--text2": "#c49f50",
            "--text3": "#7d6230",
            "--accent": "#fbbf24",
            "--accent2": "#d97706",
            "--accent3": "rgba(251,191,36,0.12)",
            "--success": "#34d399",
            "--warning": "#fbbf24",
            "--danger": "#f87171",
            "--info": "#60a5fa",
            "--radius": "12px",
            "--radius-sm": "8px",
        },
    },
]

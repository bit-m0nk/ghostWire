"""
GhostWire Backend — FastAPI Application (modular monolith)

Domain layout:
  /api/auth      — Authentication (login, token, me, change-password)
  /api/users     — User management (admin only)
  /api/vpn       — VPN session control + server info
  /api/stats     — Dashboard, active sessions, audit log
  /api/profiles  — VPN config file generation + CA cert downloads
  /api/system    — System info, cert regen, service status
  /api/config    — SMTP / DDNS / notification settings

Phase 3 will add:
  /api/dns       — Ad-blocking domain
  /api/analytics — GraphQL analytics endpoint

Phase 4 will add:
  /api/nodes     — Multi-server node management
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from app.infrastructure.db import engine, Base
from app.domains.auth.router        import router as auth_router
from app.domains.users.router       import router as users_router
from app.domains.vpn.router         import router as vpn_router
from app.domains.stats.router       import router as stats_router
from app.domains.profiles.router    import router as profiles_router
from app.domains.system.router      import router as system_router
from app.domains.config.router      import router as config_router
from app.domains.twofa.router       import router as twofa_router
from app.domains.customfields.router import router as customfields_router
from app.domains.apikeys.router     import router as apikeys_router
# Phase 3
from app.domains.dns.router         import router as dns_router
from app.domains.graphql.schema     import graphql_router
# Phase 4
from app.domains.nodes.router      import router as nodes_router
from app.domains.bots.router       import router as bots_router
# Phase 5
from app.domains.plugins.router    import router as plugins_router
from app.domains.themes.router     import router as themes_router
from app.domains.backup.router     import router as backup_router
# Phase 6
from app.domains.updates.router    import router as updates_router, start_update_checker
# WebSocket live push
from app.domains.ws.router         import router as ws_router, register_ws_event_relays
from app.core.config import settings
from app.core.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import all models so Base.metadata has every table before create_all
    import app.domains.users.models       # noqa: F401 — User, UserAPIKey
    import app.domains.vpn.models         # noqa: F401 — VPNSession
    import app.domains.audit.models       # noqa: F401 — AuditLog
    import app.domains.customfields.models # noqa: F401 — CustomFieldSchema
    # Phase 3
    import app.domains.dns.models           # noqa: F401 — DnsEvent, BlocklistSource, etc.
    import app.domains.analytics.models     # noqa: F401 — DailySummary
    # Phase 4
    import app.domains.nodes.models         # noqa: F401 — ServerNode, NodeHealthLog
    import app.domains.bots.models          # noqa: F401 — BotConfig, BotMessage
    # Phase 5
    import app.domains.plugins.models       # noqa: F401 — Plugin
    import app.domains.themes.models        # noqa: F401 — Theme
    # Run schema migrations for existing installs before create_all
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", ".."))
    from scripts.init_db import _migrate_vpn_session_is_active
    _migrate_vpn_session_is_active(engine)
    # Create all tables (safe to call repeatedly — skips existing tables)
    Base.metadata.create_all(bind=engine)
    # Seed default blocklists (Phase 3) — no-op if already seeded
    from app.infrastructure.db import SessionLocal as _SL
    from app.domains.dns.service import seed_default_blocklists
    with _SL() as _db:
        seed_default_blocklists(_db)
    # Seed default bot configs (Phase 4) — no-op if already seeded
    from app.domains.bots.service import seed_default_bot_configs
    from app.domains.bots.subscribers import register_subscribers
    with _SL() as _db:
        seed_default_bot_configs(_db)
    register_subscribers()
    # Wire WebSocket event relays (domain events → live push to dashboard)
    register_ws_event_relays()
    # Seed primary node entry if none exists
    from app.domains.nodes.models import ServerNode as _SN
    with _SL() as _db:
        if not _db.query(_SN).filter(_SN.is_primary == True).first():
            _db.add(_SN(
                name="Primary (this server)",
                hostname=settings.PUBLIC_IP or "localhost",
                port=settings.PANEL_PORT,
                is_primary=True,
                is_enabled=True,
                status="online",
                location="Primary",
                flag="🏠",
            ))
            _db.commit()
    # Phase 5: Seed built-in themes and scan plugin dir
    from app.domains.themes.router import seed_builtin_themes
    from app.domains.plugins.service import sync_plugins_from_disk, get_mounted_routers
    from app.domains.plugins.models import Plugin
    with _SL() as _db:
        seed_builtin_themes(_db)
        sync_plugins_from_disk(_db)
        # Re-activate any plugins that were active before this restart
        # (activation imports their router.py and registers it in _mounted_routers)
        active_plugins = _db.query(Plugin).filter(Plugin.status == "active").all()
        for _plugin in active_plugins:
            try:
                from app.domains.plugins.service import activate_plugin
                activate_plugin(_db, _plugin.slug)
            except Exception as _e:
                import logging as _log
                _log.getLogger("ghostwire.plugins").warning(
                    f"Could not re-activate plugin '{_plugin.slug}' at startup: {_e}"
                )
    # Mount routers for all plugins that registered one during activation above
    _plugin_routers = get_mounted_routers()
    for _slug, _plugin_router in _plugin_routers.items():
        try:
            app.include_router(
                _plugin_router,
                prefix=f"/api/plugins/{_slug}",
                tags=[f"Plugin:{_slug}"],
            )
            import logging as _log
            _log.getLogger("ghostwire.plugins").info(
                f"Plugin '{_slug}' routes mounted at /api/plugins/{_slug}/"
            )
        except Exception as _e:
            import logging as _log
            _log.getLogger("ghostwire.plugins").warning(
                f"Could not mount routes for plugin '{_slug}': {_e}"
            )
    start_update_checker()   # Phase 6: background GitHub release check
    start_scheduler()
    yield


app = FastAPI(
    title=f"{settings.VPN_BRAND} API",
    description="Self-hosted IKEv2/IPSec VPN management API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
)

import os as _os

# Build allowed origins list.
# In production the frontend is served by the same FastAPI process (no CORS needed),
# but during local development the Vite dev server runs on a separate port.
# We allow the wildcard for non-credentialed requests, and add explicit origins
# for credentialed requests (Authorization header / cookies) so browsers accept them.
_panel_port  = _os.environ.get("PANEL_PORT", "8080")
_extra_origins = [
    o.strip()
    for o in _os.environ.get("CORS_EXTRA_ORIGINS", "").split(",")
    if o.strip()
]
_cors_origins = [
    f"http://localhost:{_panel_port}",
    f"http://127.0.0.1:{_panel_port}",
    f"http://localhost:5173",   # Vite default dev port
    f"http://127.0.0.1:5173",
    *_extra_origins,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health check (unauthenticated — used by installer & uptime monitors) ─────
@app.get("/api/health", include_in_schema=False)
async def health():
    return {"status": "ok", "brand": settings.VPN_BRAND}


# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(auth_router,          prefix="/api/auth",         tags=["Authentication"])
app.include_router(users_router,         prefix="/api/users",         tags=["Users"])
app.include_router(vpn_router,           prefix="/api/vpn",           tags=["VPN"])
app.include_router(stats_router,         prefix="/api/stats",         tags=["Statistics"])
app.include_router(profiles_router,      prefix="/api/profiles",      tags=["Profiles"])
app.include_router(system_router,        prefix="/api/system",        tags=["System"])
app.include_router(config_router,        prefix="/api/config",        tags=["Config"])
# Phase 2
app.include_router(twofa_router,         prefix="/api/2fa",           tags=["Two-Factor Auth"])
app.include_router(customfields_router,  prefix="/api/customfields",  tags=["Custom Fields"])
app.include_router(apikeys_router,       prefix="/api/apikeys",       tags=["API Keys"])
# Phase 3
app.include_router(dns_router,           prefix="/api/dns",           tags=["DNS Blocking"])
app.include_router(graphql_router,       prefix="/api/graphql")
# Phase 4
app.include_router(nodes_router,         prefix="/api/nodes",          tags=["Nodes"])
app.include_router(bots_router,          prefix="/api/bots",           tags=["Bot Integrations"])
# Phase 5
app.include_router(plugins_router,       prefix="/api/plugins",        tags=["Plugins"])
app.include_router(themes_router,        prefix="/api/themes",         tags=["Themes"])
app.include_router(backup_router,        prefix="/api/backup",         tags=["Backup"])
# Phase 6
app.include_router(updates_router,       prefix="/api/updates",        tags=["Updates"])
# WebSocket live push — no prefix, the router defines /api/ws directly
app.include_router(ws_router,            prefix="/api",                tags=["WebSocket"])


# ── Frontend detection ────────────────────────────────────────────────────────

def _find_frontend_dist() -> str | None:
    candidates = [
        os.path.join(settings.INSTALL_DIR, "frontend_dist"),
        os.path.join(settings.INSTALL_DIR, "frontend", "dist"),
    ]
    for base in candidates:
        if os.path.exists(os.path.join(base, "index.html")):
            return base
    return None


_dist = _find_frontend_dist()

# ── Case A: built frontend exists ─────────────────────────────────────────────
if _dist:
    _assets = os.path.join(_dist, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file_path = os.path.join(_dist, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(_dist, "index.html"))

# ── Case B: no built frontend — serve setup page ──────────────────────────────
else:
    _SETUP_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GhostWire — Build Required</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#0a0c14;color:#e2e8f0;
     display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
.box{background:#111827;border:1px solid #1e2a3a;border-radius:16px;
     padding:40px;max-width:560px;width:100%}
h1{font-size:22px;color:#6366f1;margin-bottom:6px;text-align:center}
.sub{color:#64748b;font-size:13px;margin-bottom:24px;text-align:center}
.pill{display:flex;align-items:center;justify-content:center;gap:6px;margin-bottom:20px}
.dot{width:8px;height:8px;border-radius:50%;background:#34d399;box-shadow:0 0 6px #34d399}
.badge{background:rgba(52,211,153,.12);color:#34d399;border:1px solid rgba(52,211,153,.25);
       border-radius:20px;padding:3px 12px;font-size:12px}
.step{background:#0a0c14;border:1px solid #1e2a3a;border-radius:10px;padding:18px;margin:14px 0}
.step h3{font-size:12px;color:#64748b;margin-bottom:10px;text-transform:uppercase;letter-spacing:.05em}
code{display:block;background:#0f1623;border-radius:6px;padding:10px 14px;
     font-family:monospace;font-size:12px;color:#818cf8;
     white-space:pre-wrap;line-height:1.8;margin-top:8px}
a{color:#6366f1;font-size:13px}
.footer{text-align:center;margin-top:20px;font-size:11px;color:#475569}
.ghost{font-size:32px;display:block;text-align:center;margin-bottom:12px}
</style>
</head>
<body>
<div class="box">
  <span class="ghost">👻</span>
  <div class="pill"><div class="dot"></div><span class="badge">API online</span></div>
  <h1>GhostWire — Build Required</h1>
  <p class="sub">The VPN backend is running. Build the dashboard with one command.</p>

  <div class="step">
    <h3>Quickest way</h3>
    <code>sudo bash /opt/ghostwire/build-frontend.sh</code>
  </div>

  <div class="step">
    <h3>Manual steps</h3>
    <code>sudo apt install -y nodejs npm
cd /opt/ghostwire/frontend
sudo npm install
sudo npm run build
sudo cp -r dist ../frontend_dist
sudo systemctl restart ghostwire-backend</code>
  </div>

  <div class="footer">
    <a href="/api/docs">API documentation</a>
    &nbsp;·&nbsp;
    After building, refresh this page.
  </div>
</div>
</body>
</html>"""

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_setup_page(full_path: str = ""):
        return HTMLResponse(_SETUP_PAGE)

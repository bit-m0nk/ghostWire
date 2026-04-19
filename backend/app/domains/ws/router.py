"""GhostWire — WebSocket router (real-time push)

Single endpoint: GET /api/ws?token=<JWT>

The client connects once.  The server pushes JSON frames every
PUSH_INTERVAL seconds while the connection is open.

Frame types (``type`` field):
  "snapshot"   — full active-session list + key dashboard counters
  "event"      — a single domain event (connect, disconnect, login_failed, …)
  "ping"       — keepalive sent every ~30 s; client should reply with "pong"
  "error"      — auth or server error; connection is closed immediately after

Client → server messages:
  "pong"       — response to a server "ping"
  Any other text is ignored (reserved for future client commands).

Authentication:
  The JWT is passed as a query-parameter because browsers cannot set
  custom headers on a WebSocket handshake.  The token is validated using
  the same ``jose``/JWT logic used by the REST endpoints.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from app.domains.ws.manager import manager
from app.infrastructure.db import SessionLocal

log = logging.getLogger("ghostwire.ws")
router = APIRouter()

PUSH_INTERVAL = 3        # seconds between session snapshots
PING_INTERVAL = 30       # seconds between server keepalive pings


# ── Auth helper ───────────────────────────────────────────────────────────────

def _validate_token(token: str) -> dict | None:
    """Return the JWT payload dict if valid, else None."""
    try:
        from jose import jwt, JWTError
        from app.core.config import settings
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        if not payload.get("sub"):
            return None
        return payload
    except Exception:
        return None


def _get_user(username: str, db: Session):
    from app.domains.users.models import User
    return db.query(User).filter(User.username == username, User.is_active == True).first()


# ── Data snapshot builder ─────────────────────────────────────────────────────

def _build_snapshot(db: Session, is_admin: bool, user_id: str | None) -> dict:
    """Build the ``snapshot`` frame payload from the DB."""
    from app.domains.vpn.models import VPNSession
    from app.domains.users.models import User
    from sqlalchemy import func

    now = datetime.now(timezone.utc)

    if is_admin:
        sessions_q = db.query(VPNSession).filter(VPNSession.is_active == True).all()
    else:
        sessions_q = db.query(VPNSession).filter(
            VPNSession.user_id == user_id,
            VPNSession.is_active == True,
        ).all()

    def _fmt_bytes(b: int) -> str:
        if not b:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} PB"

    def _duration(connected_at) -> str:
        if not connected_at:
            return "—"
        ca = connected_at
        if ca.tzinfo is None:
            ca = ca.replace(tzinfo=timezone.utc)
        delta = now - ca
        total = int(delta.total_seconds())
        if total < 0:
            return "0s"
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}h {m}m"
        if m:
            return f"{m}m {s}s"
        return f"{s}s"

    def _isoformat(dt) -> str | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    sessions_data = [
        {
            "id":           s.id,
            "username":     s.username,
            "client_ip":    s.client_ip or "—",
            "virtual_ip":   s.virtual_ip or "—",
            "country":      s.country or "??",
            "country_name": s.country_name or "Unknown",
            "bytes_in":     _fmt_bytes(s.bytes_in or 0),
            "bytes_in_raw": s.bytes_in or 0,
            "bytes_out":    _fmt_bytes(s.bytes_out or 0),
            "bytes_out_raw": s.bytes_out or 0,
            "connected_at": _isoformat(s.connected_at),
            "duration":     _duration(s.connected_at),
        }
        for s in sessions_q
    ]

    payload: dict = {
        "type":            "snapshot",
        "ts":              now.isoformat(),
        "active_sessions": sessions_data,
        "session_count":   len(sessions_data),
    }

    # Admin-only counters
    if is_admin:
        total_users = db.query(User).filter(User.is_active == True).count()
        vpn_users   = db.query(User).filter(
            User.vpn_enabled == True, User.is_active == True
        ).count()
        traffic = db.query(
            func.coalesce(func.sum(VPNSession.bytes_in),  0),
            func.coalesce(func.sum(VPNSession.bytes_out), 0),
        ).first()
        payload["total_users"]  = total_users
        payload["vpn_users"]    = vpn_users
        payload["total_bytes_in"]  = _fmt_bytes(int(traffic[0]))
        payload["total_bytes_out"] = _fmt_bytes(int(traffic[1]))

    return payload


# ── Event relay (called from event bus subscribers) ───────────────────────────

async def _relay_event(event_type: str, data: dict) -> None:
    """Push a domain event frame to all connected admin clients."""
    payload = {
        "type":       "event",
        "event":      event_type,
        "data":       data,
        "ts":         datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast(payload, channel="events")


def relay_event_sync(event_type: str, data: dict) -> None:
    """
    Thread-safe wrapper — called from the synchronous event bus handlers.
    Schedules ``_relay_event`` onto the running asyncio event loop.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(_relay_event(event_type, data), loop)
    except RuntimeError:
        pass  # No loop yet (startup / test context) — skip silently


# ── Register event bus hooks ──────────────────────────────────────────────────

def register_ws_event_relays() -> None:
    """Wire up event bus → WebSocket relay.  Called once from main.py lifespan."""
    from app.infrastructure.events.bus import bus, Events

    @bus.on(Events.VPN_SESSION_STARTED)
    def _on_vpn_start(p):
        relay_event_sync("vpn_connect", p)

    @bus.on(Events.VPN_SESSION_ENDED)
    def _on_vpn_end(p):
        relay_event_sync("vpn_disconnect", p)

    @bus.on(Events.USER_CREATED)
    def _on_user_created(p):
        relay_event_sync("user_created", p)

    @bus.on(Events.USER_DELETED)
    def _on_user_deleted(p):
        relay_event_sync("user_deleted", p)

    @bus.on(Events.AUTH_LOGIN_FAILED)
    def _on_login_failed(p):
        relay_event_sync("login_failed", p)

    @bus.on(Events.NODE_OFFLINE)
    def _on_node_offline(p):
        relay_event_sync("node_offline", p)

    @bus.on(Events.NODE_ONLINE)
    def _on_node_online(p):
        relay_event_sync("node_online", p)

    log.info("WS event relays registered")


# ── Main WebSocket endpoint ───────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    token: str = Query(..., description="JWT bearer token"),
):
    # ── 1. Authenticate ───────────────────────────────────────────────────────
    payload = _validate_token(token)
    if not payload:
        await ws.accept()
        await ws.send_text(json.dumps({"type": "error", "message": "Invalid or expired token"}))
        await ws.close(code=4001)
        return

    username = payload["sub"]

    with SessionLocal() as db:
        user = _get_user(username, db)
        if not user:
            await ws.accept()
            await ws.send_text(json.dumps({"type": "error", "message": "User not found or disabled"}))
            await ws.close(code=4003)
            return
        is_admin = user.is_admin
        user_id  = user.id

    # ── 2. Register connection ─────────────────────────────────────────────────
    await manager.connect(ws, channels={"all", "events"})
    log.info(f"WS connected: user={username} admin={is_admin} total={manager.count}")

    # ── 3. Send initial snapshot immediately ──────────────────────────────────
    try:
        with SessionLocal() as db:
            snap = _build_snapshot(db, is_admin, user_id)
        await manager.send_personal(ws, snap)
    except Exception as exc:
        log.warning(f"WS initial snapshot failed for {username}: {exc}")

    # ── 4. Main loop — push snapshots + handle pings ──────────────────────────
    push_tick  = 0
    ping_tick  = 0

    try:
        while True:
            # Non-blocking read with a 1-second timeout so we can push on schedule
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=1.0)
                if raw.strip().lower() == "pong":
                    pass  # keepalive reply — nothing to do
                # Future: handle client commands here
            except asyncio.TimeoutError:
                pass  # expected — just means no client message this tick
            except WebSocketDisconnect:
                raise

            push_tick += 1
            ping_tick += 1

            # Push session snapshot every PUSH_INTERVAL ticks (each tick ≈ 1 s)
            if push_tick >= PUSH_INTERVAL:
                push_tick = 0
                try:
                    with SessionLocal() as db:
                        snap = _build_snapshot(db, is_admin, user_id)
                    await manager.send_personal(ws, snap)
                except Exception as exc:
                    log.warning(f"WS snapshot push failed for {username}: {exc}")

            # Server keepalive ping every PING_INTERVAL ticks
            if ping_tick >= PING_INTERVAL:
                ping_tick = 0
                try:
                    await manager.send_personal(ws, {
                        "type": "ping",
                        "ts":   datetime.now(timezone.utc).isoformat(),
                    })
                except Exception:
                    break  # client gone

    except WebSocketDisconnect:
        log.info(f"WS disconnected: user={username}")
    except Exception as exc:
        log.warning(f"WS loop error for {username}: {exc}")
    finally:
        await manager.disconnect(ws)
        log.info(f"WS cleaned up: user={username} remaining={manager.count}")

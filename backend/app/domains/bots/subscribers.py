"""GhostWire — Bot notification subscribers (Phase 4)

Subscribes to the in-process event bus and fires bot notifications
for the events that matter. Imported once in main.py lifespan.
"""
import logging
from app.infrastructure.events.bus import bus, Events

log = logging.getLogger("ghostwire.bots.subscribers")


def _notify(event_type: str, message: str) -> None:
    """Fire-and-forget bot notify — swallows errors so it never breaks the caller."""
    try:
        from app.infrastructure.db import SessionLocal
        from app.domains.bots.service import notify
        with SessionLocal() as db:
            notify(db, event_type, message)
    except Exception as exc:
        log.error(f"Bot subscriber error for {event_type}: {exc}")


def register_subscribers() -> None:
    """Register all bot notification handlers onto the event bus."""

    @bus.on(Events.VPN_SESSION_STARTED)
    def on_vpn_connect(p: dict):
        username = p.get("username", "?")
        ip       = p.get("client_ip", "?")
        country  = p.get("country_name", "")
        _notify("vpn_connect", f"🟢 <b>{username}</b> connected to VPN\n📍 {ip} {country}")

    @bus.on(Events.VPN_SESSION_ENDED)
    def on_vpn_disconnect(p: dict):
        username = p.get("username", "?")
        duration = p.get("duration", "")
        _notify("vpn_disconnect", f"🔴 <b>{username}</b> disconnected from VPN{f' — {duration}' if duration else ''}")

    @bus.on(Events.USER_CREATED)
    def on_user_created(p: dict):
        username = p.get("username", "?")
        _notify("user_created", f"👤 New user created: <b>{username}</b>")

    @bus.on(Events.USER_DELETED)
    def on_user_deleted(p: dict):
        username = p.get("username", "?")
        _notify("user_deleted", f"🗑 User deleted: <b>{username}</b>")

    @bus.on(Events.AUTH_LOGIN_FAILED)
    def on_login_failed(p: dict):
        username = p.get("username", "?")
        ip       = p.get("ip", "?")
        _notify("login_failed", f"⚠️ Failed login attempt for <b>{username}</b> from {ip}")

    @bus.on(Events.AUTH_LOGIN_SUCCESS)
    def on_login_success(p: dict):
        username = p.get("username", "?")
        ip       = p.get("ip", "?")
        _notify("login_success", f"✅ <b>{username}</b> logged in from {ip}")

    @bus.on(Events.NODE_ADDED)
    def on_node_added(p: dict):
        name = p.get("name", "?")
        _notify("system_alert", f"🖥 New node registered: <b>{name}</b>")

    log.info("Bot subscribers registered")

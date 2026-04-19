"""GhostWire — Bot notification subscribers (Phase 4)

Subscribes to the in-process event bus and fires bot notifications
for the events that matter. Imported once in main.py lifespan.

Messages use HTML tags (<b>, <i>) as the canonical format.
The bot service layer (service.py) converts them per platform:
  • Telegram  → HTML passthrough (parse_mode=HTML)
  • Discord   → **markdown**
  • Slack     → *mrkdwn*
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
        username = p.get("username", "unknown")
        ip       = p.get("client_ip", "?")
        country  = p.get("country_name", "")
        loc      = f" ({country})" if country else ""
        _notify("vpn_connect",
                f"🟢 <b>{username}</b> connected to VPN\n"
                f"📍 IP: {ip}{loc}")

    @bus.on(Events.VPN_SESSION_ENDED)
    def on_vpn_disconnect(p: dict):
        username = p.get("username", "unknown")
        duration = p.get("duration", "")
        dur_str  = f"\n⏱ Duration: {duration}" if duration else ""
        _notify("vpn_disconnect",
                f"🔴 <b>{username}</b> disconnected from VPN{dur_str}")

    @bus.on(Events.USER_CREATED)
    def on_user_created(p: dict):
        username = p.get("username", "unknown")
        _notify("user_created",
                f"👤 New user created: <b>{username}</b>")

    @bus.on(Events.USER_DELETED)
    def on_user_deleted(p: dict):
        username = p.get("username", "unknown")
        _notify("user_deleted",
                f"🗑️ User deleted: <b>{username}</b>")

    @bus.on(Events.AUTH_LOGIN_FAILED)
    def on_login_failed(p: dict):
        username = p.get("username", "unknown")
        ip       = p.get("ip", "?")
        _notify("login_failed",
                f"⚠️ Failed login: <b>{username}</b>\n"
                f"📍 From: {ip}")

    @bus.on(Events.AUTH_LOGIN_SUCCESS)
    def on_login_success(p: dict):
        username = p.get("username", "unknown")
        ip       = p.get("ip", "?")
        _notify("login_success",
                f"✅ <b>{username}</b> logged in\n"
                f"📍 From: {ip}")

    @bus.on(Events.NODE_ADDED)
    def on_node_added(p: dict):
        name     = p.get("name", "unknown")
        hostname = p.get("hostname", "")
        host_str = f"\n🌐 Host: {hostname}" if hostname else ""
        _notify("system_alert",
                f"🖥️ New node registered: <b>{name}</b>{host_str}")

    log.info("Bot subscribers registered")

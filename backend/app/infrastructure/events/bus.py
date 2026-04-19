"""GhostWire — In-process event bus

Lightweight publish/subscribe bus that keeps domains decoupled.
Any domain can emit an event; any other domain can subscribe without
importing from the emitter — no circular dependencies.

Usage:
    # Publisher (e.g. users domain)
    from app.infrastructure.events import bus
    bus.emit("user.created", {"user_id": uid, "username": name})

    # Subscriber (e.g. notifications domain in Phase 4)
    from app.infrastructure.events import bus
    @bus.on("user.created")
    def handle_user_created(payload: dict):
        send_welcome_notification(payload["username"])

Thread safety: handlers run synchronously in the emitter's thread.
For async handlers, wrap with asyncio.create_task in Phase 3+.
"""
import logging
from collections import defaultdict
from typing import Callable

log = logging.getLogger("ghostwire.events")


class EventBus:
    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def on(self, event: str) -> Callable:
        """Decorator to register a handler for an event."""
        def decorator(fn: Callable) -> Callable:
            self._handlers[event].append(fn)
            log.debug(f"EventBus: handler registered for '{event}': {fn.__qualname__}")
            return fn
        return decorator

    def subscribe(self, event: str, fn: Callable) -> None:
        """Programmatic subscription (no decorator)."""
        self._handlers[event].append(fn)
        log.debug(f"EventBus: subscribed '{fn.__qualname__}' to '{event}'")

    def emit(self, event: str, payload: dict | None = None) -> None:
        """Fire all handlers registered for event. Errors are caught and logged."""
        handlers = self._handlers.get(event, [])
        if not handlers:
            log.debug(f"EventBus: no handlers for '{event}'")
            return
        for handler in handlers:
            try:
                handler(payload or {})
            except Exception as exc:
                log.error(f"EventBus: handler {handler.__qualname__} for '{event}' raised: {exc}")

    def clear(self, event: str | None = None) -> None:
        """Remove handlers — primarily for testing."""
        if event:
            self._handlers.pop(event, None)
        else:
            self._handlers.clear()


# Singleton bus — import this everywhere
bus = EventBus()

# ── Well-known event names (document the contract, prevent typos) ─────────────
# Phase 1 seeds — expand in later phases

class Events:
    # Users domain
    USER_CREATED    = "user.created"
    USER_UPDATED    = "user.updated"
    USER_DELETED    = "user.deleted"
    USER_VPN_TOGGLED = "user.vpn_toggled"

    # Auth domain
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILED  = "auth.login.failed"
    AUTH_PASSWORD_CHANGED = "auth.password.changed"

    # VPN domain
    VPN_SESSION_STARTED = "vpn.session.started"
    VPN_SESSION_ENDED   = "vpn.session.ended"
    VPN_RESTARTED       = "vpn.restarted"

    # System domain
    SYSTEM_CERT_REGENERATED   = "system.cert.regenerated"
    SYSTEM_IP_CHANGED         = "system.ip.changed"
    SYSTEM_PROFILE_UPDATE_REQ = "system.profile.update_required"

    # 2FA domain (Phase 2)
    AUTH_2FA_ENABLED   = "auth.2fa.enabled"
    AUTH_2FA_DISABLED  = "auth.2fa.disabled"
    AUTH_2FA_CHALLENGE = "auth.2fa.challenge"
    AUTH_2FA_SUCCESS   = "auth.2fa.success"
    AUTH_2FA_FAILED    = "auth.2fa.failed"

    # API keys domain (Phase 2)
    APIKEY_CREATED = "apikey.created"
    APIKEY_REVOKED = "apikey.revoked"

    # Custom fields domain (Phase 2)
    CUSTOMFIELDS_SCHEMA_UPDATED = "customfields.schema.updated"

    # DNS domain (Phase 3)
    DNS_BLOCKLIST_SYNCED          = "dns.blocklist.synced"
    DNS_USER_SETTINGS_UPDATED     = "dns.user_settings.updated"
    DNS_QUERY_BLOCKED             = "dns.query.blocked"
    DNS_QUERY_ALLOWED             = "dns.query.allowed"
    DNS_OVERRIDE_ADDED            = "dns.override.added"

    # Nodes domain (Phase 4)
    NODE_ADDED      = "node.added"
    NODE_UPDATED    = "node.updated"
    NODE_REMOVED    = "node.removed"
    NODE_OFFLINE    = "node.offline"
    NODE_ONLINE     = "node.online"

    # Bots domain (Phase 4)
    BOT_MESSAGE_SENT   = "bot.message.sent"
    BOT_MESSAGE_FAILED = "bot.message.failed"

    # Plugins domain (Phase 5)
    PLUGIN_ACTIVATED   = "plugin.activated"
    PLUGIN_DEACTIVATED = "plugin.deactivated"
    PLUGIN_DELETED     = "plugin.deleted"

    # Themes domain (Phase 5)
    THEME_ACTIVATED    = "theme.activated"
    THEME_CREATED      = "theme.created"

    # Backup domain (Phase 5)
    BACKUP_CREATED     = "backup.created"
    BACKUP_RESTORED    = "backup.restored"


# Convenience aliases for code that imports as `from app.infrastructure.events.bus import event_bus, AppEvent`
AppEvent   = Events
event_bus  = bus

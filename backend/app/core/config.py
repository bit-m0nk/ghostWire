"""GhostWire — Centralised settings (loaded from .env)

All configurable values live here. Defaults target a fresh Pi install.
Postgres support: set DB_URL=postgresql://user:pass@host/dbname in .env.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Identity ──────────────────────────────────────────────────────────────
    VPN_BRAND:    str = "GhostWire"
    INSTALL_DIR:  str = "/opt/ghostwire"
    PANEL_PORT:   int = 8080

    # ── Database ──────────────────────────────────────────────────────────────
    # Override with DB_URL=postgresql://... in .env for Postgres (Phase 4)
    DB_PATH:      str = "/opt/ghostwire/data/ghostwire.db"
    DB_URL:       str = ""   # if set, takes priority over DB_PATH

    # ── VPN / Network ─────────────────────────────────────────────────────────
    CERTS_DIR:      str = "/etc/swanctl"
    SWANCTL_CONF:   str = "/etc/swanctl/conf.d/ghostwire.conf"
    LOG_DIR:      str = "/var/log/ghostwire"
    LOCAL_IP:     str = "127.0.0.1"
    PUBLIC_IP:    str = "127.0.0.1"
    WAN_IFACE:    str = "eth0"
    VPN_SUBNET:   str = "10.10.0.0/24"
    PSK:          str = ""

    # ── DDNS ──────────────────────────────────────────────────────────────────
    USE_DDNS:           str = "false"
    DDNS_PRIMARY:       str = "dynu"
    DDNS_HOSTNAME:      str = ""
    DYNU_HOSTNAME:      str = ""
    DYNU_USERNAME:      str = ""
    DYNU_IP_UPDATE_PASS:str = ""
    NOIP_HOSTNAME:      str = ""
    NOIP_USERNAME:      str = ""
    NOIP_PASSWORD:      str = ""

    # ── Notifications ─────────────────────────────────────────────────────────
    TG_BOT_TOKEN:  str = ""
    TG_CHAT_ID:    str = ""
    SMTP_HOST:     str = ""
    SMTP_PORT:     int = 587
    SMTP_USER:     str = ""
    SMTP_PASS:     str = ""
    NOTIFY_EMAIL:  str = ""

    # ── Security ──────────────────────────────────────────────────────────────
    JWT_SECRET:        str = "changeme"
    JWT_EXPIRE_HOURS:  int = 24

    # ── GeoIP ─────────────────────────────────────────────────────────────────
    GEOIP_DB: str = "/opt/ghostwire/data/GeoLite2-Country.mmdb"

    # ── Computed properties ───────────────────────────────────────────────────

    @property
    def database_url(self) -> str:
        """Postgres if DB_URL is set, otherwise SQLite."""
        if self.DB_URL:
            return self.DB_URL
        return f"sqlite:///{self.DB_PATH}"

    @property
    def server_hostname(self) -> str:
        if self.ddns_enabled and self.DDNS_HOSTNAME:
            return self.DDNS_HOSTNAME
        return self.PUBLIC_IP

    @property
    def ddns_enabled(self) -> bool:
        return self.USE_DDNS.lower() == "true"

    @property
    def dynu_configured(self) -> bool:
        return bool(self.DYNU_HOSTNAME and self.DYNU_USERNAME and self.DYNU_IP_UPDATE_PASS)

    @property
    def noip_configured(self) -> bool:
        return bool(self.NOIP_HOSTNAME and self.NOIP_USERNAME and self.NOIP_PASSWORD)

    class Config:
        env_file = "/opt/ghostwire/.env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

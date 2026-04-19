"""GhostWire — Configuration management routes (config domain)"""
import logging
import smtplib
import ssl
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import require_admin
from app.domains.users.models import User
from app.services.config_service import (
    get_smtp_config, get_ddns_config, get_notification_config, write_env
)

router = APIRouter()
log = logging.getLogger("ghostwire.config")


class SmtpUpdate(BaseModel):
    host:         str
    port:         int  = 587
    user:         str  = ""
    password:     Optional[str] = None
    tls:          str  = "starttls"
    from_addr:    str  = ""
    notify_email: str  = ""


class DdnsUpdate(BaseModel):
    use_ddns:            bool = False
    ddns_primary:        str  = "dynu"
    ddns_hostname:       str  = ""
    dynu_hostname:       str  = ""
    dynu_username:       str  = ""
    dynu_ip_update_pass: Optional[str] = None
    noip_hostname:       str  = ""
    noip_username:       str  = ""
    noip_password:       Optional[str] = None


class NotificationUpdate(BaseModel):
    tg_bot_token: Optional[str] = None
    tg_chat_id:   str = ""
    notify_email: str = ""


# ── SMTP ──────────────────────────────────────────────────────────────────────

@router.get("/smtp")
async def get_smtp(admin: User = Depends(require_admin)):
    cfg = get_smtp_config()
    if not cfg:
        return {
            "configured": False,
            "host": "", "port": 587, "user": "", "tls": "starttls",
            "from_addr": "", "notify_email": "",
        }
    return {
        "configured":   True,
        "host":         cfg["host"],
        "port":         cfg["port"],
        "user":         cfg["user"],
        "tls":          cfg["tls"],
        "from_addr":    cfg["from"],
        "notify_email": cfg["notify_email"],
        "has_password": bool(cfg["password"]),
    }


@router.post("/smtp")
async def update_smtp(data: SmtpUpdate, admin: User = Depends(require_admin)):
    updates: dict[str, str] = {
        "SMTP_HOST":    data.host.strip(),
        "SMTP_PORT":    str(data.port),
        "SMTP_USER":    data.user.strip(),
        "SMTP_TLS":     data.tls.strip(),
        "NOTIFY_EMAIL": data.notify_email.strip(),
    }
    if data.from_addr.strip():
        updates["SMTP_FROM"] = data.from_addr.strip()
    if data.password is not None:
        updates["SMTP_PASS"] = data.password
    try:
        write_env(updates)
    except Exception as e:
        raise HTTPException(500, f"Failed to write config: {e}")
    return {"message": "SMTP settings saved", "configured": bool(data.host.strip())}


@router.post("/smtp/test")
async def test_smtp(admin: User = Depends(require_admin)):
    cfg = get_smtp_config()
    if not cfg:
        raise HTTPException(400, "SMTP is not configured")
    if not cfg.get("notify_email"):
        raise HTTPException(400, "Set NOTIFY_EMAIL first")
    try:
        _send_test_email(cfg)
        return {"message": f"Test email sent to {cfg['notify_email']}"}
    except Exception as e:
        raise HTTPException(500, f"SMTP test failed: {e}")


def _send_test_email(cfg: dict) -> None:
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{cfg['brand']}] SMTP Test — configuration works ✓"
    msg["From"]    = f"{cfg['brand']} <{cfg['from']}>"
    msg["To"]      = cfg["notify_email"]
    msg.attach(MIMEText(
        f"SMTP is correctly configured for {cfg['brand']} VPN.\n\n"
        f"Server: {cfg['host']}:{cfg['port']} ({cfg['tls']})\n"
        f"Account: {cfg['user']}", "plain"
    ))

    tls_mode = cfg["tls"]
    if tls_mode == "ssl":
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=ctx) as s:
            if cfg["user"]:
                s.login(cfg["user"], cfg["password"])
            s.sendmail(cfg["from"], [cfg["notify_email"]], msg.as_string())
    else:
        with smtplib.SMTP(cfg["host"], cfg["port"]) as s:
            if tls_mode == "starttls":
                s.starttls(context=ssl.create_default_context())
            if cfg["user"]:
                s.login(cfg["user"], cfg["password"])
            s.sendmail(cfg["from"], [cfg["notify_email"]], msg.as_string())


# ── DDNS ──────────────────────────────────────────────────────────────────────

@router.get("/ddns")
async def get_ddns(admin: User = Depends(require_admin)):
    return get_ddns_config()


@router.post("/ddns")
async def update_ddns(data: DdnsUpdate, admin: User = Depends(require_admin)):
    updates: dict[str, str] = {
        "USE_DDNS":      "true" if data.use_ddns else "false",
        "DDNS_PRIMARY":  data.ddns_primary.strip() or "dynu",
        "DDNS_HOSTNAME": data.ddns_hostname.strip(),
        "DYNU_HOSTNAME": data.dynu_hostname.strip(),
        "DYNU_USERNAME": data.dynu_username.strip(),
        "NOIP_HOSTNAME": data.noip_hostname.strip(),
        "NOIP_USERNAME": data.noip_username.strip(),
    }
    if data.dynu_ip_update_pass is not None:
        updates["DYNU_IP_UPDATE_PASS"] = data.dynu_ip_update_pass
    if data.noip_password is not None:
        updates["NOIP_PASSWORD"] = data.noip_password
    try:
        write_env(updates)
    except Exception as e:
        raise HTTPException(500, f"Failed to write config: {e}")
    return {"message": "DDNS settings saved"}


# ── Notifications ─────────────────────────────────────────────────────────────

@router.get("/notifications")
async def get_notifications(admin: User = Depends(require_admin)):
    return get_notification_config()


@router.post("/notifications")
async def update_notifications(
    data: NotificationUpdate,
    admin: User = Depends(require_admin),
):
    updates: dict[str, str] = {
        "TG_CHAT_ID":   data.tg_chat_id.strip(),
        "NOTIFY_EMAIL": data.notify_email.strip(),
    }
    if data.tg_bot_token is not None:
        updates["TG_BOT_TOKEN"] = data.tg_bot_token
    try:
        write_env(updates)
    except Exception as e:
        raise HTTPException(500, f"Failed to write config: {e}")
    return {"message": "Notification settings saved"}


# ── Combined status ───────────────────────────────────────────────────────────

@router.get("/status")
async def config_status(admin: User = Depends(require_admin)):
    smtp  = get_smtp_config()
    ddns  = get_ddns_config()
    notif = get_notification_config()
    return {
        "smtp": {
            "configured": smtp is not None,
            "host":       smtp["host"] if smtp else "",
        },
        "ddns": {
            "enabled":  ddns["use_ddns"],
            "provider": ddns["ddns_primary"],
            "hostname": ddns["ddns_hostname"],
        },
        "telegram": {
            "configured": notif["tg_enabled"],
        },
    }

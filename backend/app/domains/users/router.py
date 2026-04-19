"""GhostWire — User management routes (users domain, admin only)"""
import re
import secrets
import string
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import Optional, List

from app.infrastructure.db import get_db
from app.domains.users.models import User
from app.domains.audit.models import AuditLog
from app.core.security import hash_password, require_admin
from app.infrastructure.events import bus, Events

router = APIRouter()

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{3,32}$")
_EMAIL_RE    = re.compile(r"^[^\@\s]+@[^\@\s]+\.[^\@\s]+$")


def _rand_pass(length: int = 16) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(chars) for _ in range(length))


def _rand_vpn_user(base: str) -> str:
    safe = re.sub(r"[^a-z0-9]", "", base.lower())[:12] or "user"
    return safe + "_" + secrets.token_hex(3)


def _audit(db, actor, action, target, ip="", level="info"):
    db.add(AuditLog(actor=actor, action=action, target=target,
                    ip_address=ip, level=level))
    db.commit()


def _user_dict(u: User) -> dict:
    return {
        "id":                  u.id,
        "username":            u.username,
        "full_name":           u.full_name,
        "email":               u.email,
        "is_admin":            u.is_admin,
        "is_active":           u.is_active,
        "vpn_enabled":         u.vpn_enabled,
        "vpn_username":        u.vpn_username,
        "created_at":          u.created_at,
        "updated_at":          u.updated_at,
        "last_login":          u.last_login,
        "notes":               u.notes,
        "bandwidth_limit_gb":  u.bandwidth_limit_gb,
        # Phase 2
        "totp_enabled":        u.totp_enabled,
        "has_custom_fields":   bool(u.custom_fields),
    }


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username:           str
    full_name:          str
    email:              str
    password:           Optional[str] = None
    vpn_password:       Optional[str] = None
    is_admin:           bool          = False
    vpn_enabled:        bool          = True
    notes:              Optional[str] = ""
    bandwidth_limit_gb: Optional[str] = "0"
    send_email:         bool          = False

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        v = v.strip()
        if not _USERNAME_RE.match(v):
            raise ValueError("Username must be 3–32 characters: letters, numbers, _ or -")
        return v

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v):
        v = v.strip()
        if not v or len(v) < 2:
            raise ValueError("Full name must be at least 2 characters")
        if len(v) > 128:
            raise ValueError("Full name must be under 128 characters")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v

    @field_validator("password", "vpn_password", mode="before")
    @classmethod
    def validate_password(cls, v):
        if v == "" or v is None:
            return None
        v = str(v).strip()
        if not v:
            return None
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must be under 128 characters")
        return v


class UserUpdate(BaseModel):
    full_name:          Optional[str]  = None
    email:              Optional[str]  = None
    is_active:          Optional[bool] = None
    vpn_enabled:        Optional[bool] = None
    notes:              Optional[str]  = None
    bandwidth_limit_gb: Optional[str]  = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if v is not None:
            v = v.strip().lower()
            if not _EMAIL_RE.match(v):
                raise ValueError("Invalid email address")
        return v


class ResetPassword(BaseModel):
    new_password: Optional[str] = None
    send_connection_package: bool = False   # also re-send connection package email

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v):
        if v is not None and len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/smtp-status")
async def smtp_status(admin: User = Depends(require_admin)):
    from app.services.config_service import get_smtp_config
    cfg = get_smtp_config()
    if cfg:
        return {"configured": True, "host": cfg["host"], "port": cfg["port"], "from": cfg["from"]}
    return {"configured": False, "message": "SMTP not configured — use the Config page to set it up"}


@router.get("/", response_model=List[dict])
async def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return [_user_dict(u) for u in
            db.query(User).order_by(User.created_at.desc()).all()]


@router.post("/", status_code=201)
async def create_user(
    data: UserCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(409, "Username already exists")
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(409, "Email already exists")

    plain_pass = data.password or _rand_pass()
    vpn_pass   = data.vpn_password or _rand_pass(14)
    vpn_user   = _rand_vpn_user(data.username)

    user = User(
        username=data.username,
        full_name=data.full_name,
        email=data.email,
        hashed_password=hash_password(plain_pass),
        is_admin=data.is_admin,
        vpn_enabled=data.vpn_enabled,
        vpn_username=vpn_user,
        vpn_password=hash_password(vpn_pass),
        notes=data.notes or "",
        bandwidth_limit_gb=data.bandwidth_limit_gb or "0",
    )
    db.add(user)
    db.flush()

    if data.vpn_enabled:
        _write_vpn_secret(vpn_user, vpn_pass)

    db.commit()
    _audit(db, admin.username, "CREATE_USER", data.username, request.client.host)

    # Emit event for other domains to react (notifications, etc.)
    bus.emit(Events.USER_CREATED, {
        "user_id":  user.id,
        "username": user.username,
        "email":    user.email,
    })

    email_status = None
    if data.send_email and data.email:
        from app.services.email_service import send_welcome_emails
        from app.services.config_service import get_smtp_config
        from app.core.config import settings
        smtp_ok = get_smtp_config() is not None
        if smtp_ok:
            panel_url = f"http://{settings.server_hostname}:{settings.PANEL_PORT}"
            ok, msg = send_welcome_emails(
                to_email        = data.email,
                full_name       = data.full_name,
                username        = data.username,
                panel_password  = plain_pass,
                vpn_username    = vpn_user,
                vpn_password    = vpn_pass,
                server_hostname = settings.server_hostname,
                panel_url       = panel_url,
                brand           = settings.VPN_BRAND,
            )
            email_status = {"sent": ok, "message": msg}
        else:
            email_status = {"sent": False, "message": "SMTP not configured"}

    return {
        **_user_dict(user),
        "panel_password": plain_pass,
        "vpn_username":   vpn_user,
        "vpn_password":   vpn_pass,
        "_notice": "Save these credentials now — passwords cannot be recovered later",
        "email_status": email_status,
    }


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return _user_dict(user)


@router.patch("/{user_id}")
async def update_user(
    user_id: str,
    data: UserUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    was_vpn_enabled = user.vpn_enabled
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    if was_vpn_enabled and data.vpn_enabled is False:
        _remove_vpn_secret(user.vpn_username)

    db.commit()
    _audit(db, admin.username, "UPDATE_USER", user.username, request.client.host)
    bus.emit(Events.USER_UPDATED, {"user_id": user.id, "username": user.username})
    return _user_dict(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if user.is_admin:
        raise HTTPException(400, "Cannot delete admin users")
    if user.id == admin.id:
        raise HTTPException(400, "Cannot delete your own account")

    _remove_vpn_secret(user.vpn_username)
    _audit(db, admin.username, "DELETE_USER", user.username,
           request.client.host, "warning")
    bus.emit(Events.USER_DELETED, {"user_id": user.id, "username": user.username})
    db.delete(user)
    db.commit()


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    data: ResetPassword,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    new_pass = data.new_password or _rand_pass()
    user.hashed_password = hash_password(new_pass)
    user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    _audit(db, admin.username, "RESET_PANEL_PASSWORD", user.username,
           request.client.host, "warning")

    email_status = None
    if data.send_connection_package and user.email:
        from app.services.email_service import send_connection_package_email
        from app.services.config_service import get_smtp_config
        from app.core.config import settings
        if get_smtp_config():
            panel_url = f"http://{settings.server_hostname}:{settings.PANEL_PORT}"
            ok, msg = send_connection_package_email(
                to_email        = user.email,
                full_name       = user.full_name,
                username        = user.username,
                vpn_username    = user.vpn_username or "",
                server_hostname = settings.server_hostname,
                panel_url       = panel_url,
                brand           = settings.VPN_BRAND,
            )
            email_status = {"sent": ok, "message": msg}
        else:
            email_status = {"sent": False, "message": "SMTP not configured"}

    return {
        "new_password": new_pass,
        "message": "Panel password reset — share securely",
        "email_status": email_status,
    }


@router.post("/{user_id}/reset-vpn-password")
async def reset_vpn_password(
    user_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if not user.vpn_username:
        raise HTTPException(400, "User has no VPN credentials assigned")

    new_vpn_pass = _rand_pass(14)
    user.vpn_password = hash_password(new_vpn_pass)
    user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    _write_vpn_secret(user.vpn_username, new_vpn_pass)
    _audit(db, admin.username, "RESET_VPN_PASSWORD", user.username,
           request.client.host, "warning")

    email_status = None
    if user.email:
        from app.services.email_service import send_connection_package_email
        from app.services.config_service import get_smtp_config
        from app.core.config import settings
        if get_smtp_config():
            panel_url = f"http://{settings.server_hostname}:{settings.PANEL_PORT}"
            ok, msg = send_connection_package_email(
                to_email        = user.email,
                full_name       = user.full_name,
                username        = user.username,
                vpn_username    = user.vpn_username,
                server_hostname = settings.server_hostname,
                panel_url       = panel_url,
                brand           = settings.VPN_BRAND,
            )
            email_status = {"sent": ok, "message": msg}

    return {
        "vpn_username": user.vpn_username,
        "vpn_password": new_vpn_pass,
        "message": "VPN credentials reset — user must re-download config profiles",
        "email_status": email_status,
    }


@router.post("/{user_id}/toggle-vpn")
async def toggle_vpn(
    user_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    user.vpn_enabled = not user.vpn_enabled
    user.updated_at  = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    if not user.vpn_enabled:
        _remove_vpn_secret(user.vpn_username)

    action = "VPN_ENABLED" if user.vpn_enabled else "VPN_DISABLED"
    _audit(db, admin.username, action, user.username, request.client.host)
    bus.emit(Events.USER_VPN_TOGGLED, {
        "user_id":    user.id,
        "username":   user.username,
        "vpn_enabled": user.vpn_enabled,
    })

    msg = "VPN access enabled" if user.vpn_enabled else "VPN access disabled"
    if user.vpn_enabled:
        msg += " — user must reset VPN password to get fresh credentials"
    return {"vpn_enabled": user.vpn_enabled, "message": msg}


# ── strongSwan secrets helpers ────────────────────────────────────────────────

def _sanitise(s: str) -> str:
    return re.sub(r'["\n\r\\]', "", s)


def _write_vpn_secret(username: str, password: str) -> None:
    """
    Write an EAP user secret into the swanctl.conf secrets block and hot-reload.

    swanctl EAP secrets format (inside the top-level secrets {} block):

        eap-<username> {        # section name — must be unique per user
            id     = <username>
            secret = "<password>"
        }

    We bracket each user block with a pair of marker comments so the remove
    function can surgically delete just that user's block later.
    """
    import subprocess
    import logging
    from app.core.config import settings as _s
    log = logging.getLogger("ghostwire.users")

    if not username or not password:
        log.warning("_write_vpn_secret called with empty username or password — skipped")
        return

    safe_user = _sanitise(username)
    safe_pass = _sanitise(password)

    conf_path = _s.SWANCTL_CONF
    open_marker  = f"    # ghostwire-user:{safe_user}"
    close_marker = f"    # ghostwire-user-end:{safe_user}"

    new_block = [
        open_marker,
        f"    eap-{safe_user} {{",
        f'        id     = {safe_user}',
        f'        secret = "{safe_pass}"',
        "    }",
        close_marker,
    ]

    try:
        try:
            content = open(conf_path).read()
        except FileNotFoundError:
            log.warning(f"swanctl conf not found at {conf_path} — cannot write EAP secret")
            _write_chap_secret(safe_user, safe_pass)
            return

        # Remove existing block for this user if present
        lines = content.splitlines()
        filtered = []
        skip = False
        for line in lines:
            if line.strip() == open_marker.strip():
                skip = True
                continue
            if skip and line.strip() == close_marker.strip():
                skip = False
                continue
            if not skip:
                filtered.append(line)

        # Inject the new block just before the closing `}` of the secrets {} section.
        # We look for the last `}` in the file (which closes the top-level secrets block).
        # If no secrets block exists at all, append one.
        content_out = "\n".join(filtered)
        if "secrets {" in content_out:
            # Find the closing brace of the secrets block
            secrets_start = content_out.rfind("secrets {")
            secrets_end   = content_out.find("\n}", secrets_start)
            if secrets_end != -1:
                insert_text = "\n" + "\n".join(new_block)
                content_out = (
                    content_out[:secrets_end]
                    + insert_text
                    + "\n"
                    + content_out[secrets_end:]
                )
            else:
                # Malformed — just append
                content_out += "\n" + "\n".join(new_block) + "\n"
        else:
            # No secrets block — create one
            content_out += "\nsecrets {\n" + "\n".join(new_block) + "\n}\n"

        with open(conf_path, "w") as f:
            f.write(content_out)

        subprocess.run(["swanctl", "--load-creds"], capture_output=True, timeout=5)
        log.info(f"VPN secret written for {safe_user}")
        _write_chap_secret(safe_user, safe_pass)
    except Exception as e:
        log.error(f"Failed to write VPN secret for {safe_user}: {e}")


def _remove_vpn_secret(username: str) -> None:
    """
    Remove an EAP user secret block from swanctl.conf and hot-reload credentials.
    """
    import subprocess
    import logging
    from app.core.config import settings as _s
    log = logging.getLogger("ghostwire.users")

    if not username:
        return

    safe_user    = _sanitise(username)
    conf_path    = _s.SWANCTL_CONF
    open_marker  = f"    # ghostwire-user:{safe_user}"
    close_marker = f"    # ghostwire-user-end:{safe_user}"

    try:
        try:
            lines = open(conf_path).readlines()
        except FileNotFoundError:
            return

        filtered   = []
        skip_block = False
        for line in lines:
            if line.strip() == open_marker.strip():
                skip_block = True
                continue
            if skip_block and line.strip() == close_marker.strip():
                skip_block = False
                continue
            if not skip_block:
                filtered.append(line)

        with open(conf_path, "w") as f:
            f.writelines(filtered)

        subprocess.run(["swanctl", "--load-creds"], capture_output=True, timeout=5)
        log.info(f"VPN secret removed for {safe_user}")
        _remove_chap_secret(safe_user)
    except Exception as e:
        log.error(f"Failed to remove VPN secret for {safe_user}: {e}")


def _write_chap_secret(username: str, password: str) -> None:
    import logging
    log = logging.getLogger("ghostwire.users")
    chap_file = "/etc/ppp/chap-secrets"
    marker = f"# ghostwire-user:{username}"
    try:
        try:
            content = open(chap_file).read()
        except FileNotFoundError:
            content = "# chap-secrets - secrets for authenticating users\n"
        lines = content.splitlines()
        filtered = [l for l in lines
                    if l.strip() != marker and not (username in l and "ghostwire" not in l and "*" in l)]
        filtered.append(marker)
        filtered.append(f'{username} * "{password}" *')
        with open(chap_file, "w") as f:
            f.write("\n".join(filtered) + "\n")
    except Exception as e:
        log.warning(f"CHAP secret write failed for {username}: {e}")


def _remove_chap_secret(username: str) -> None:
    import logging
    log = logging.getLogger("ghostwire.users")
    chap_file = "/etc/ppp/chap-secrets"
    marker = f"# ghostwire-user:{username}"
    try:
        try:
            lines = open(chap_file).readlines()
        except FileNotFoundError:
            return
        filtered = []
        skip = False
        for line in lines:
            if line.strip() == marker:
                skip = True
                continue
            if skip:
                skip = False
                continue
            filtered.append(line)
        with open(chap_file, "w") as f:
            f.writelines(filtered)
    except Exception as e:
        log.warning(f"CHAP secret removal failed for {username}: {e}")

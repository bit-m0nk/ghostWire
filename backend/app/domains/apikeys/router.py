"""GhostWire — API keys domain (Phase 2)

Users can generate named API keys for programmatic portal access.
Keys are shown once at creation, then only the bcrypt hash is stored.
Admin can see all keys for a user; users can only see their own.

Key format: gw_{32 random hex chars}
Prefix stored in plain for display: "gw_3f9a1b..."
"""
import secrets
import logging
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.db import get_db
from app.domains.users.models import User, UserAPIKey
from app.domains.audit.models import AuditLog
from app.core.security import get_current_user, require_admin

router = APIRouter()
log = logging.getLogger("ghostwire.apikeys")

_MAX_KEYS_PER_USER = 10


def _audit(db, actor, action, target, ip="", level="info"):
    db.add(AuditLog(actor=actor, action=action, target=target,
                    ip_address=ip, level=level))
    db.commit()


def _key_dict(k: UserAPIKey, show_hash: bool = False) -> dict:
    return {
        "id":         k.id,
        "name":       k.name,
        "key_prefix": k.key_prefix,
        "created_at": k.created_at,
        "last_used":  k.last_used,
        "is_active":  k.is_active,
    }


class KeyCreate(BaseModel):
    name: str   # human label, e.g. "Home script", "Monitoring"


# ── User: manage own keys ─────────────────────────────────────────────────────

@router.get("/my-keys")
async def list_my_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all API keys for the authenticated user."""
    keys = db.query(UserAPIKey).filter(
        UserAPIKey.user_id == current_user.id,
        UserAPIKey.is_active == True,
    ).order_by(UserAPIKey.created_at.desc()).all()
    return [_key_dict(k) for k in keys]


@router.post("/my-keys", status_code=201)
async def create_my_key(
    data: KeyCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new API key. The raw key is returned ONCE — store it now.
    Subsequent calls only show the prefix.
    """
    name = data.name.strip()[:64]
    if not name:
        raise HTTPException(400, "Key name is required")

    # Enforce per-user limit
    count = db.query(UserAPIKey).filter(
        UserAPIKey.user_id == current_user.id,
        UserAPIKey.is_active == True,
    ).count()
    if count >= _MAX_KEYS_PER_USER:
        raise HTTPException(400, f"Maximum {_MAX_KEYS_PER_USER} active API keys per user")

    # Generate key
    raw_key    = "gw_" + secrets.token_hex(32)
    key_prefix = raw_key[:11]   # "gw_" + first 8 hex chars
    key_hash   = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()

    api_key = UserAPIKey(
        user_id    = current_user.id,
        name       = name,
        key_hash   = key_hash,
        key_prefix = key_prefix,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    ip = request.client.host if request.client else "unknown"
    _audit(db, current_user.username, "API_KEY_CREATED", name, ip)
    log.info(f"API key '{name}' created for {current_user.username}")

    return {
        **_key_dict(api_key),
        "key": raw_key,   # shown ONCE — never returned again
        "_notice": "Copy this key now — it cannot be retrieved after this response",
    }


@router.delete("/my-keys/{key_id}", status_code=204)
async def revoke_my_key(
    key_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke (soft-delete) one of the authenticated user's API keys."""
    key = db.query(UserAPIKey).filter(
        UserAPIKey.id      == key_id,
        UserAPIKey.user_id == current_user.id,
    ).first()
    if not key:
        raise HTTPException(404, "API key not found")

    key.is_active = False
    db.commit()

    ip = request.client.host if request.client else "unknown"
    _audit(db, current_user.username, "API_KEY_REVOKED", key.name, ip, "warning")


# ── Admin: view/revoke any user's keys ────────────────────────────────────────

@router.get("/users/{user_id}/keys")
async def admin_list_keys(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    keys = db.query(UserAPIKey).filter(
        UserAPIKey.user_id == user_id,
    ).order_by(UserAPIKey.created_at.desc()).all()
    return [_key_dict(k) for k in keys]


@router.delete("/users/{user_id}/keys/{key_id}", status_code=204)
async def admin_revoke_key(
    user_id: str,
    key_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    key = db.query(UserAPIKey).filter(
        UserAPIKey.id      == key_id,
        UserAPIKey.user_id == user_id,
    ).first()
    if not key:
        raise HTTPException(404, "API key not found")

    key.is_active = False
    db.commit()

    ip = request.client.host if request.client else "unknown"
    _audit(db, admin.username, "ADMIN_REVOKE_API_KEY", f"{user_id}/{key.name}", ip, "warning")


# ── Key verification (used by auth middleware for API key auth) ───────────────

def verify_api_key(raw_key: str, db: Session) -> User | None:
    """
    Given a raw API key string, return the owning User if valid, else None.
    Used by optional bearer-token auth in the portal.
    """
    if not raw_key or not raw_key.startswith("gw_"):
        return None

    prefix = raw_key[:11]
    candidates = db.query(UserAPIKey).filter(
        UserAPIKey.key_prefix == prefix,
        UserAPIKey.is_active  == True,
    ).all()

    for key in candidates:
        try:
            if bcrypt.checkpw(raw_key.encode(), key.key_hash.encode()):
                # Update last_used timestamp (non-blocking)
                key.last_used = datetime.now(timezone.utc).replace(tzinfo=None)
                db.commit()
                user = db.query(User).filter(
                    User.id == key.user_id, User.is_active == True
                ).first()
                return user
        except Exception:
            continue
    return None

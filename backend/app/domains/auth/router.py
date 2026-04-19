"""GhostWire — Authentication routes (auth domain)"""
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.infrastructure.db import get_db
from app.domains.users.models import User
from app.domains.audit.models import AuditLog
from app.core.security import verify_password, hash_password, create_access_token, get_current_user
from app.infrastructure.events import bus, Events

router = APIRouter()
log = logging.getLogger("ghostwire.auth")

# ── Pending 2FA challenges ─────────────────────────────────────────────────────
# key = challenge_token → {"username": str, "method": str, "expires": float}
_pending_2fa: dict[str, dict] = {}
_2FA_CHALLENGE_TTL = 300   # 5 minutes


def _audit(db, actor, action, target, ip, level="info"):
    db.add(AuditLog(actor=actor, action=action, target=target,
                    ip_address=ip, level=level))
    db.commit()


def _purge_challenges():
    import time
    now = time.time()
    dead = [k for k, v in _pending_2fa.items() if now > v["expires"]]
    for k in dead:
        del _pending_2fa[k]


# ── Schemas ────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type:   str
    is_admin:     bool
    username:     str
    full_name:    str


class TwoFARequired(BaseModel):
    needs_2fa:       bool = True
    method:          str           # "totp" | "email_otp"
    challenge_token: str           # opaque token, submit with verify-2fa
    message:         str


class Verify2FA(BaseModel):
    challenge_token: str
    code:            str


class PasswordChange(BaseModel):
    current_password: str
    new_password:     str

    @field_validator("new_password")
    @classmethod
    def strong_enough(cls, v):
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must be under 128 characters")
        return v


# ── Login ──────────────────────────────────────────────────────────────────────

@router.post("/token")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Step 1 of login.
    - If 2FA is disabled → returns Token (same as Phase 1).
    - If 2FA is enabled  → returns TwoFARequired (challenge_token + method).
    """
    client_ip = request.client.host if request.client else "unknown"
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        log.warning(f"FAILED_LOGIN username={form_data.username} ip={client_ip}")
        _audit(db, form_data.username, "FAILED_LOGIN", form_data.username,
               client_ip, "warning")
        bus.emit(Events.AUTH_LOGIN_FAILED, {"username": form_data.username, "ip": client_ip})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # ── 2FA required? ─────────────────────────────────────────────────────────
    if user.totp_enabled:
        import time
        _purge_challenges()
        challenge_token = secrets.token_urlsafe(32)
        _pending_2fa[challenge_token] = {
            "username": user.username,
            "method":   "totp",
            "expires":  time.time() + _2FA_CHALLENGE_TTL,
        }
        _audit(db, user.username, "LOGIN_2FA_CHALLENGE", user.username, client_ip)
        return TwoFARequired(
            needs_2fa=True,
            method="totp",
            challenge_token=challenge_token,
            message="Enter the 6-digit code from your authenticator app",
        )

    # ── No 2FA — issue token immediately ─────────────────────────────────────
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    token = create_access_token({"sub": user.username})
    _audit(db, user.username, "LOGIN", user.username, client_ip)
    bus.emit(Events.AUTH_LOGIN_SUCCESS, {"username": user.username, "ip": client_ip})

    return Token(
        access_token=token,
        token_type="bearer",
        is_admin=user.is_admin,
        username=user.username,
        full_name=user.full_name,
    )


@router.post("/verify-2fa", response_model=Token)
async def verify_2fa(
    data: Verify2FA,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Step 2 of login when 2FA is required.
    Validates the challenge_token + TOTP/OTP code → issues JWT on success.
    """
    import time
    import pyotp

    _purge_challenges()
    challenge = _pending_2fa.get(data.challenge_token)
    client_ip = request.client.host if request.client else "unknown"

    if not challenge:
        raise HTTPException(400, "Invalid or expired 2FA challenge — please log in again")

    if time.time() > challenge["expires"]:
        del _pending_2fa[data.challenge_token]
        raise HTTPException(400, "2FA challenge expired — please log in again")

    username = challenge["username"]
    method   = challenge["method"]
    user     = db.query(User).filter(User.username == username).first()

    if not user or not user.is_active:
        raise HTTPException(403, "Account not found or disabled")

    # Verify the code
    if method == "totp":
        if not user.totp_secret:
            raise HTTPException(500, "TOTP secret missing — contact admin")
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(data.code.strip(), valid_window=1):
            _audit(db, username, "2FA_FAILED", username, client_ip, "warning")
            raise HTTPException(400, "Invalid TOTP code")

    elif method == "email_otp":
        from app.services.otp_service import verify_otp
        if not verify_otp(username, "login_2fa", data.code.strip()):
            _audit(db, username, "EMAIL_OTP_FAILED", username, client_ip, "warning")
            raise HTTPException(400, "Invalid or expired email OTP")

    else:
        raise HTTPException(400, f"Unknown 2FA method: {method}")

    # Success — consume challenge and issue token
    del _pending_2fa[data.challenge_token]
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    token = create_access_token({"sub": user.username})
    _audit(db, user.username, "LOGIN_2FA_SUCCESS", user.username, client_ip)
    bus.emit(Events.AUTH_LOGIN_SUCCESS, {"username": user.username, "ip": client_ip})

    return Token(
        access_token=token,
        token_type="bearer",
        is_admin=user.is_admin,
        username=user.username,
        full_name=user.full_name,
    )


# ── Password change ────────────────────────────────────────────────────────────

@router.post("/change-password")
async def change_password(
    data: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")

    current_user.hashed_password = hash_password(data.new_password)
    current_user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    client_ip = request.client.host if request.client else "unknown"
    _audit(db, current_user.username, "PASSWORD_CHANGE",
           current_user.username, client_ip)
    bus.emit(Events.AUTH_PASSWORD_CHANGED, {"username": current_user.username})
    return {"message": "Password changed successfully"}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id":           current_user.id,
        "username":     current_user.username,
        "full_name":    current_user.full_name,
        "email":        current_user.email,
        "is_admin":     current_user.is_admin,
        "vpn_enabled":  current_user.vpn_enabled,
        "vpn_username": current_user.vpn_username,
        "created_at":   current_user.created_at,
        "last_login":   current_user.last_login,
        "totp_enabled": current_user.totp_enabled,
    }

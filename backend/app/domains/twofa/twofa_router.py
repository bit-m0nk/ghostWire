"""GhostWire — Two-factor authentication domain (Phase 2)

Supports two methods:
  1. TOTP (authenticator app) — pyotp / RFC 6238
     Flow: GET /setup → returns secret + QR URI → POST /setup/confirm (first TOTP code)
           → TOTP is now active on the account
           POST /disable (current TOTP code required)

  2. Email OTP — fallback when user has no authenticator app
     Flow: POST /email-otp/send → OTP emailed → POST /email-otp/verify
           (used from login when totp_enabled=False but admin requires 2FA)

Login 2FA integration (in auth/router.py):
  - After password check, if user.totp_enabled → return {"needs_2fa": true, "method": "totp"}
  - Client calls POST /auth/verify-2fa with the TOTP/OTP code to get the real JWT
"""
import io
import logging
from typing import Optional

import pyotp
import qrcode
import qrcode.image.svg

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.db import get_db
from app.domains.users.models import User
from app.domains.audit.models import AuditLog
from app.core.security import get_current_user, hash_password, verify_password
from app.core.config import settings

router = APIRouter()
log = logging.getLogger("ghostwire.twofa")


def _audit(db, actor, action, target, ip="", level="info"):
    db.add(AuditLog(actor=actor, action=action, target=target,
                    ip_address=ip, level=level))
    db.commit()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ConfirmTOTP(BaseModel):
    code: str                    # 6-digit TOTP code from authenticator
    password: str                # current panel password (re-auth before enabling 2FA)

class DisableTOTP(BaseModel):
    code: str                    # current TOTP code to prove ownership
    password: str                # current panel password

class EmailOTPRequest(BaseModel):
    pass                         # no body — user inferred from JWT

class EmailOTPVerify(BaseModel):
    code: str


# ── TOTP: setup ───────────────────────────────────────────────────────────────

@router.get("/setup")
async def totp_setup(current_user: User = Depends(get_current_user)):
    """
    Generate a fresh TOTP secret and return the provisioning URI + raw secret.
    Does NOT activate 2FA — user must confirm with a valid code first.
    Secret is stored immediately so QR can be re-fetched, but totp_enabled stays False.
    """
    # Generate a new secret each time /setup is called (allows re-scan)
    secret = pyotp.random_base32()

    # Store the pending secret (not yet enabled)
    from app.infrastructure.db import SessionLocal
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == current_user.id).first()
        u.totp_secret  = secret
        u.totp_enabled = False
        db.commit()
    finally:
        db.close()

    issuer = settings.VPN_BRAND
    totp   = pyotp.TOTP(secret)
    uri    = totp.provisioning_uri(name=current_user.username, issuer_name=issuer)

    return {
        "secret":           secret,
        "provisioning_uri": uri,
        "issuer":           issuer,
        "username":         current_user.username,
        "instructions": (
            "Scan the QR code (GET /2fa/setup/qr) or enter the secret manually "
            "in your authenticator app, then call POST /2fa/setup/confirm with a "
            "valid 6-digit code to activate."
        ),
    }


@router.get("/setup/qr")
async def totp_qr(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Return the TOTP provisioning URI as an SVG QR code image."""
    # Re-query from DB — the dependency-injected current_user is loaded from the
    # JWT at request time and may be a stale detached object if /setup just wrote
    # the secret in a separate DB session. Reading totp_secret off the stale
    # object returns None and raises a spurious 400.
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user or not user.totp_secret:
        raise HTTPException(400, "Call GET /2fa/setup first to generate a secret")

    totp = pyotp.TOTP(user.totp_secret)
    uri  = totp.provisioning_uri(
        name=user.username,
        issuer_name=settings.VPN_BRAND,
    )

    # SvgFillImage produces clean SVG with proper viewBox — required for
    # correct rendering when injected via v-html in Vue. SvgImage (the basic
    # factory) omits viewBox which causes some browsers to render it at 0x0.
    factory = qrcode.image.svg.SvgFillImage
    img = qrcode.make(uri, image_factory=factory, box_size=10, border=4)
    buf = io.BytesIO()
    img.save(buf)
    svg_bytes = buf.getvalue()

    # Ensure the SVG has an explicit width/height so it is not zero-sized
    # when injected via innerHTML in environments that ignore viewBox only.
    svg_str = svg_bytes.decode("utf-8")
    if 'width=' not in svg_str[:200]:
        svg_str = svg_str.replace("<svg ", '<svg width="220" height="220" ', 1)
    svg_bytes = svg_str.encode("utf-8")

    return Response(
        content=svg_bytes,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.post("/setup/confirm")
async def totp_confirm(
    data: ConfirmTOTP,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Activate TOTP 2FA after user confirms with their first valid code."""
    if not current_user.totp_secret:
        raise HTTPException(400, "Call GET /2fa/setup first")
    if current_user.totp_enabled:
        raise HTTPException(400, "TOTP 2FA is already enabled")

    # Re-verify password before activating
    if not verify_password(data.password, current_user.hashed_password):
        raise HTTPException(403, "Incorrect password")

    totp = pyotp.TOTP(current_user.totp_secret)
    # valid=True accepts current window ± 1 (30-second tolerance)
    if not totp.verify(data.code.strip(), valid_window=1):
        raise HTTPException(400, "Invalid TOTP code — check your authenticator app clock")

    current_user.totp_enabled = True
    db.commit()

    ip = request.client.host if request.client else "unknown"
    _audit(db, current_user.username, "2FA_ENABLED", current_user.username, ip)
    log.info(f"TOTP 2FA enabled for {current_user.username}")

    return {"message": "TOTP 2FA enabled successfully", "totp_enabled": True}


@router.post("/disable")
async def totp_disable(
    data: DisableTOTP,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disable TOTP 2FA. Requires both current password and a valid TOTP code."""
    if not current_user.totp_enabled:
        raise HTTPException(400, "TOTP 2FA is not enabled")

    if not verify_password(data.password, current_user.hashed_password):
        raise HTTPException(403, "Incorrect password")

    totp = pyotp.TOTP(current_user.totp_secret)
    if not totp.verify(data.code.strip(), valid_window=1):
        raise HTTPException(400, "Invalid TOTP code")

    current_user.totp_enabled = False
    current_user.totp_secret  = None
    db.commit()

    ip = request.client.host if request.client else "unknown"
    _audit(db, current_user.username, "2FA_DISABLED", current_user.username, ip, "warning")
    log.info(f"TOTP 2FA disabled for {current_user.username}")

    return {"message": "TOTP 2FA disabled", "totp_enabled": False}


@router.get("/status")
async def totp_status(current_user: User = Depends(get_current_user)):
    """Return current 2FA status for the authenticated user."""
    return {
        "totp_enabled":  current_user.totp_enabled,
        "has_secret":    bool(current_user.totp_secret),
        "email_2fa_available": True,   # always available if SMTP configured
    }


# ── Email OTP ─────────────────────────────────────────────────────────────────

@router.post("/email-otp/send")
async def send_email_otp(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Send a 6-digit OTP to the user's registered email.
    Called from the login flow when the server returned needs_2fa=true and method=email_otp.
    """
    from app.services.otp_service import generate_otp, send_otp_email
    from app.services.config_service import get_smtp_config

    if not get_smtp_config():
        raise HTTPException(503, "Email 2FA requires SMTP to be configured")

    code = generate_otp(current_user.username, "login_2fa")
    ok, msg = send_otp_email(
        to_email=current_user.email,
        username=current_user.username,
        code=code,
        purpose="login_2fa",
        brand=settings.VPN_BRAND,
    )

    if not ok:
        raise HTTPException(503, f"Failed to send OTP email: {msg}")

    return {
        "message": f"OTP sent to {current_user.email[:3]}***",
        "expires_in": 600,
    }


@router.post("/email-otp/verify")
async def verify_email_otp(
    data: EmailOTPVerify,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify an email OTP. Returns 200 on success, 400 on failure."""
    from app.services.otp_service import verify_otp

    if not verify_otp(current_user.username, "login_2fa", data.code.strip()):
        ip = request.client.host if request.client else "unknown"
        _audit(db, current_user.username, "EMAIL_OTP_FAILED",
               current_user.username, ip, "warning")
        raise HTTPException(400, "Invalid or expired OTP code")

    ip = request.client.host if request.client else "unknown"
    _audit(db, current_user.username, "EMAIL_OTP_VERIFIED", current_user.username, ip)
    return {"verified": True}


# ── Admin: force-disable 2FA for a user (e.g. lost phone) ────────────────────

@router.post("/admin/reset/{user_id}")
async def admin_reset_2fa(
    user_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin endpoint: disable 2FA for a user (e.g. lost authenticator)."""
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    user.totp_enabled = False
    user.totp_secret  = None
    db.commit()

    ip = request.client.host if request.client else "unknown"
    _audit(db, current_user.username, "ADMIN_RESET_2FA", user.username, ip, "warning")
    log.info(f"Admin {current_user.username} reset 2FA for {user.username}")

    return {"message": f"2FA reset for {user.username}", "totp_enabled": False}

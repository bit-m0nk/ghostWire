"""GhostWire — Email OTP service (Phase 2)

Generates time-limited one-time codes for:
  - Email-based 2FA (alternative to TOTP)
  - Password reset confirmation
  - Account verification

Storage: in-memory dict with expiry (simple, works on single-server Pi).
Phase 4 (multi-server) should swap this for Redis/DB-backed storage.
"""
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("ghostwire.otp")

# OTP lives for this many seconds
OTP_TTL_SECONDS = 600   # 10 minutes


@dataclass
class OTPRecord:
    code:       str
    purpose:    str       # "login_2fa" | "password_reset" | "verify_email"
    username:   str
    created_at: float = field(default_factory=time.time)
    used:       bool  = False


# ── In-memory store ───────────────────────────────────────────────────────────
# key = (username, purpose) → OTPRecord
_store: dict[tuple[str, str], OTPRecord] = {}


def _purge_expired() -> None:
    """Remove expired / used OTPs from the store."""
    now = time.time()
    dead = [k for k, v in _store.items()
            if v.used or (now - v.created_at) > OTP_TTL_SECONDS]
    for k in dead:
        del _store[k]


def generate_otp(username: str, purpose: str) -> str:
    """
    Generate a 6-digit OTP for (username, purpose), store it, return the code.
    Replaces any existing pending OTP for the same user+purpose.
    """
    _purge_expired()
    code = f"{secrets.randbelow(1_000_000):06d}"
    _store[(username, purpose)] = OTPRecord(
        code=code, purpose=purpose, username=username
    )
    log.info(f"OTP generated for {username} / {purpose}")
    return code


def verify_otp(username: str, purpose: str, code: str) -> bool:
    """
    Return True if the code matches and is not expired/used.
    Marks it used on success so it can't be replayed.
    """
    _purge_expired()
    record = _store.get((username, purpose))
    if not record:
        log.warning(f"OTP verify failed for {username}/{purpose}: no record")
        return False
    if record.used:
        log.warning(f"OTP verify failed for {username}/{purpose}: already used")
        return False
    if (time.time() - record.created_at) > OTP_TTL_SECONDS:
        log.warning(f"OTP verify failed for {username}/{purpose}: expired")
        return False
    if not secrets.compare_digest(record.code, code.strip()):
        log.warning(f"OTP verify failed for {username}/{purpose}: wrong code")
        return False
    record.used = True
    log.info(f"OTP verified successfully for {username}/{purpose}")
    return True


def invalidate_otp(username: str, purpose: str) -> None:
    """Manually invalidate a pending OTP (e.g. on logout)."""
    _store.pop((username, purpose), None)


def send_otp_email(
    to_email: str,
    username: str,
    code: str,
    purpose: str,
    brand: str = "GhostWire",
) -> tuple[bool, str]:
    """
    Send the OTP code via email using the configured SMTP settings.
    Returns (success: bool, message: str).
    """
    from app.services.email_service import _smtp_settings, _send_message

    smtp = _smtp_settings()
    if not smtp:
        return False, "SMTP not configured — cannot send OTP email"

    purpose_labels = {
        "login_2fa":      "Login verification",
        "password_reset": "Password reset",
        "verify_email":   "Email verification",
    }
    label = purpose_labels.get(purpose, "Verification")

    subject = f"[{brand}] {label} code: {code}"
    html = f"""
<div style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;
            background:#111827;color:#e2e8f0;border-radius:12px;padding:32px;">
  <h2 style="color:#6366f1;margin-bottom:8px;">👻 {brand}</h2>
  <p style="color:#94a3b8;font-size:14px;margin-bottom:24px;">{label}</p>
  <p style="font-size:14px;margin-bottom:16px;">
    Hi <strong>{username}</strong>, here is your verification code:
  </p>
  <div style="background:#1a2235;border:1px solid #1e2a3a;border-radius:8px;
              padding:20px;text-align:center;margin-bottom:24px;">
    <span style="font-family:monospace;font-size:36px;font-weight:800;
                 letter-spacing:8px;color:#c7d2fe;">{code}</span>
  </div>
  <p style="color:#64748b;font-size:12px;">
    This code expires in 10 minutes. If you didn't request this, ignore this email.
  </p>
</div>"""

    text = f"{brand} — {label}\n\nYour code: {code}\n\nExpires in 10 minutes."

    try:
        _send_message(smtp, to_email, subject, html, text)
        return True, "OTP sent"
    except Exception as e:
        log.error(f"Failed to send OTP email to {to_email}: {e}")
        return False, str(e)

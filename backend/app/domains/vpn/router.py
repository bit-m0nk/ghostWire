"""GhostWire — VPN session control routes (vpn domain)"""
import subprocess
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.infrastructure.db import get_db
from app.domains.vpn.models import VPNSession
from app.domains.users.models import User
from app.domains.audit.models import AuditLog
from app.core.security import require_admin, get_current_user
from app.core.config import settings
from app.infrastructure.events import bus, Events

router = APIRouter()
log = logging.getLogger("ghostwire.vpn")


def _audit(db, actor, action, target, level="info"):
    db.add(AuditLog(actor=actor, action=action, target=target, level=level))
    db.commit()


def _run(cmd: list) -> tuple:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except FileNotFoundError:
        return 1, "", f"Command not found: {cmd[0]}"


def _now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _force_disconnect(session: VPNSession) -> bool:
    conn = session.device_info or "ikev2-eap"
    uid  = session.session_key or ""
    user = session.username or ""

    # swanctl --terminate scoped to a single IKE-SA via --ike-id (numeric unique-ID).
    # We deliberately avoid the bare `--ike <conn>` fallback because that would
    # terminate *all* IKE SAs matching the connection name and disconnect every
    # user on that connection, not just the target.
    cmds = []
    if uid and uid.isdigit():
        # Preferred: target the exact IKE-SA by unique-ID
        cmds.append(["swanctl", "--terminate", "--ike", conn, "--ike-id", uid])
    elif uid:
        # uid present but non-numeric (shouldn't happen with swanctl, log it)
        log.warning(f"session_key {uid!r} is not a numeric IKE unique-ID — cannot safely terminate SA for {user}")
    # No broad --ike-only fallback: if we have no uid we cannot safely target a
    # single SA.  The session will be marked inactive in the DB (caller's job).

    for cmd in cmds:
        code, out, err = _run(cmd)
        log.info(f"disconnect cmd={' '.join(cmd)} code={code} out={out[:300]}")
        if code == 0:
            return True

    log.warning(f"Could not disconnect SA for {user} via swanctl --terminate — marking inactive in DB only")
    return False


@router.post("/disconnect/{session_id}")
async def disconnect_session(
    session_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    session = db.query(VPNSession).filter(VPNSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "Session not found")

    _force_disconnect(session)
    session.is_active = False
    session.disconnected_at = _now_naive()
    db.commit()

    _audit(db, admin.username, "DISCONNECT_SESSION", session.username or session_id, "warning")
    bus.emit(Events.VPN_SESSION_ENDED, {"session_id": session_id, "username": session.username})
    return {"message": f"Session for {session.username} disconnected"}


@router.post("/disconnect-user/{user_id}")
async def disconnect_user_all(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    sessions = db.query(VPNSession).filter(
        VPNSession.user_id  == user_id,
        VPNSession.is_active == True,
    ).all()

    for s in sessions:
        _force_disconnect(s)
        s.is_active = False
        s.disconnected_at = _now_naive()

    db.commit()
    _audit(db, admin.username, "DISCONNECT_ALL", user.username, "warning")
    return {"message": f"Disconnected {len(sessions)} session(s) for {user.username}"}


@router.get("/status")
async def vpn_status(admin: User = Depends(require_admin)):
    code, out, err = _run(["swanctl", "--list-sas"])
    return {"running": code == 0, "output": out[:2000] if out else err[:500]}


@router.post("/restart")
async def restart_vpn(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    import time
    code, out, err = _run(["systemctl", "restart", "strongswan"])
    if code != 0:
        raise HTTPException(500, f"Restart failed: {err}")
    time.sleep(3)  # wait for charon socket
    _run(["swanctl", "--load-all"])
    _run(["swanctl", "--load-creds"])
    _audit(db, admin.username, "RESTART_VPN", "strongswan", "warning")
    bus.emit(Events.VPN_RESTARTED, {"actor": admin.username})
    return {"message": "VPN restarted successfully"}


@router.post("/reload-secrets")
async def reload_secrets(admin: User = Depends(require_admin)):
    code, out, err = _run(["swanctl", "--load-creds"])
    if code != 0:
        raise HTTPException(500, f"Reload failed: {err}")
    return {"message": "Secrets reloaded"}


@router.get("/ping", include_in_schema=True)
async def ping():
    """Public health check — returns brand name without authentication."""
    return {
        "status":  "ok",
        "brand":   settings.VPN_BRAND,
        "version": "2.0.0",
    }


@router.get("/server-info")
async def server_info(current_user: User = Depends(get_current_user)):
    from pathlib import Path
    last_ip_file = Path(settings.INSTALL_DIR) / "data" / "last_known_ip.txt"
    current_ip = (
        last_ip_file.read_text().strip()
        if last_ip_file.exists()
        else settings.PUBLIC_IP
    )
    return {
        "server":       settings.server_hostname,
        "current_ip":   current_ip,
        "brand":        settings.VPN_BRAND,
        "protocol":     "IKEv2 / IPSec",
        "ports":        {"udp": [500, 4500]},
        "ddns_enabled": settings.ddns_enabled,
        "psk":          settings.PSK,
        "dns":          ["1.1.1.1", "8.8.8.8"],
    }


@router.get("/debug-bytes")
async def debug_bytes(admin: User = Depends(require_admin)):
    """Debug endpoint: run swanctl --list-sas and return raw + parsed output."""
    from app.core.scheduler import _parse_swanctl_sas
    code, out, err = _run(["swanctl", "--list-sas", "--raw"])
    active_uids, active_vips, vip_bytes_tuples = _parse_swanctl_sas(out or "")
    active_uids = list(active_uids)
    vip_bytes = {vip: {"bytes_i": b[0], "bytes_o": b[1]} for vip, b in vip_bytes_tuples.items()}

    from app.infrastructure.db import SessionLocal
    db_sessions = []
    try:
        db = SessionLocal()
        for s in db.query(VPNSession).filter(VPNSession.is_active == True).all():
            db_sessions.append({
                "username":   s.username,
                "virtual_ip": s.virtual_ip,
                "session_key": s.session_key,
                "bytes_in":   s.bytes_in,
                "bytes_out":  s.bytes_out,
            })
        db.close()
    except Exception as e:
        db_sessions = [{"error": str(e)}]

    return {
        "swanctl_exit_code":         code,
        "active_uids_in_list_sas":   active_uids,
        "vip_bytes_in_list_sas":     vip_bytes,
        "active_sessions_in_db":     db_sessions,
        "list_sas_snippet":          out[:2000] if out else err[:500],
    }


# ── Phase 4: User's own active sessions (portal self-service) ─────────────────

@router.get("/sessions/my")
async def my_sessions(
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Return the current user's active VPN sessions. Used by the user portal."""
    from app.domains.vpn.models import VPNSession
    rows = (
        db.query(VPNSession)
        .filter(
            VPNSession.user_id   == current_user.id,
            VPNSession.is_active == True,
        )
        .order_by(VPNSession.connected_at.desc())
        .all()
    )
    return [
        {
            "id":           s.id,
            "client_ip":    s.client_ip,
            "virtual_ip":   s.virtual_ip,
            "country":      s.country,
            "country_name": s.country_name,
            "bytes_in":     s.bytes_in,
            "bytes_out":    s.bytes_out,
            "connected_at": s.connected_at.isoformat() if s.connected_at else None,
        }
        for s in rows
    ]


@router.get("/sessions/active")
async def active_sessions_list(
    admin: User    = Depends(require_admin),
    db:    Session = Depends(get_db),
):
    """All active sessions across all users — used by node health checker."""
    from app.domains.vpn.models import VPNSession
    rows = db.query(VPNSession).filter(VPNSession.is_active == True).all()
    return [
        {
            "id":       s.id,
            "username": s.username,
            "user_id":  s.user_id,
        }
        for s in rows
    ]

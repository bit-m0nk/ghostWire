"""GhostWire — Statistics routes (stats domain)"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.infrastructure.db import get_db
from app.domains.users.models import User
from app.domains.vpn.models import VPNSession
from app.domains.audit.models import AuditLog
from app.core.security import require_admin, get_current_user
from app.core.config import settings

router = APIRouter()


def _fmt_bytes(b: int) -> str:
    if not b:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _to_aware(dt) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _fmt_dt(dt) -> str:
    if dt is None:
        return None
    aware = _to_aware(dt)
    return aware.strftime("%Y-%m-%dT%H:%M:%SZ")


def _duration_str(connected_at) -> str:
    if not connected_at:
        return "—"
    aware = _to_aware(connected_at)
    delta = datetime.now(timezone.utc) - aware
    total = int(delta.total_seconds())
    if total < 0:
        return "0s"
    h, rem = divmod(total, 3600)
    m, s   = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


@router.get("/dashboard")
async def dashboard(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    total_users = db.query(User).filter(User.is_active == True).count()
    vpn_users   = db.query(User).filter(
        User.vpn_enabled == True, User.is_active == True
    ).count()
    active_now  = db.query(VPNSession).filter(
        VPNSession.is_active == True
    ).count()

    traffic = db.query(
        func.coalesce(func.sum(VPNSession.bytes_in),  0),
        func.coalesce(func.sum(VPNSession.bytes_out), 0),
    ).first()
    total_in  = int(traffic[0])
    total_out = int(traffic[1])

    cutoff_naive = (datetime.now(timezone.utc) - timedelta(days=30)).replace(tzinfo=None)
    recent = db.query(VPNSession).filter(
        VPNSession.connected_at >= cutoff_naive
    ).count()

    recent_logs = (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .limit(20)
        .all()
    )

    countries = (
        db.query(VPNSession.country_name, func.count(VPNSession.id))
        .group_by(VPNSession.country_name)
        .order_by(func.count(VPNSession.id).desc())
        .limit(10)
        .all()
    )

    return {
        "total_users":     total_users,
        "vpn_users":       vpn_users,
        "active_now":      active_now,
        "total_in":        _fmt_bytes(total_in),
        "total_out":       _fmt_bytes(total_out),
        "total_in_raw":    total_in,
        "total_out_raw":   total_out,
        "connections_30d": recent,
        "server_hostname": settings.server_hostname,
        "ddns_enabled":    settings.ddns_enabled,
        "recent_logs": [
            {
                "timestamp": _fmt_dt(l.timestamp),
                "actor":     l.actor,
                "action":    l.action,
                "target":    l.target,
                "level":     l.level,
            }
            for l in recent_logs
        ],
        "top_countries": [
            {"country": c[0] or "Unknown", "count": c[1]}
            for c in countries
        ],
    }


@router.get("/active-sessions")
async def active_sessions(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    sessions = db.query(VPNSession).filter(
        VPNSession.is_active == True
    ).all()
    return [
        {
            "id":           s.id,
            "username":     s.username,
            "client_ip":    s.client_ip   or "—",
            "virtual_ip":   s.virtual_ip  or "—",
            "country":      s.country     or "??",
            "country_name": s.country_name or "Unknown",
            "bytes_in":     _fmt_bytes(s.bytes_in  or 0),
            "bytes_out":    _fmt_bytes(s.bytes_out or 0),
            "connected_at": _fmt_dt(s.connected_at),
            "duration":     _duration_str(s.connected_at),
        }
        for s in sessions
    ]


@router.get("/connection-history")
async def connection_history(
    limit:  int     = 100,
    offset: int     = 0,
    search: str     = "",
    admin:  User    = Depends(require_admin),
    db:     Session = Depends(get_db),
):
    if limit < 1 or limit > 1000:
        limit = 100
    if offset < 0:
        offset = 0

    q = db.query(VPNSession).order_by(VPNSession.connected_at.desc())
    if search:
        q = q.filter(VPNSession.username.ilike(f"%{search}%"))

    total    = q.count()
    sessions = q.offset(offset).limit(limit).all()
    return {
        "total":  total,
        "offset": offset,
        "limit":  limit,
        "items": [
            {
                "id":              s.id,
                "username":        s.username,
                "client_ip":       s.client_ip    or "—",
                "country_name":    s.country_name or "Unknown",
                "bytes_in":        _fmt_bytes(s.bytes_in  or 0),
                "bytes_out":       _fmt_bytes(s.bytes_out or 0),
                "connected_at":    _fmt_dt(s.connected_at),
                "disconnected_at": _fmt_dt(s.disconnected_at),
                "is_active":       s.is_active == True,
            }
            for s in sessions
        ],
    }


@router.get("/audit-log")
async def audit_log(
    limit:  int           = 200,
    offset: int           = 0,
    level:  str           = "",
    search: str           = "",
    admin:  User          = Depends(require_admin),
    db:     Session       = Depends(get_db),
):
    if limit < 1 or limit > 2000:
        limit = 200
    if offset < 0:
        offset = 0

    q = db.query(AuditLog).order_by(AuditLog.timestamp.desc())
    if level:
        q = q.filter(AuditLog.level == level)
    if search:
        like = f"%{search.lower()}%"
        from sqlalchemy import or_, func as sqlfunc
        q = q.filter(or_(
            sqlfunc.lower(AuditLog.actor).like(like),
            sqlfunc.lower(AuditLog.action).like(like),
            sqlfunc.lower(AuditLog.target).like(like),
        ))

    total = q.count()
    logs  = q.offset(offset).limit(limit).all()

    return {
        "total":  total,
        "offset": offset,
        "limit":  limit,
        "items": [
            {
                "timestamp":  l.timestamp,
                "actor":      l.actor,
                "action":     l.action,
                "target":     l.target,
                "detail":     l.detail,
                "ip_address": l.ip_address,
                "level":      l.level,
            }
            for l in logs
        ],
    }

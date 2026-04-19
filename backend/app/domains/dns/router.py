"""GhostWire — DNS domain router (Phase 3)

Endpoints:
  GET    /dns/status             — global blocking status + blocklist stats
  POST   /dns/sync               — admin: trigger full blocklist resync
  GET    /dns/blocklists          — list all blocklist sources
  POST   /dns/blocklists          — add a custom source
  PATCH  /dns/blocklists/{id}    — enable / disable / rename a source
  DELETE /dns/blocklists/{id}    — remove a source

  GET    /dns/overrides           — global admin whitelist/blacklist
  POST   /dns/overrides           — add an override
  DELETE /dns/overrides/{id}      — remove an override

  GET    /dns/settings/me         — current user's DNS settings
  PUT    /dns/settings/me         — update my blocking toggle + custom lists
  GET    /dns/settings/{user_id}  — admin: view any user's settings
  PUT    /dns/settings/{user_id}  — admin: update any user's settings

  GET    /dns/events              — recent events (paginated, filterable)
  GET    /dns/stats/summary       — totals for dashboard widgets
  GET    /dns/stats/top-domains   — top blocked domains
  GET    /dns/stats/hourly        — hourly blocked/allowed series (last 24h)
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_admin
from app.domains.users.models import User
from app.domains.dns.models import (
    BlocklistSource, DnsEvent, UserDnsSettings, DnsOverride
)
from app.domains.dns import service as dns_svc
from app.infrastructure.db import get_db
from app.infrastructure.events.bus import bus, Events

log = logging.getLogger("ghostwire.dns")
router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class BlocklistCreate(BaseModel):
    name: str
    url: str


class BlocklistPatch(BaseModel):
    name:      Optional[str]  = None
    is_active: Optional[bool] = None


class OverrideCreate(BaseModel):
    domain: str
    action: str   # "allow" | "block"
    reason: Optional[str] = None


class DnsSettingsUpdate(BaseModel):
    blocking_enabled: Optional[bool]       = None
    custom_whitelist: Optional[list[str]]  = None
    custom_blacklist: Optional[list[str]]  = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_create_settings(user_id: str, db: Session) -> UserDnsSettings:
    s = db.query(UserDnsSettings).filter(UserDnsSettings.user_id == user_id).first()
    if not s:
        s = UserDnsSettings(user_id=user_id)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _settings_to_dict(s: UserDnsSettings) -> dict:
    return {
        "user_id":          s.user_id,
        "blocking_enabled": s.blocking_enabled,
        "custom_whitelist": json.loads(s.custom_whitelist or "[]"),
        "custom_blacklist": json.loads(s.custom_blacklist or "[]"),
        "updated_at":       s.updated_at.isoformat() if s.updated_at else None,
    }


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
def dns_status(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    sources      = db.query(BlocklistSource).all()
    active_count = sum(1 for s in sources if s.is_active)
    total_domains = sum(s.domain_count for s in sources if s.is_active)
    last_sync    = max(
        (s.last_synced for s in sources if s.last_synced),
        default=None,
    )
    return {
        "active_sources":  active_count,
        "total_sources":   len(sources),
        "total_domains":   total_domains,
        "last_sync":       last_sync.isoformat() if last_sync else None,
        "dnsmasq_conf_dir": dns_svc.DNSMASQ_CONF_DIR,
        "merged_blocklist": dns_svc.MERGED_BLOCKLIST,
    }


# ── Blocklist sources ─────────────────────────────────────────────────────────

@router.get("/blocklists")
def list_blocklists(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    sources = db.query(BlocklistSource).order_by(BlocklistSource.name).all()
    return [
        {
            "id":           s.id,
            "name":         s.name,
            "url":          s.url,
            "is_active":    s.is_active,
            "domain_count": s.domain_count,
            "last_synced":  s.last_synced.isoformat()  if s.last_synced  else None,
            "last_error":   s.last_error,
            "created_at":   s.created_at.isoformat()   if s.created_at   else None,
        }
        for s in sources
    ]


@router.post("/blocklists", status_code=201)
def add_blocklist(
    body: BlocklistCreate,
    db:   Session = Depends(get_db),
    _:    User    = Depends(require_admin),
):
    existing = db.query(BlocklistSource).filter(BlocklistSource.url == body.url).first()
    if existing:
        raise HTTPException(400, "Blocklist with this URL already exists")
    src = BlocklistSource(name=body.name, url=body.url)
    db.add(src)
    db.commit()
    db.refresh(src)
    return {"id": src.id, "message": "Blocklist added"}


@router.patch("/blocklists/{source_id}")
def patch_blocklist(
    source_id: str,
    body: BlocklistPatch,
    db:   Session = Depends(get_db),
    _:    User    = Depends(require_admin),
):
    src = db.query(BlocklistSource).filter(BlocklistSource.id == source_id).first()
    if not src:
        raise HTTPException(404, "Blocklist source not found")
    if body.name is not None:
        src.name = body.name
    if body.is_active is not None:
        src.is_active = body.is_active
    db.commit()
    return {"message": "Updated"}


@router.delete("/blocklists/{source_id}", status_code=204)
def delete_blocklist(
    source_id: str,
    db:  Session = Depends(get_db),
    _:   User    = Depends(require_admin),
):
    src = db.query(BlocklistSource).filter(BlocklistSource.id == source_id).first()
    if not src:
        raise HTTPException(404, "Blocklist source not found")
    db.delete(src)
    db.commit()


@router.post("/sync")
async def sync_blocklists(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _:  User    = Depends(require_admin),
):
    """Trigger full blocklist resync in background."""
    async def _do_sync():
        count = await dns_svc.rebuild_merged_blocklist(db)
        bus.emit(Events.DNS_BLOCKLIST_SYNCED, {"domain_count": count})
        log.info(f"DNS: sync complete — {count} domains")

    background_tasks.add_task(_do_sync)
    return {"message": "Sync started in background"}


# ── Global overrides ──────────────────────────────────────────────────────────

@router.get("/overrides")
def list_overrides(
    db: Session = Depends(get_db),
    _:  User    = Depends(require_admin),
):
    rows = db.query(DnsOverride).order_by(DnsOverride.action, DnsOverride.domain).all()
    return [
        {
            "id":         r.id,
            "domain":     r.domain,
            "action":     r.action,
            "reason":     r.reason,
            "created_by": r.created_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/overrides", status_code=201)
def add_override(
    body:    OverrideCreate,
    db:      Session = Depends(get_db),
    current: User    = Depends(require_admin),
):
    if body.action not in ("allow", "block"):
        raise HTTPException(400, "action must be 'allow' or 'block'")
    existing = db.query(DnsOverride).filter(DnsOverride.domain == body.domain).first()
    if existing:
        raise HTTPException(400, "Override for this domain already exists")
    override = DnsOverride(
        domain=body.domain.lower(),
        action=body.action,
        reason=body.reason,
        created_by=current.id,
    )
    db.add(override)
    db.commit()
    db.refresh(override)
    return {"id": override.id, "message": "Override added"}


@router.delete("/overrides/{override_id}", status_code=204)
def delete_override(
    override_id: str,
    db: Session = Depends(get_db),
    _:  User    = Depends(require_admin),
):
    row = db.query(DnsOverride).filter(DnsOverride.id == override_id).first()
    if not row:
        raise HTTPException(404, "Override not found")
    db.delete(row)
    db.commit()


# ── Per-user settings ─────────────────────────────────────────────────────────

@router.get("/settings/me")
def get_my_settings(
    db:      Session = Depends(get_db),
    current: User    = Depends(get_current_user),
):
    return _settings_to_dict(_get_or_create_settings(current.id, db))


@router.put("/settings/me")
def update_my_settings(
    body:    DnsSettingsUpdate,
    db:      Session = Depends(get_db),
    current: User    = Depends(get_current_user),
):
    s = _get_or_create_settings(current.id, db)
    if body.blocking_enabled is not None:
        s.blocking_enabled = body.blocking_enabled
    if body.custom_whitelist is not None:
        s.custom_whitelist = json.dumps(body.custom_whitelist)
    if body.custom_blacklist is not None:
        s.custom_blacklist = json.dumps(body.custom_blacklist)
    s.updated_at = datetime.now(timezone.utc)
    db.commit()
    # Rewrite dnsmasq conf for this user
    dns_svc.write_user_conf(current.id, s)
    bus.emit(Events.DNS_USER_SETTINGS_UPDATED, {"user_id": current.id})
    return _settings_to_dict(s)


@router.get("/settings/{user_id}")
def get_user_settings(
    user_id: str,
    db:      Session = Depends(get_db),
    _:       User    = Depends(require_admin),
):
    return _settings_to_dict(_get_or_create_settings(user_id, db))


@router.put("/settings/{user_id}")
def update_user_settings(
    user_id: str,
    body:    DnsSettingsUpdate,
    db:      Session = Depends(get_db),
    _:       User    = Depends(require_admin),
):
    s = _get_or_create_settings(user_id, db)
    if body.blocking_enabled is not None:
        s.blocking_enabled = body.blocking_enabled
    if body.custom_whitelist is not None:
        s.custom_whitelist = json.dumps(body.custom_whitelist)
    if body.custom_blacklist is not None:
        s.custom_blacklist = json.dumps(body.custom_blacklist)
    s.updated_at = datetime.now(timezone.utc)
    db.commit()
    dns_svc.write_user_conf(user_id, s)
    return _settings_to_dict(s)


# ── Events / query log ────────────────────────────────────────────────────────

@router.get("/events")
def list_events(
    action:  Optional[str] = Query(None, description="Filter: blocked | allowed"),
    user_id: Optional[str] = Query(None, description="Filter by user"),
    domain:  Optional[str] = Query(None, description="Substring domain filter"),
    limit:   int           = Query(50, ge=1, le=500),
    offset:  int           = Query(0,  ge=0),
    db:      Session       = Depends(get_db),
    current: User          = Depends(get_current_user),
):
    # Non-admins can only see their own events
    if not current.is_admin:
        user_id = current.id

    q = db.query(DnsEvent).order_by(DnsEvent.timestamp.desc())
    if action:
        q = q.filter(DnsEvent.action == action)
    if user_id:
        q = q.filter(DnsEvent.user_id == user_id)
    if domain:
        q = q.filter(DnsEvent.domain.contains(domain.lower()))

    total = q.count()
    rows  = q.offset(offset).limit(limit).all()

    return {
        "total":  total,
        "offset": offset,
        "limit":  limit,
        "items": [
            {
                "id":        r.id,
                "user_id":   r.user_id,
                "domain":    r.domain,
                "qtype":     r.qtype,
                "action":    r.action,
                "reason":    r.reason,
                "client_ip": r.client_ip,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in rows
        ],
    }


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats/summary")
def stats_summary(
    hours:   int           = Query(24, ge=1, le=720),
    user_id: Optional[str] = Query(None),
    db:      Session       = Depends(get_db),
    current: User          = Depends(get_current_user),
):
    if not current.is_admin:
        user_id = current.id
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    return dns_svc.get_summary_stats(db, user_id=user_id, since=since)


@router.get("/stats/top-domains")
def stats_top_domains(
    limit:   int           = Query(10, ge=1, le=50),
    hours:   int           = Query(24, ge=1, le=720),
    user_id: Optional[str] = Query(None),
    db:      Session       = Depends(get_db),
    current: User          = Depends(get_current_user),
):
    if not current.is_admin:
        user_id = current.id
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    return dns_svc.get_top_blocked_domains(db, user_id=user_id, limit=limit, since=since)


@router.get("/stats/hourly")
def stats_hourly(
    hours:   int           = Query(24, ge=1, le=168),
    user_id: Optional[str] = Query(None),
    db:      Session       = Depends(get_db),
    current: User          = Depends(get_current_user),
):
    if not current.is_admin:
        user_id = current.id
    return dns_svc.get_event_counts_by_hour(db, user_id=user_id, hours=hours)

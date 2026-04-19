"""GhostWire — GraphQL schema (Phase 3, Strawberry)

Flexible analytics endpoint.  Requires strawberry-graphql[fastapi].

Example queries:

  # Top 10 blocked domains for user X in the last 7 days
  query {
    topBlockedDomains(userId: "abc", hours: 168, limit: 10) {
      domain
      count
    }
  }

  # Hourly blocked/allowed breakdown
  query {
    hourlyStats(hours: 24) {
      hour
      action
      count
    }
  }

  # Per-user summary (admin only)
  query {
    userSummaries(hours: 24) {
      userId
      username
      totalQueries
      blockedCount
      blockRate
    }
  }

Authentication: Bearer JWT required (same as REST).
Non-admin users see only their own data; admin sees all.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import strawberry
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info

from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.security import get_current_user
from app.infrastructure.db import get_db, SessionLocal
from app.domains.dns.models import DnsEvent
from app.domains.users.models import User

log = logging.getLogger("ghostwire.graphql")


# ── GraphQL context ───────────────────────────────────────────────────────────

class GWContext:
    def __init__(self, db: Session, user: User):
        self.db   = db
        self.user = user


async def get_graphql_context(
    db:      Session = Depends(get_db),
    current: User    = Depends(get_current_user),
) -> GWContext:
    return GWContext(db=db, user=current)


# ── Types ─────────────────────────────────────────────────────────────────────

@strawberry.type
class DomainCount:
    domain: str
    count:  int


@strawberry.type
class HourlyStat:
    hour:   str
    action: str
    count:  int


@strawberry.type
class SummaryStats:
    total_queries: int
    blocked_count: int
    allowed_count: int
    block_rate:    float
    since:         str


@strawberry.type
class UserSummary:
    user_id:       str
    username:      str
    total_queries: int
    blocked_count: int
    block_rate:    float


@strawberry.type
class DnsEventType:
    id:         str
    user_id:    Optional[str]
    domain:     str
    qtype:      str
    action:     str
    reason:     Optional[str]
    client_ip:  Optional[str]
    timestamp:  str


# ── Resolvers ─────────────────────────────────────────────────────────────────

def _resolve_user_id(info: Info, requested_user_id: Optional[str]) -> Optional[str]:
    """Non-admins always get their own data regardless of what they ask for."""
    ctx: GWContext = info.context
    if not ctx.user.is_admin:
        return ctx.user.id
    return requested_user_id


@strawberry.type
class Query:

    @strawberry.field
    def top_blocked_domains(
        self,
        info:    Info,
        hours:   int            = 24,
        limit:   int            = 10,
        user_id: Optional[str] = None,
    ) -> list[DomainCount]:
        ctx: GWContext = info.context
        uid   = _resolve_user_id(info, user_id)
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        q = ctx.db.query(DnsEvent.domain, func.count(DnsEvent.id).label("cnt")) \
                  .filter(DnsEvent.action == "blocked", DnsEvent.timestamp >= since)
        if uid:
            q = q.filter(DnsEvent.user_id == uid)
        rows = q.group_by(DnsEvent.domain).order_by(desc("cnt")).limit(limit).all()
        return [DomainCount(domain=r.domain, count=r.cnt) for r in rows]

    @strawberry.field
    def hourly_stats(
        self,
        info:    Info,
        hours:   int            = 24,
        user_id: Optional[str] = None,
    ) -> list[HourlyStat]:
        ctx: GWContext = info.context
        uid   = _resolve_user_id(info, user_id)
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        q = ctx.db.query(
            func.strftime("%Y-%m-%dT%H:00:00", DnsEvent.timestamp).label("hour"),
            DnsEvent.action,
            func.count(DnsEvent.id).label("cnt"),
        ).filter(DnsEvent.timestamp >= since)
        if uid:
            q = q.filter(DnsEvent.user_id == uid)
        rows = q.group_by("hour", DnsEvent.action).order_by("hour").all()
        return [HourlyStat(hour=r.hour, action=r.action, count=r.cnt) for r in rows]

    @strawberry.field
    def summary(
        self,
        info:    Info,
        hours:   int            = 24,
        user_id: Optional[str] = None,
    ) -> SummaryStats:
        ctx: GWContext = info.context
        uid   = _resolve_user_id(info, user_id)
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        q = ctx.db.query(func.count(DnsEvent.id)).filter(DnsEvent.timestamp >= since)
        if uid:
            q = q.filter(DnsEvent.user_id == uid)
        total   = q.scalar() or 0
        blocked = (ctx.db.query(func.count(DnsEvent.id))
                       .filter(DnsEvent.action == "blocked", DnsEvent.timestamp >= since,
                               *([DnsEvent.user_id == uid] if uid else []))
                       .scalar() or 0)
        allowed = total - blocked
        rate    = round((blocked / total * 100) if total else 0, 1)
        return SummaryStats(
            total_queries=total, blocked_count=blocked,
            allowed_count=allowed, block_rate=rate,
            since=since.isoformat(),
        )

    @strawberry.field
    def user_summaries(
        self,
        info:  Info,
        hours: int = 24,
    ) -> list[UserSummary]:
        ctx: GWContext = info.context
        if not ctx.user.is_admin:
            raise Exception("Admin access required")

        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        rows = (
            ctx.db.query(
                DnsEvent.user_id,
                func.count(DnsEvent.id).label("total"),
                func.sum(
                    func.cast(DnsEvent.action == "blocked", func.Integer)
                    if False else (DnsEvent.action == "blocked")
                ).label("blocked"),
            )
            .filter(DnsEvent.timestamp >= since, DnsEvent.user_id.isnot(None))
            .group_by(DnsEvent.user_id)
            .all()
        )

        # Map user_ids to usernames
        uids     = [r.user_id for r in rows]
        users    = ctx.db.query(User).filter(User.id.in_(uids)).all()
        umap     = {u.id: u.username for u in users}

        result = []
        for r in rows:
            total   = r.total or 0
            # SQLite SUM of boolean: count blocked directly
            blocked = (ctx.db.query(func.count(DnsEvent.id))
                           .filter(DnsEvent.user_id == r.user_id,
                                   DnsEvent.action == "blocked",
                                   DnsEvent.timestamp >= since)
                           .scalar() or 0)
            result.append(UserSummary(
                user_id=r.user_id,
                username=umap.get(r.user_id, "unknown"),
                total_queries=total,
                blocked_count=blocked,
                block_rate=round((blocked / total * 100) if total else 0, 1),
            ))
        return result

    @strawberry.field
    def recent_events(
        self,
        info:    Info,
        limit:   int            = 20,
        action:  Optional[str] = None,
        user_id: Optional[str] = None,
        domain:  Optional[str] = None,
    ) -> list[DnsEventType]:
        ctx: GWContext = info.context
        uid = _resolve_user_id(info, user_id)
        q   = ctx.db.query(DnsEvent).order_by(DnsEvent.timestamp.desc())
        if uid:
            q = q.filter(DnsEvent.user_id == uid)
        if action:
            q = q.filter(DnsEvent.action == action)
        if domain:
            q = q.filter(DnsEvent.domain.contains(domain.lower()))
        rows = q.limit(min(limit, 200)).all()
        return [
            DnsEventType(
                id=r.id, user_id=r.user_id, domain=r.domain,
                qtype=r.qtype, action=r.action, reason=r.reason,
                client_ip=r.client_ip,
                timestamp=r.timestamp.isoformat() if r.timestamp else "",
            )
            for r in rows
        ]


# ── FastAPI router ────────────────────────────────────────────────────────────

schema = strawberry.Schema(query=Query)

graphql_router = GraphQLRouter(
    schema,
    context_getter=get_graphql_context,
    graphql_ide="graphiql",   # strawberry ≥0.235 uses graphql_ide= instead of graphiql=
)

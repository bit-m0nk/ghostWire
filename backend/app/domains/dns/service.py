"""GhostWire — DNS service (Phase 3)

Responsibilities:
  1. Blocklist sync — download remote lists, merge into a single dnsmasq conf
  2. dnsmasq config writer — per-user conf snippets, global overrides
  3. Log tailer — parse dnsmasq query.log lines → DnsEvent rows
  4. Stats helpers — top domains, blocked count, etc.

All filesystem operations are guarded by try/except so the app keeps running
on machines where dnsmasq isn't installed (dev laptops, CI).
"""
import json
import logging
import os
import re
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.domains.dns.models import (
    DnsEvent, BlocklistSource, UserDnsSettings, DnsOverride
)
from app.domains.users.models import User
from app.infrastructure.events.bus import bus, Events

log = logging.getLogger("ghostwire.dns")

# ── Filesystem paths ──────────────────────────────────────────────────────────
DNSMASQ_CONF_DIR   = "/etc/dnsmasq.d/ghostwire"
BLOCKLIST_DIR      = "/opt/ghostwire/blocklists"
MERGED_BLOCKLIST   = os.path.join(BLOCKLIST_DIR, "merged.conf")
DNSMASQ_QUERY_LOG  = "/var/log/dnsmasq/query.log"

# ── Default blocklists bundled at install time ─────────────────────────────────
DEFAULT_BLOCKLISTS = [
    {
        "name": "StevenBlack Unified (Ads + Malware)",
        "url": "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
    },
    {
        "name": "OISD Basic",
        "url": "https://abp.oisd.nl/basic/",
    },
]

# ── Regex for dnsmasq query log lines ────────────────────────────────────────
# Format: "Jan  1 12:00:00 dnsmasq[1234]: query[A] ads.example.com from 10.10.0.2"
#         "Jan  1 12:00:00 dnsmasq[1234]: /etc/dnsmasq.d/.../merged.conf ads.example.com is NXDOMAIN"
_QUERY_RE  = re.compile(r"query\[(\w+)\] ([\w.\-]+) from ([\d.]+)")
_BLOCK_RE  = re.compile(r"config ([\w.\-]+) is (NXDOMAIN|0\.0\.0\.0)")


# ── Blocklist sync ────────────────────────────────────────────────────────────

def _parse_hosts_file(text: str) -> list[str]:
    """Extract domains from a hosts-format or plain-domain-list file."""
    domains: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # hosts format: "0.0.0.0 ads.example.com" or "127.0.0.1 ads.example.com"
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("0.0.0.0", "127.0.0.1"):
            d = parts[1].lower()
        elif len(parts) == 1:
            d = parts[0].lower()
        else:
            continue
        # Skip localhost entries and invalid domains
        if d in ("localhost", "localhost.localdomain", "broadcasthost", "0.0.0.0"):
            continue
        if "." in d and len(d) <= 253:
            domains.append(d)
    return domains


async def sync_blocklist(source: BlocklistSource, db: Session) -> int:
    """Download one blocklist, update the source record, return domain count."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(source.url, follow_redirects=True)
            resp.raise_for_status()
        domains = _parse_hosts_file(resp.text)
        source.domain_count = len(domains)
        source.last_synced  = datetime.now(timezone.utc)
        source.last_error   = None
        db.commit()
        log.info(f"DNS: synced '{source.name}' — {len(domains)} domains")
        return len(domains)
    except Exception as exc:
        source.last_error = str(exc)[:512]
        db.commit()
        log.error(f"DNS: sync failed for '{source.name}': {exc}")
        return 0


async def rebuild_merged_blocklist(db: Session) -> int:
    """Re-download all active sources and write merged dnsmasq conf."""
    sources = db.query(BlocklistSource).filter(BlocklistSource.is_active == True).all()
    all_domains: set[str] = set()

    # Pull domains from each source
    for src in sources:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(src.url, follow_redirects=True)
                resp.raise_for_status()
            domains = _parse_hosts_file(resp.text)
            all_domains.update(domains)
            src.domain_count = len(domains)
            src.last_synced  = datetime.now(timezone.utc)
            src.last_error   = None
        except Exception as exc:
            src.last_error = str(exc)[:512]
            log.error(f"DNS: sync failed for '{src.name}': {exc}")

    # Apply global overrides — remove whitelisted domains
    overrides = db.query(DnsOverride).all()
    whitelist = {o.domain for o in overrides if o.action == "allow"}
    blocklist  = {o.domain for o in overrides if o.action == "block"}
    final_domains = (all_domains - whitelist) | blocklist

    db.commit()
    _write_merged_conf(final_domains)
    _reload_dnsmasq()
    return len(final_domains)


def _write_merged_conf(domains: set[str]) -> None:
    """Write dnsmasq address=/.domain/# entries for all blocked domains."""
    try:
        os.makedirs(BLOCKLIST_DIR, exist_ok=True)
        lines = [f"address=/{d}/#\n" for d in sorted(domains)]
        with open(MERGED_BLOCKLIST, "w") as f:
            f.write(f"# GhostWire merged blocklist — {len(domains)} domains\n")
            f.write(f"# Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
            f.writelines(lines)
        log.info(f"DNS: wrote {len(domains)} entries to {MERGED_BLOCKLIST}")
    except OSError as e:
        log.warning(f"DNS: could not write merged blocklist (dev mode?): {e}")


def write_user_conf(user_id: str, settings: UserDnsSettings) -> None:
    """Write per-user dnsmasq conf: whitelist (unblock) + blacklist (block) entries."""
    try:
        os.makedirs(DNSMASQ_CONF_DIR, exist_ok=True)
        path = os.path.join(DNSMASQ_CONF_DIR, f"user-{user_id}.conf")

        whitelist = json.loads(settings.custom_whitelist or "[]")
        blacklist = json.loads(settings.custom_blacklist or "[]")

        lines = [f"# GhostWire per-user overrides for {user_id}\n"]
        for d in whitelist:
            lines.append(f"server=/{d}/8.8.8.8\n")   # force resolve (unblock)
        for d in blacklist:
            lines.append(f"address=/{d}/#\n")         # block

        with open(path, "w") as f:
            f.writelines(lines)
        _reload_dnsmasq()
    except OSError as e:
        log.warning(f"DNS: could not write user conf (dev mode?): {e}")


def delete_user_conf(user_id: str) -> None:
    path = os.path.join(DNSMASQ_CONF_DIR, f"user-{user_id}.conf")
    try:
        if os.path.exists(path):
            os.remove(path)
            _reload_dnsmasq()
    except OSError as e:
        log.warning(f"DNS: could not remove user conf: {e}")


def _reload_dnsmasq() -> None:
    """Send SIGHUP to dnsmasq to reload config without dropping queries."""
    try:
        subprocess.run(["pkill", "-HUP", "dnsmasq"], check=False, timeout=5)
    except Exception as e:
        log.debug(f"DNS: dnsmasq reload skipped (dev mode?): {e}")


# ── Seed default blocklists ───────────────────────────────────────────────────

def seed_default_blocklists(db: Session) -> None:
    """Insert default blocklist sources if table is empty."""
    existing = db.query(BlocklistSource).count()
    if existing == 0:
        for bl in DEFAULT_BLOCKLISTS:
            db.add(BlocklistSource(name=bl["name"], url=bl["url"]))
        db.commit()
        log.info("DNS: seeded default blocklists")


# ── Analytics helpers ─────────────────────────────────────────────────────────

def get_top_blocked_domains(
    db: Session,
    user_id: Optional[str] = None,
    limit: int = 10,
    since: Optional[datetime] = None,
) -> list[dict]:
    q = db.query(DnsEvent.domain, func.count(DnsEvent.id).label("count")) \
          .filter(DnsEvent.action == "blocked")
    if user_id:
        q = q.filter(DnsEvent.user_id == user_id)
    if since:
        q = q.filter(DnsEvent.timestamp >= since)
    rows = q.group_by(DnsEvent.domain).order_by(desc("count")).limit(limit).all()
    return [{"domain": r.domain, "count": r.count} for r in rows]


def get_event_counts_by_hour(
    db: Session,
    user_id: Optional[str] = None,
    hours: int = 24,
) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    q = db.query(
        func.strftime("%Y-%m-%dT%H:00:00", DnsEvent.timestamp).label("hour"),
        DnsEvent.action,
        func.count(DnsEvent.id).label("count"),
    ).filter(DnsEvent.timestamp >= since)
    if user_id:
        q = q.filter(DnsEvent.user_id == user_id)
    rows = q.group_by("hour", DnsEvent.action).order_by("hour").all()
    return [{"hour": r.hour, "action": r.action, "count": r.count} for r in rows]


def get_summary_stats(
    db: Session,
    user_id: Optional[str] = None,
    since: Optional[datetime] = None,
) -> dict:
    if since is None:
        since = datetime.now(timezone.utc) - timedelta(hours=24)

    q_base = db.query(func.count(DnsEvent.id)).filter(DnsEvent.timestamp >= since)
    if user_id:
        q_base = q_base.filter(DnsEvent.user_id == user_id)

    total   = q_base.scalar() or 0
    blocked = (q_base.filter(DnsEvent.action == "blocked")).scalar() or 0  # type: ignore

    return {
        "total_queries": total,
        "blocked_count": blocked,
        "allowed_count": total - blocked,
        "block_rate":    round((blocked / total * 100) if total else 0, 1),
        "since": since.isoformat(),
    }

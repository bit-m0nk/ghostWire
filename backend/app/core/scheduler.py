"""GhostWire — Background scheduler v2
- swanctl --list-sas parser handles strongSwan 6.x vici output
- 16-second timeout for Pi Zero 2W
- Uses new infrastructure.db path
"""
import logging
import os
import re
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import Thread

log = logging.getLogger("ghostwire.scheduler")

_SUBPROCESS_ENV = {**os.environ, "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"}

# Pre-compiled regexes for swanctl --list-sas output
# IKE-SA block header: "  ikev2-eap: #3, ESTABLISHED, IKEv2, ..."
_IKE_RE     = re.compile(r'#(\d+),\s+ESTABLISHED')
# CHILD-SA virtual-IP assignment: "  10.10.0.2 === ..."  or  "local  10.10.0.2/32"
_VIP_RE     = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/32\b')
# Byte counters: "in 1234 bytes"  /  "out 5678 bytes"  (swanctl uses "in X bytes, Y packets")
_BYTES_RE   = re.compile(
    r'in\s+(\d+)\s+bytes[^,]*,\s*\d+\s+packets.*?out\s+(\d+)\s+bytes',
    re.DOTALL,
)


def _run_swanctl_list_sas() -> str:
    """Run swanctl --list-sas. Tries full path first, falls back to PATH lookup."""
    for cmd in (
        ["/usr/sbin/swanctl", "--list-sas"],
        ["swanctl", "--list-sas"],
    ):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=16, env=_SUBPROCESS_ENV)
            out = r.stdout
            if out and ("ESTABLISHED" in out or "CHILD_SA" in out or out.strip()):
                return out
            if r.stderr and "error" in r.stderr.lower():
                log.debug(f"swanctl list-sas stderr ({cmd[0]}): {r.stderr[:200]}")
        except subprocess.TimeoutExpired:
            log.debug(f"swanctl list-sas timed out ({cmd[0]})"); continue
        except FileNotFoundError:
            log.debug(f"swanctl not found at {cmd[0]}"); continue
        except Exception as e:
            log.debug(f"swanctl list-sas error ({cmd[0]}): {e}"); continue
    return ""


def _parse_swanctl_sas(output: str):
    """
    Parser for swanctl --list-sas output.

    swanctl groups output as IKE-SA blocks, each containing CHILD-SA sub-blocks.
    Example fragment:
        ikev2-eap: #3, ESTABLISHED, IKEv2, ...
          ikev2-eap: #4, reqid 1, INSTALLED, TUNNEL, ...
            local  10.10.0.1/32
            remote 10.10.0.2/32
            in  AES_CBC_256/HMAC_SHA2_256_128, 1234 bytes, 10 packets, 5s ago
            out AES_CBC_256/HMAC_SHA2_256_128, 5678 bytes, 20 packets, 5s ago

    Returns (active_uids: set, active_vips: set, vip_bytes: dict).
    """
    active_uids: set  = set()
    active_vips: set  = set()
    vip_bytes:   dict = {}

    # Collect IKE-SA unique IDs
    for m in _IKE_RE.finditer(output):
        active_uids.add(m.group(1))

    # Split into CHILD-SA blocks at lines with "INSTALLED" (child-sa header)
    # Each block spans until the next child-sa header or IKE-SA header
    child_blocks: list[str] = []
    current: list[str] = []
    for line in output.splitlines():
        if "INSTALLED" in line and ("TUNNEL" in line or "TRANSPORT" in line):
            if current:
                child_blocks.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        child_blocks.append("\n".join(current))

    for block in child_blocks:
        # Find the remote VIP (/32 on a "remote" line, or any /32 not on "local" line)
        vip = None
        for line in block.splitlines():
            vm = _VIP_RE.search(line)
            if vm and "local" not in line.lower():
                vip = vm.group(1)
                break
        if not vip:
            # Fallback: take any /32 found
            vm = _VIP_RE.search(block)
            if vm:
                vip = vm.group(1)

        if vip:
            active_vips.add(vip)
            # Parse byte counters.
            # strongSwan 5.x format: "in X bytes, Y packets"
            # strongSwan 6.x format: "in  HEX_SPI,  X bytes,  Y packets, Zs ago"
            # The regex must skip the optional SPI hex token (word of hex chars
            # followed by a comma) that appears in 6.x before the byte count.
            lines = block.splitlines()
            bytes_in = bytes_out = 0
            for line in lines:
                # Match: "in" then optional "HEX," then the number then "bytes"
                m_in  = re.search(r'\bin\s+(?:[0-9a-f]+,\s*)?(\d+)\s+bytes', line, re.IGNORECASE)
                m_out = re.search(r'\bout\s+(?:[0-9a-f]+,\s*)?(\d+)\s+bytes', line, re.IGNORECASE)
                if m_in:
                    bytes_in  = int(m_in.group(1))
                if m_out:
                    bytes_out = int(m_out.group(1))
            if bytes_in or bytes_out:
                vip_bytes[vip] = (bytes_in, bytes_out)

    return active_uids, active_vips, vip_bytes


def _sync_active_sessions():
    """Sync session state and byte counters every 10s.

    Also emits VPN_SESSION_STARTED / VPN_SESSION_ENDED events onto the
    in-process bus so that bot subscribers and the WebSocket relay react to
    sessions that were created/closed by the updown hook (a separate process
    that cannot touch the bus directly).
    """
    try:
        from app.infrastructure.db import SessionLocal
        from app.domains.vpn.models import VPNSession
        from app.infrastructure.events.bus import bus, Events

        output = _run_swanctl_list_sas()
        if not output:
            return

        active_uids, active_vips, vip_bytes = _parse_swanctl_sas(output)
        log.debug(
            f"swanctl list-sas: uids={active_uids} vips={active_vips} "
            f"bytes_keys={list(vip_bytes.keys())}"
        )

        db = SessionLocal()
        try:
            changed        = False
            ended_sessions  = []   # collect for event emission after commit
            started_sessions = []  # sessions we haven't seen as active before

            # Track which DB session IDs were active before this tick
            db_active = db.query(VPNSession).filter(VPNSession.is_active == True).all()

            for sess in db_active:
                sess_vip = (sess.virtual_ip or "").strip().split("/")[0]

                alive = (
                    (sess.session_key and sess.session_key in active_uids) or
                    (sess_vip and sess_vip in active_vips) or
                    (sess.username and len(sess.username) > 3 and sess.username in output)
                )

                if not alive:
                    sess.is_active = False
                    sess.disconnected_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    log.info(f"Session marked inactive: {sess.username}")
                    ended_sessions.append({
                        "session_id": sess.id,
                        "username":   sess.username or "unknown",
                        "client_ip":  sess.client_ip or "",
                        "virtual_ip": sess.virtual_ip or "",
                        "country_name": sess.country_name or "",
                    })
                    changed = True
                else:
                    if sess_vip and sess_vip in vip_bytes:
                        bi, bo = vip_bytes[sess_vip]
                        stored_in  = sess.bytes_in  if sess.bytes_in  is not None else -1
                        stored_out = sess.bytes_out if sess.bytes_out is not None else -1
                        if bi != stored_in or bo != stored_out:
                            sess.bytes_in  = bi
                            sess.bytes_out = bo
                            changed = True
                            log.debug(f"Bytes updated {sess.username}: in={bi} out={bo}")

            # Detect newly-active sessions (created by updown hook since last tick)
            # We recognise them by checking for is_active=True rows that have no
            # bytes_in yet (brand-new) OR whose session_key just appeared in active_uids.
            # Use a simple heuristic: sessions connected within the last 30 seconds
            # that haven't been seen before in this scheduler run.
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=30)
            new_sessions = db.query(VPNSession).filter(
                VPNSession.is_active == True,
                VPNSession.connected_at >= cutoff,
                VPNSession.bytes_in.is_(None),  # not yet updated by scheduler
            ).all()
            for ns in new_sessions:
                started_sessions.append({
                    "session_id": ns.id,
                    "username":   ns.username or "unknown",
                    "user_id":    ns.user_id or "",
                    "client_ip":  ns.client_ip or "",
                    "virtual_ip": ns.virtual_ip or "",
                    "country_name": ns.country_name or "",
                })

            if changed:
                db.commit()

        finally:
            db.close()

        # Emit events outside the DB session
        for payload in ended_sessions:
            try:
                bus.emit(Events.VPN_SESSION_ENDED, payload)
            except Exception as exc:
                log.debug(f"Event emit VPN_SESSION_ENDED error: {exc}")

        for payload in started_sessions:
            try:
                bus.emit(Events.VPN_SESSION_STARTED, payload)
            except Exception as exc:
                log.debug(f"Event emit VPN_SESSION_STARTED error: {exc}")

    except Exception as e:
        log.warning(f"Session sync error: {e}")


def _cleanup_old_sessions():
    try:
        from app.infrastructure.db import SessionLocal
        from app.domains.vpn.models import VPNSession
        db = SessionLocal()
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).replace(tzinfo=None)
            deleted = db.query(VPNSession).filter(
                VPNSession.connected_at < cutoff, VPNSession.is_active == False
            ).delete()
            db.commit()
            if deleted:
                log.info(f"Cleaned up {deleted} old sessions")
        finally:
            db.close()
    except Exception as e:
        log.debug(f"Session cleanup error: {e}")


def _download_geoip():
    from app.core.config import settings
    geoip_path = Path(settings.GEOIP_DB)
    if geoip_path.exists():
        return
    ettercap = Path("/usr/share/ettercap/GeoLite2-Country.mmdb")
    if ettercap.exists():
        try:
            import shutil
            geoip_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ettercap, geoip_path)
            log.info("GeoIP DB copied from ettercap")
            return
        except Exception as e:
            log.warning(f"GeoIP ettercap copy failed: {e}")
    try:
        import urllib.request, gzip, shutil
        from datetime import datetime as dt
        geoip_path.parent.mkdir(parents=True, exist_ok=True)
        now = dt.now()
        for year, month in [
            (now.year, now.month),
            (now.year if now.month > 1 else now.year - 1,
             now.month - 1 if now.month > 1 else 12),
        ]:
            url = (
                f"https://download.db-ip.com/free/"
                f"dbip-country-lite-{year}-{month:02d}.mmdb.gz"
            )
            try:
                gz = geoip_path.parent / "geoip.mmdb.gz"
                urllib.request.urlretrieve(url, gz)
                with gzip.open(gz, "rb") as fi, open(geoip_path, "wb") as fo:
                    shutil.copyfileobj(fi, fo)
                gz.unlink(missing_ok=True)
                log.info("GeoIP DB downloaded")
                return
            except Exception as e:
                log.warning(f"GeoIP download failed {year}-{month:02d}: {e}")
    except Exception as e:
        log.warning(f"GeoIP setup failed: {e}")


def _rollup_dns_daily_summary():
    """Pre-aggregate yesterday's DNS events into DailySummary rows.
    Runs once per day.  Safe to run multiple times — upserts by (user_id, date).
    """
    try:
        import json
        from datetime import date
        from sqlalchemy import func, desc
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        from app.infrastructure.db import SessionLocal
        from app.domains.dns.models import DnsEvent
        from app.domains.analytics.models import DailySummary

        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        start     = datetime(yesterday.year, yesterday.month, yesterday.day,
                             0, 0, 0, tzinfo=timezone.utc)
        end       = start + timedelta(days=1)

        db = SessionLocal()
        try:
            # Collect all user_ids that had events yesterday
            user_ids_raw = (
                db.query(DnsEvent.user_id)
                  .filter(DnsEvent.timestamp >= start, DnsEvent.timestamp < end)
                  .distinct()
                  .all()
            )
            user_ids = [r.user_id for r in user_ids_raw]  # includes None

            for uid in user_ids:
                q = db.query(DnsEvent).filter(
                    DnsEvent.timestamp >= start, DnsEvent.timestamp < end
                )
                if uid is not None:
                    q = q.filter(DnsEvent.user_id == uid)
                else:
                    q = q.filter(DnsEvent.user_id.is_(None))

                total   = q.count()
                blocked = q.filter(DnsEvent.action == "blocked").count()
                allowed = total - blocked
                rate    = round((blocked / total * 100) if total else 0, 1)

                # Top 10 blocked for this user/day
                top = (
                    db.query(DnsEvent.domain, func.count(DnsEvent.id).label("cnt"))
                      .filter(
                          DnsEvent.timestamp >= start,
                          DnsEvent.timestamp < end,
                          DnsEvent.action == "blocked",
                          DnsEvent.user_id == uid if uid else DnsEvent.user_id.is_(None),
                      )
                      .group_by(DnsEvent.domain)
                      .order_by(desc("cnt"))
                      .limit(10)
                      .all()
                )
                top_json = json.dumps([{"domain": r.domain, "count": r.cnt} for r in top])

                # Upsert (SQLite INSERT OR REPLACE via merge pattern)
                existing = (
                    db.query(DailySummary)
                      .filter(DailySummary.user_id == uid,
                              DailySummary.summary_date == yesterday)
                      .first()
                )
                if existing:
                    existing.total_queries    = total
                    existing.blocked_count    = blocked
                    existing.allowed_count    = allowed
                    existing.block_rate       = rate
                    existing.top_blocked_json = top_json
                    existing.updated_at       = datetime.now(timezone.utc)
                else:
                    db.add(DailySummary(
                        user_id=uid,
                        summary_date=yesterday,
                        total_queries=total,
                        blocked_count=blocked,
                        allowed_count=allowed,
                        block_rate=rate,
                        top_blocked_json=top_json,
                    ))
            db.commit()
            log.info(f"DNS daily rollup complete for {yesterday}: {len(user_ids)} user(s)")
        finally:
            db.close()
    except Exception as e:
        log.warning(f"DNS daily rollup error: {e}")


# ── DNS log tailer state ──────────────────────────────────────────────────────
# Tracks the file inode + byte offset so we only parse NEW lines each tick.
# Reset automatically when the log is rotated (inode changes).
_dns_log_state: dict = {"inode": None, "offset": 0}

# dnsmasq query log format examples:
#   Apr 19 12:00:01 dnsmasq[1234]: query[A] ads.example.com from 10.10.0.2
#   Apr 19 12:00:01 dnsmasq[1234]: /opt/ghostwire/blocklists/merged.conf ads.example.com is NXDOMAIN
#   Apr 19 12:00:01 dnsmasq[1234]: config ads.example.com is NXDOMAIN
_DNS_QUERY_RE = re.compile(r"query\[(?:A|AAAA|PTR)\]\s+([\w.\-]+)\s+from\s+([\d.]+)")
_DNS_BLOCK_RE = re.compile(r"(?:config|address)\s+([\w.\-]+)\s+is\s+(?:NXDOMAIN|0\.0\.0\.0)")
_DNS_LOGFILE  = "/var/log/dnsmasq/query.log"


def _tail_dns_log() -> None:
    """
    Read new lines from the dnsmasq query log and persist them as DnsEvent rows.

    Strategy:
    - Track file inode + byte offset between calls so we only parse new data.
    - Detect log rotation (inode change) and restart from offset 0.
    - Match query lines to virtual-IP → user mapping via VPN sessions.
    - A line matches a block if a NXDOMAIN/config line follows the query line
      for the same domain within the same log batch.
    - Batch-insert up to 2 000 events per tick to avoid DB pressure on a Pi.
    """
    global _dns_log_state
    try:
        import os as _os
        if not _os.path.exists(_DNS_LOGFILE):
            return

        stat = _os.stat(_DNS_LOGFILE)
        current_inode = stat.st_ino

        # Detect log rotation
        if _dns_log_state["inode"] != current_inode:
            _dns_log_state = {"inode": current_inode, "offset": 0}
            log.debug("DNS log tailer: new inode detected (log rotated or first run)")

        # Nothing new since last tick
        if stat.st_size <= _dns_log_state["offset"]:
            return

        with open(_DNS_LOGFILE, "r", errors="replace") as fh:
            fh.seek(_dns_log_state["offset"])
            new_lines = fh.readlines(512 * 1024)  # max 512 KB per tick
            _dns_log_state["offset"] = fh.tell()

        if not new_lines:
            return

        # ── Parse lines into (domain, client_ip, action) tuples ──────────────
        # Two-pass: first collect all queried domains per client IP,
        # then mark any that appear in a block line as "blocked".
        queries: list[tuple[str, str]] = []   # (domain, client_ip)
        blocked_domains: set[str]      = set()

        for line in new_lines:
            qm = _DNS_QUERY_RE.search(line)
            if qm:
                domain = qm.group(1).lower().rstrip(".")
                client_ip = qm.group(2)
                # Skip reverse-lookup noise
                if not domain.endswith(".arpa"):
                    queries.append((domain, client_ip))
                continue

            bm = _DNS_BLOCK_RE.search(line)
            if bm:
                blocked_domains.add(bm.group(1).lower().rstrip("."))

        if not queries:
            return

        # Cap batch size to protect the DB on very noisy networks
        queries = queries[:2000]

        # ── Map client VIPs to user_ids via active VPN sessions ───────────────
        from app.infrastructure.db import SessionLocal
        from app.domains.dns.models import DnsEvent
        from app.domains.vpn.models import VPNSession

        db = SessionLocal()
        try:
            # Build {virtual_ip: user_id} from currently (or recently) active sessions
            active_rows = db.query(
                VPNSession.virtual_ip, VPNSession.user_id
            ).filter(VPNSession.is_active == True).all()
            # Also include sessions disconnected in the last 2 minutes (log may lag)
            from datetime import timedelta as _td
            recent_cutoff = (
                datetime.now(timezone.utc) - _td(minutes=2)
            ).replace(tzinfo=None)
            recent_rows = db.query(
                VPNSession.virtual_ip, VPNSession.user_id
            ).filter(
                VPNSession.is_active == False,
                VPNSession.disconnected_at >= recent_cutoff,
            ).all()

            vip_to_user: dict[str, str] = {}
            for vip, uid in (*active_rows, *recent_rows):
                if vip:
                    vip_to_user[vip.strip().split("/")[0]] = uid

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            events = []
            for domain, client_ip in queries:
                action  = "blocked" if domain in blocked_domains else "allowed"
                user_id = vip_to_user.get(client_ip)
                events.append(DnsEvent(
                    domain    = domain,
                    client_ip = client_ip,
                    action    = action,
                    user_id   = user_id,
                    timestamp = now,
                ))

            if events:
                db.bulk_save_objects(events)
                db.commit()
                blocked_n = sum(1 for e in events if e.action == "blocked")
                log.debug(
                    f"DNS tailer: +{len(events)} events "
                    f"({blocked_n} blocked, {len(events)-blocked_n} allowed)"
                )
        finally:
            db.close()

    except Exception as exc:
        log.warning(f"DNS log tailer error: {exc}")


def _scheduler_loop():
    import time
    tick = 0
    _download_geoip()
    while True:
        time.sleep(10)
        tick += 1
        _sync_active_sessions()
        # Phase 3: DNS log tailer — every tick (every 10s) to keep analytics fresh
        _tail_dns_log()
        if tick % 2160 == 0:
            _cleanup_old_sessions()
        # Phase 3: DNS daily rollup — every 8640 ticks (8640 × 10s = 24h)
        if tick % 8640 == 0:
            _rollup_dns_daily_summary()
        # Phase 4: Node health checks — every 18 ticks (3 min)
        if tick % 18 == 0:
            _check_nodes()
        # Phase 6: Update check — every 2160 ticks (6h)
        if tick % 2160 == 0:
            _check_updates()
        if tick % 267840 == 0:
            _download_geoip()


def start_scheduler():
    t = Thread(target=_scheduler_loop, daemon=True)
    t.start()
    log.info("Scheduler started (v2) — 10s interval, swanctl --list-sas parser")


def _check_nodes():
    """Phase 4 — ping all registered remote nodes every 3 minutes."""
    try:
        from app.infrastructure.db import SessionLocal
        from app.domains.nodes.service import check_all_nodes
        with SessionLocal() as db:
            check_all_nodes(db)
    except Exception as e:
        log.debug(f"Node health check error: {e}")


def _check_updates():
    """Phase 6 — refresh GitHub release check every 6 hours."""
    try:
        from app.domains.updates.router import fetch_latest_release
        fetch_latest_release()
    except Exception as e:
        log.debug(f"Update check error: {e}")

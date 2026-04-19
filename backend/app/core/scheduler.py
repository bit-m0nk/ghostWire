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
    """Sync session state and byte counters every 10s."""
    try:
        from app.infrastructure.db import SessionLocal
        from app.domains.vpn.models import VPNSession

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
            changed = False
            for sess in db.query(VPNSession).filter(VPNSession.is_active == True).all():
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
            if changed:
                db.commit()
        finally:
            db.close()
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


def _scheduler_loop():
    import time
    tick = 0
    _download_geoip()
    while True:
        time.sleep(10)
        tick += 1
        _sync_active_sessions()
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

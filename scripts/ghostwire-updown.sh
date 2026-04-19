#!/bin/bash
# =============================================================
# GhostWire — strongSwan updown hook v5.2
# Called by charon's updown plugin on every VPN connect/disconnect.
#
# Requires: charon updown plugin loaded (libcharon-extra-plugins).
# Uses: swanctl --list-sas (vici interface) — NOT ipsec statusall.
# PLUTO_* variables are injected by the updown plugin; if they are
# absent the script exits immediately with a clear error message.
# =============================================================

INSTALL_DIR="/opt/ghostwire"
LOG="/var/log/ghostwire/updown.log"
PYTHON="$INSTALL_DIR/venv/bin/python3"
mkdir -p "$(dirname "$LOG")"

_log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') VERB=$PLUTO_VERB CONN=$PLUTO_CONNECTION PEER=$PLUTO_PEER XAUTH=$PLUTO_XAUTH_ID PEER_ID=$PLUTO_PEER_ID VIP=$PLUTO_PEER_SOURCEIP UID=$PLUTO_UNIQUEID" >> "$LOG"
}

# ── PLUTO_* variable guard ─────────────────────────────────────────────────────
# These variables are injected by charon's *updown* plugin
# (libcharon-extra-plugins). If PLUTO_VERB is empty the plugin is not loaded.
# Ensure strongswan.conf contains:
#   charon { plugins { updown {} } }
# or that the updown plugin .conf file exists in strongswan.d/charon/.
if [ -z "$PLUTO_VERB" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [updown] ERROR: PLUTO_VERB is unset — charon updown plugin not loaded. Check strongswan.conf." >> "$LOG"
    exit 1
fi

case "$PLUTO_VERB" in
    up-client|up-client-v6)
        _log
        XAUTH_ID="$PLUTO_XAUTH_ID"
        PEER_ID="$PLUTO_PEER_ID"
        CLIENT_IP="$PLUTO_PEER"
        VIP="${PLUTO_PEER_SOURCEIP%%/*}"   # strip /32 suffix
        UNIQUE_ID="$PLUTO_UNIQUEID"
        CONN_NAME="$PLUTO_CONNECTION"

        "$PYTHON" >> "$LOG" 2>&1 << PYEOF
import sys, os, re
sys.path.insert(0, "$INSTALL_DIR/backend")
from dotenv import load_dotenv
load_dotenv("/opt/ghostwire/.env")
from app.infrastructure.db import SessionLocal
from app.domains.vpn.models import VPNSession
from app.domains.users.models import User
from datetime import datetime, timezone

xauth_id  = r"""$XAUTH_ID""".strip()
peer_id   = r"""$PEER_ID""".strip()
client_ip = r"""$CLIENT_IP""".strip()
vip       = r"""$VIP""".strip()
unique_id = r"""$UNIQUE_ID""".strip()
conn      = r"""$CONN_NAME""".strip()

print(f"[updown UP] conn={conn} xauth={xauth_id!r} peer_id={peer_id!r} ip={client_ip} vip={vip} uid={unique_id}")

def is_not_username(s):
    if not s or not s.strip(): return True
    s = s.strip()
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', s): return True
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}[:/]', s): return True
    if '.' in s and '@' not in s and re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}$', s): return True
    return False

username = ""
if peer_id and not is_not_username(peer_id):
    username = peer_id
elif xauth_id and not is_not_username(xauth_id):
    username = xauth_id

print(f"[updown UP] resolved username={username!r}")

db = SessionLocal()
try:
    user = None
    if username:
        user = db.query(User).filter(User.vpn_username == username).first()
        if not user:
            clean = re.sub(r'^[^\\\\]+\\\\', '', username)
            if clean != username:
                user = db.query(User).filter(User.vpn_username == clean).first()
                if user: username = clean

    if unique_id:
        for stale in db.query(VPNSession).filter(
            VPNSession.session_key == unique_id, VPNSession.is_active == True
        ).all():
            stale.is_active = False
            stale.disconnected_at = datetime.now(timezone.utc).replace(tzinfo=None)

    country, country_name = "??", "Unknown"
    try:
        db_path = "/opt/ghostwire/data/GeoLite2-Country.mmdb"
        if os.path.exists(db_path) and client_ip and not client_ip.startswith(('10.', '192.168.', '172.')):
            try:
                import geoip2.database
                with geoip2.database.Reader(db_path) as reader:
                    r = reader.country(client_ip)
                    country, country_name = r.country.iso_code or "??", r.country.name or "Unknown"
            except ImportError:
                import maxminddb
                with maxminddb.open_database(db_path) as r:
                    rec = r.get(client_ip)
                    if rec and "country" in rec:
                        country = rec["country"].get("iso_code", "??")
                        country_name = rec["country"]["names"].get("en", "Unknown")
    except Exception as e:
        print(f"[updown UP] GeoIP error: {e}")

    sess = VPNSession(
        user_id=user.id if user else "unknown",
        username=username or f"psk_{vip or client_ip}",
        client_ip=client_ip, virtual_ip=vip,
        country=country, country_name=country_name,
        device_info=conn, is_active=True,
        session_key=unique_id or None,
        connected_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(sess)
    db.commit()
    print(f"[updown UP] Session created: user={sess.username} vip={vip} country={country_name}")
except Exception as ex:
    print(f"[updown UP] ERROR: {ex}")
    import traceback; traceback.print_exc()
finally:
    db.close()
PYEOF
        ;;

    down-client|down-client-v6)
        _log
        XAUTH_ID="$PLUTO_XAUTH_ID"
        PEER_ID="$PLUTO_PEER_ID"
        CLIENT_IP="$PLUTO_PEER"
        UNIQUE_ID="$PLUTO_UNIQUEID"
        CONN_NAME="$PLUTO_CONNECTION"

        # CRITICAL: timeout 5 prevents this hook from hanging forever
        # if charon's vici socket is unavailable.
        FINAL_STATUSALL=$(timeout 5 swanctl --list-sas 2>/dev/null || true)

        "$PYTHON" >> "$LOG" 2>&1 << PYEOF
import sys, os, re
sys.path.insert(0, "$INSTALL_DIR/backend")
from dotenv import load_dotenv
load_dotenv("/opt/ghostwire/.env")
from app.infrastructure.db import SessionLocal
from app.domains.vpn.models import VPNSession
from datetime import datetime, timezone

xauth_id  = r"""$XAUTH_ID""".strip()
peer_id   = r"""$PEER_ID""".strip()
client_ip = r"""$CLIENT_IP""".strip()
unique_id = r"""$UNIQUE_ID""".strip()
conn      = r"""$CONN_NAME""".strip()
statusall = r"""$FINAL_STATUSALL"""

print(f"[updown DOWN] conn={conn} uid={unique_id} ip={client_ip}")

def is_not_username(s):
    if not s or not s.strip(): return True
    s = s.strip()
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', s): return True
    if '.' in s and '@' not in s and re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}$', s): return True
    return False

if peer_id and not is_not_username(peer_id):
    username = peer_id
elif xauth_id and not is_not_username(xauth_id):
    username = xauth_id
else:
    username = ""

def parse_bytes(output, target_ip):
    """Block-based parser — finds bytes for target_ip in swanctl --list-sas output.

    swanctl CHILD-SA blocks look like:
      ikev2-eap: #3, ESTABLISHED, IKEv2, ...
        ghostwire-vpn{1}:  INSTALLED, TUNNEL, ...
          10.10.0.2/32 === 0.0.0.0/0
          in  AES_CBC_256/HMAC_SHA2_256_128, 1234 bytes, 10 packets, 5s ago
          out AES_CBC_256/HMAC_SHA2_256_128, 5678 bytes, 20 packets, 3s ago
    """
    target = (target_ip or "").strip().split("/")[0]
    if not target: return None, None
    # swanctl CHILD-SA opener: lines containing INSTALLED and TUNNEL or TRANSPORT
    _CHILD_SA_RE = re.compile(r'INSTALLED,\s+(?:TUNNEL|TRANSPORT)')
    _VIP_RE      = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/32')
    # swanctl byte format: "in  <cipher>, <N> bytes" / "out  <cipher>, <N> bytes"
    _BYTES_IN_RE  = re.compile(r'^\s+in\s+\S[^,]*,\s*(\d+)\s+bytes', re.MULTILINE)
    _BYTES_OUT_RE = re.compile(r'^\s+out\s+\S[^,]*,\s*(\d+)\s+bytes', re.MULTILINE)
    blocks = []
    current_block = None
    for line in output.splitlines():
        if _CHILD_SA_RE.search(line):
            current_block = [line]
            blocks.append(current_block)
        elif current_block is not None:
            if line.startswith(" ") or line.startswith("\t"):
                current_block.append(line)
            else:
                current_block = None
    for block_lines in blocks:
        block_text = "\n".join(block_lines)
        vm = _VIP_RE.search(block_text)
        if vm and vm.group(1) == target:
            bm_in  = _BYTES_IN_RE.search(block_text)
            bm_out = _BYTES_OUT_RE.search(block_text)
            if bm_in and bm_out:
                return int(bm_in.group(1)), int(bm_out.group(1))
    return None, None

db = SessionLocal()
try:
    sess = None
    if unique_id:
        sess = db.query(VPNSession).filter(
            VPNSession.session_key == unique_id, VPNSession.is_active == True
        ).first()
    if not sess and username:
        sess = db.query(VPNSession).filter(
            VPNSession.username == username, VPNSession.is_active == True
        ).order_by(VPNSession.connected_at.desc()).first()
    if not sess and client_ip:
        sess = db.query(VPNSession).filter(
            VPNSession.client_ip == client_ip, VPNSession.is_active == True
        ).order_by(VPNSession.connected_at.desc()).first()

    if sess:
        if sess.virtual_ip and statusall:
            bi, bo = parse_bytes(statusall, sess.virtual_ip)
            if bi is not None:
                sess.bytes_in, sess.bytes_out = bi, bo
                print(f"[updown DOWN] Final bytes: in={bi} out={bo}")
        sess.is_active = False
        sess.disconnected_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        print(f"[updown DOWN] Session closed: {sess.username} bytes_in={sess.bytes_in} bytes_out={sess.bytes_out}")
    else:
        print(f"[updown DOWN] No active session for uid={unique_id} ip={client_ip}")
except Exception as ex:
    print(f"[updown DOWN] ERROR: {ex}")
    import traceback; traceback.print_exc()
finally:
    db.close()
PYEOF
        ;;
esac
exit 0

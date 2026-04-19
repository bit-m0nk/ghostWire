#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
#  GhostWire — fix-iphone-ipsec.sh
#
#  Fixes: "found N matching configs, but none allows XAuthInitPSK using Main Mode"
#
#  Root cause: iOS built-in IPSec (Settings → VPN → Type: IPSec) uses
#  IKEv1 Main Mode. The GhostWire config must have a connection block with
#  aggressive = no AND auth = xauth in the remote section.
#
#  This script:
#    1. Detects your server ID from the installed config / .env
#    2. Checks whether a proper Main Mode block exists
#    3. Rewrites /etc/swanctl/conf.d/ghostwire.conf with correct IKEv1 blocks
#    4. Verifies xauth-generic plugin is loaded
#    5. Reloads swanctl — no full restart needed
#
#  Usage:  sudo bash fix-iphone-ipsec.sh
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
info() { echo -e "${CYAN}  →${NC} $*"; }
warn() { echo -e "${YELLOW}  ⚠${NC} $*"; }
fail() { echo -e "${RED}  ✗${NC} $*"; exit 1; }

[ "$(id -u)" -ne 0 ] && fail "Run as root: sudo bash $0"

INSTALL_DIR="${INSTALL_DIR:-/opt/ghostwire}"
CONF="/etc/swanctl/conf.d/ghostwire.conf"
UPDOWN="${INSTALL_DIR}/scripts/ghostwire-updown.sh"

echo ""
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}   GhostWire — iPhone IPSec Main Mode Fix${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
echo ""

[ -f "$CONF" ] || fail "$CONF not found. Is GhostWire installed?"

# ── Step 1: Detect server ID ──────────────────────────────────────────────────
info "Detecting server identity..."
SERVER_ID=""

# Try swanctl.conf first
SERVER_ID=$(python3 -c "
import re, sys
conf = open('${CONF}').read()
# Look for id = in ikev2-eap local block
m = re.search(r'ikev2-eap\s*\{.*?local\s*\{.*?id\s*=\s*([^\n]+)', conf, re.DOTALL)
if m:
    print(m.group(1).strip())
    sys.exit(0)
# Fallback: any id = line
m = re.search(r'^\s*id\s*=\s*([^\n]+)', conf, re.MULTILINE)
if m:
    print(m.group(1).strip())
" 2>/dev/null || true)

# Try .env
if [ -z "$SERVER_ID" ] && [ -f "${INSTALL_DIR}/.env" ]; then
    SERVER_ID=$(grep -E '^(DDNS_HOSTNAME|SERVER_HOSTNAME|PUBLIC_IP)=' "${INSTALL_DIR}/.env" 2>/dev/null \
        | head -1 | cut -d= -f2 | tr -d '"' || true)
fi

# Last resort: system hostname
[ -z "$SERVER_ID" ] && SERVER_ID=$(hostname -f 2>/dev/null || hostname)
ok "Server ID: $SERVER_ID"

# ── Step 2: Check xauth-generic plugin ───────────────────────────────────────
info "Verifying xauth-generic plugin..."
mkdir -p /etc/strongswan.d/charon
cat > /etc/strongswan.d/charon/xauth-generic.conf << 'XAUTH'
xauth-generic {
    load = yes
}
XAUTH
ok "xauth-generic plugin enabled"

# Check strongswan.conf has aggressive mode allowed
if ! grep -q 'i_dont_care_about_security_and_use_aggressive_mode_psk' /etc/strongswan.conf 2>/dev/null; then
    warn "Adding aggressive mode PSK permission to /etc/strongswan.conf"
    # Append inside charon {} block or create file
    if grep -q '^charon {' /etc/strongswan.conf 2>/dev/null; then
        sed -i '/^charon {/a\    i_dont_care_about_security_and_use_aggressive_mode_psk = yes' /etc/strongswan.conf
    else
        cat >> /etc/strongswan.conf << 'SWCONF'

charon {
    i_dont_care_about_security_and_use_aggressive_mode_psk = yes
    load_modular = yes
    plugins {
        include strongswan.d/charon/*.conf
    }
}
include strongswan.d/*.conf
SWCONF
    fi
    ok "strongswan.conf updated"
fi

# ── Step 3: Diagnose current IKEv1 config ────────────────────────────────────
info "Diagnosing current IKEv1 config..."

HAS_MAINMODE=$(grep -c 'aggressive = no' "$CONF" 2>/dev/null || echo 0)
HAS_XAUTH_REMOTE=$(grep -c 'auth = xauth' "$CONF" 2>/dev/null || echo 0)
HAS_OLD_XAUTH=$(grep -c 'ikev1-xauth-psk' "$CONF" 2>/dev/null || echo 0)

echo "    Main Mode blocks (aggressive = no): $HAS_MAINMODE"
echo "    XAuth remote blocks (auth = xauth): $HAS_XAUTH_REMOTE"
echo "    Existing ikev1 blocks: $HAS_OLD_XAUTH"

if [ "$HAS_MAINMODE" -ge 1 ] && [ "$HAS_XAUTH_REMOTE" -ge 1 ]; then
    ok "Config looks correct already — reloading to be sure"
else
    # ── Step 4: Patch the config ──────────────────────────────────────────────
    info "Patching swanctl config — backing up first..."
    cp "$CONF" "${CONF}.bak.$(date +%s)"
    ok "Backup saved"

    info "Writing corrected IKEv1 XAuth blocks..."

    python3 << PYEOF
import re, sys

conf = open('${CONF}').read()
server_id = '${SERVER_ID}'
updown = '${UPDOWN}'

# Remove ALL existing ikev1-xauth-psk* blocks (we'll replace them)
# Match from the connection name to the closing brace at the same indent level
conf = re.sub(
    r'\n\s+# (?:──[^\n]*IKEv1[^\n]*\n\s+#[^\n]*\n\s+)?ikev1-xauth-psk[^\n]*\n(?:(?!\n\s+[a-z]|\n\s+#|\n\s*\}).)*?\n\s+\}',
    '',
    conf,
    flags=re.DOTALL
)

# Also strip with a simpler fallback
conf = re.sub(
    r'[ \t]+ikev1-xauth-psk(?:-agr)?\s*\{[^}]*(?:\{[^}]*\}[^}]*)?\}[ \t]*\n',
    '',
    conf,
    flags=re.DOTALL
)

new_blocks = """
    # ── IKEv1 XAuth — Main Mode (iOS 15+ "IPSec" type) ───────────────────────
    # iOS sends IKEv1 Main Mode. The block MUST have aggressive = no and
    # remote.auth = xauth. The server uses PSK phase-1, then XAuth phase-2.
    ikev1-xauth-psk {
        version = 1
        proposals = aes256-sha256-modp2048,aes256-sha1-modp2048,aes256-sha1-modp1024,aes128-sha1-modp1024,3des-sha1-modp1024
        rekey_time = 0s
        dpd_delay = 30s
        dpd_timeout = 90s
        local_addrs = %any
        aggressive = no
        encap = yes
        unique = never

        local {
            auth = psk
            id = """ + server_id + """
        }
        remote {
            auth = xauth
            id = %any
        }
        children {
            ikev1-xauth-psk {
                local_ts      = 0.0.0.0/0
                updown        = """ + updown + """
                esp_proposals = aes256-sha256,aes256-sha1,aes128-sha1,3des-sha1
                dpd_action    = clear
            }
        }
        pools = vpn-pool
    }

    # ── IKEv1 XAuth — Aggressive Mode (older iOS, Android XAuth PSK) ─────────
    ikev1-xauth-psk-agr {
        version = 1
        proposals = aes256-sha256-modp2048,aes256-sha1-modp2048,aes256-sha1-modp1024,aes128-sha1-modp1024,3des-sha1-modp1024
        rekey_time = 0s
        dpd_delay = 30s
        dpd_timeout = 90s
        local_addrs = %any
        aggressive = yes
        encap = yes
        unique = never

        local {
            auth = psk
            id = %any
        }
        remote {
            auth = xauth
            id = %any
        }
        children {
            ikev1-xauth-psk-agr {
                local_ts      = 0.0.0.0/0
                updown        = """ + updown + """
                esp_proposals = aes256-sha256,aes256-sha1,aes128-sha1,3des-sha1
                dpd_action    = clear
            }
        }
        pools = vpn-pool
    }
"""

# Insert new blocks before the closing brace of the connections block
# Find the last connection block's closing brace before the top-level closing }
insert_pos = conf.rfind('\n}')
if insert_pos == -1:
    print("ERROR: cannot find closing brace in config", file=sys.stderr)
    sys.exit(1)

conf = conf[:insert_pos] + new_blocks + conf[insert_pos:]
open('${CONF}', 'w').write(conf)
print("Config patched successfully")
PYEOF

    ok "swanctl config updated"
fi

# ── Step 5: Reload swanctl ────────────────────────────────────────────────────
info "Reloading swanctl connections and credentials..."
if swanctl --load-all 2>&1; then
    ok "swanctl reloaded"
else
    warn "swanctl --load-all had warnings. Trying individual commands..."
    swanctl --load-conns 2>&1 || true
    swanctl --load-creds 2>&1 || true
    swanctl --load-pools 2>&1 || true
fi

# ── Step 6: Verify ───────────────────────────────────────────────────────────
echo ""
info "Active IKEv1 connection configs:"
swanctl --list-conns 2>/dev/null | grep -E 'ikev1' || warn "No IKEv1 connections visible — check swanctl --list-conns manually"

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓  iPhone IPSec fix applied!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo ""
echo "  On your iPhone:"
echo "  1. Delete the existing IPSec VPN profile"
echo "  2. Re-add it: Settings → General → VPN → Add VPN Configuration"
echo "     Type: IPSec"
echo "     Description: $(grep -o 'VPN_BRAND=[^ ]*' ${INSTALL_DIR}/.env 2>/dev/null | cut -d= -f2 | tr -d '\"' || echo 'GhostWire') VPN"
echo "     Server: $SERVER_ID"
echo "     Account: <your VPN username>"
echo "     Password: <your VPN password>"
echo "     Group Name: (leave blank)"
echo "     Secret: <PSK from admin panel>"
echo ""
echo "  OR re-download the .mobileconfig from the VPN portal (includes IPSec profile)."
echo ""

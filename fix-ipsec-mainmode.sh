#!/usr/bin/env bash
# GhostWire — Fix IKEv1 XAuth Main Mode for iOS
# iOS 15+ sends IKEv1 Main Mode; the old config only had aggressive=yes
# which rejected Main Mode with AUTH_FAILED. This script patches swanctl.conf
# to add a Main Mode connection alongside the existing Aggressive Mode one.
#
# Safe to run on an already-installed server. Restarts strongSwan at the end.
set -euo pipefail

CONF="/etc/swanctl/conf.d/ghostwire.conf"
INSTALL_DIR="${INSTALL_DIR:-/opt/ghostwire}"
UPDOWN="${INSTALL_DIR}/scripts/ghostwire-updown.sh"

if [[ ! -f "$CONF" ]]; then
  echo "ERROR: $CONF not found. Is GhostWire installed?"
  exit 1
fi

# Read current server ID from the ikev2-eap connection block
SERVER_ID=$(grep -A20 'ikev2-eap {' "$CONF" | grep '^\s*id\s*=' | head -1 | awk -F'=' '{print $2}' | tr -d ' ')
if [[ -z "$SERVER_ID" ]]; then
  # Fall back to reading from .env
  SERVER_ID=$(grep '^SERVER_HOSTNAME=' "${INSTALL_DIR}/.env" 2>/dev/null | cut -d= -f2 | tr -d '"' || hostname -f)
fi
echo "Server ID: $SERVER_ID"

# Check if fix already applied
if grep -q 'ikev1-xauth-psk-agr' "$CONF"; then
  echo "Fix already applied (ikev1-xauth-psk-agr block exists). Verifying main mode block..."
  if grep -q 'aggressive = no' "$CONF"; then
    echo "Main Mode block already present. Nothing to do."
    exit 0
  fi
fi

echo "Backing up $CONF → ${CONF}.bak"
cp "$CONF" "${CONF}.bak"

# Patch: replace the single ikev1-xauth-psk block with two blocks
python3 << PYEOF
import re, sys

conf = open('${CONF}').read()

old_block = re.search(
    r'(\s+# ──[^\n]*IKEv1[^\n]*\n(?:\s+#[^\n]*\n)*\s+ikev1-xauth-psk \{.*?pools = vpn-pool\n\s+\})',
    conf, re.DOTALL
)

if not old_block:
    # Try simpler match
    old_block = re.search(
        r'\s+ikev1-xauth-psk \{.*?pools = vpn-pool\n\s+\}',
        conf, re.DOTALL
    )

if not old_block:
    print("ERROR: Could not locate ikev1-xauth-psk block in config", file=sys.stderr)
    sys.exit(1)

new_blocks = """
    # IKEv1 XAuth - Main Mode (iOS 15+ uses Main Mode NOT Aggressive Mode)
    ikev1-xauth-psk {
        version = 1
        proposals = aes256-sha1-modp1024,aes128-sha1-modp1024,aes256-sha256-modp1024,aes256-sha1-modp2048,3des-sha1-modp1024
        rekey_time = 0s
        dpd_delay = 30s
        dpd_timeout = 90s
        local_addrs = %any
        aggressive = no
        encap = yes
        unique = never

        local {
            auth = psk
            id = ${SERVER_ID}
        }
        remote {
            auth = xauth
            id = %any
        }
        children {
            ikev1-xauth-psk {
                local_ts      = 0.0.0.0/0
                updown        = ${UPDOWN}
                esp_proposals = aes256-sha256,aes256-sha1,aes128-sha1,3des-sha1
                dpd_action    = clear
            }
        }
        pools = vpn-pool
    }

    # IKEv1 XAuth - Aggressive Mode (Android built-in IPSec Xauth PSK, older iOS)
    ikev1-xauth-psk-agr {
        version = 1
        proposals = aes256-sha1-modp1024,aes128-sha1-modp1024,aes256-sha256-modp1024,aes256-sha1-modp2048,3des-sha1-modp1024
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
                updown        = ${UPDOWN}
                esp_proposals = aes256-sha256,aes256-sha1,aes128-sha1,3des-sha1
                dpd_action    = clear
            }
        }
        pools = vpn-pool
    }"""

conf = conf[:old_block.start()] + new_blocks + conf[old_block.end():]
open('${CONF}', 'w').write(conf)
print("Config patched OK")
PYEOF

echo "Reloading strongSwan connections..."
swanctl --load-conns  2>&1 || true
swanctl --load-creds  2>&1 || true

echo ""
echo "✓ Done. iOS IPSec (XAuth Main Mode) should now work."
echo "  Active connections:"
swanctl --list-conns 2>/dev/null | grep -E 'ikev1|ikev2' || true
echo ""
echo "If you regenerate .mobileconfig profiles from the portal, re-download them on your iPhone."

#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
#  GhostWire — fix-strongswan.sh
#  Fixes ALL known strongSwan connection issues including:
#
#  1. "loading EAP_MSCHAPV2 method failed"
#     → EAP-MSCHAPv2 plugin not installed / disabled. Installs the package
#       and writes an explicit eap-mschapv2.conf to force load = yes.
#
#  2. "found 2 matching configs, but none allows XAuthInitPSK … Main Mode"
#     → iOS built-in "IPSec" (Cisco) type uses IKEv1 Main Mode, not Aggressive
#       Mode. The original ikev1-xauth-psk block had aggressive = yes so charon
#       rejected it. This script adds ikev1-xauth-mainmode (aggressive = no).
#
#  3. strongswan-starter conflict — switches to charon-systemd / swanctl.
#
#  Usage:  sudo bash /opt/ghostwire/fix-strongswan.sh
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
info() { echo -e "${CYAN}  →${NC} $*"; }
warn() { echo -e "${YELLOW}  ⚠${NC} $*"; }
fail() { echo -e "${RED}  ✗${NC} $*"; }

if [ "$(id -u)" -ne 0 ]; then
  fail "This script must be run as root: sudo bash $0"
  exit 1
fi

# Detect install dir from .env or use default
INSTALL_DIR="/opt/ghostwire"
if [ -f "$INSTALL_DIR/.env" ]; then
  source <(grep -E '^(INSTALL_DIR|PSK|DDNS_HOSTNAME|PUBLIC_IP|VPN_SUBNET)=' "$INSTALL_DIR/.env" 2>/dev/null || true)
fi
SWANCTL_CONF="/etc/swanctl/conf.d/ghostwire.conf"
SERVER_ID="${DDNS_HOSTNAME:-${PUBLIC_IP:-}}"

echo ""
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo -e "${CYAN}   GhostWire — StrongSwan Full Fix${NC}"
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIX 1: Install EAP-MSCHAPv2 package + force plugin to load
# Root cause: On Raspberry Pi OS / Debian Bookworm, the eap-mschapv2 plugin
# is either in a separate package that wasn't installed, or its generated
# .conf file has load = no (disabled by default in some builds).
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
info "=== FIX 1: EAP-MSCHAPv2 plugin ==="

info "Installing EAP plugin packages..."
apt-get install -y -qq \
    strongswan-plugin-eap-mschapv2 \
    strongswan-plugin-eap-dynamic \
    strongswan-plugin-eap-identity \
    libcharon-extra-plugins \
    libcharon-extauth-plugins \
    libstrongswan-extra-plugins \
  2>/dev/null && ok "EAP packages installed" || warn "apt install had warnings — continuing"

mkdir -p /etc/strongswan.d/charon

# Force eap-mschapv2 plugin to load regardless of package defaults
info "Writing /etc/strongswan.d/charon/eap-mschapv2.conf (load = yes)..."
cat > /etc/strongswan.d/charon/eap-mschapv2.conf << 'EAPMSCHAP'
eap-mschapv2 {
    load = yes
}
EAPMSCHAP
ok "eap-mschapv2.conf written"

# eap-dynamic lets charon pick MSCHAPv2 when client proposes multiple methods
info "Writing /etc/strongswan.d/charon/eap-dynamic.conf..."
cat > /etc/strongswan.d/charon/eap-dynamic.conf << 'EAPDYN'
eap-dynamic {
    load = yes
    preferred = mschapv2, md5, gtc
}
EAPDYN
ok "eap-dynamic.conf written"

info "Writing /etc/strongswan.d/charon/eap-identity.conf..."
cat > /etc/strongswan.d/charon/eap-identity.conf << 'EAPID'
eap-identity {
    load = yes
}
EAPID
ok "eap-identity.conf written"

# Ensure xauth-generic is enabled too (for IKEv1 XAuth)
cat > /etc/strongswan.d/charon/xauth-generic.conf << 'XAUTH'
xauth-generic {
    load = yes
}
XAUTH
ok "xauth-generic.conf written"

cat > /etc/strongswan.d/charon/updown.conf << 'UPDOWN'
updown {
    load = yes
}
UPDOWN
ok "updown.conf written"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIX 2: Add ikev1-xauth-mainmode block for iOS IPSec
# Root cause: iOS built-in "IPSec" profile uses IKEv1 Main Mode (ID_PROT),
# NOT Aggressive Mode. The existing ikev1-xauth-psk block has aggressive = yes
# which disqualifies it from matching Main Mode initiations.
# strongSwan log: "found 2 matching configs, but none allows XAuthInitPSK
#                  authentication using Main Mode"
# Fix: inject a new connection block (ikev1-xauth-mainmode) with aggressive = no.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
info "=== FIX 2: iOS IPSec Main Mode (XAuth) ==="

if [ ! -f "$SWANCTL_CONF" ]; then
  fail "$SWANCTL_CONF not found — run the GhostWire installer first"
  exit 1
fi

if grep -q "ikev1-xauth-mainmode" "$SWANCTL_CONF" 2>/dev/null; then
  ok "ikev1-xauth-mainmode block already present in ghostwire.conf"
else
  info "Injecting ikev1-xauth-mainmode into $SWANCTL_CONF ..."

  # We inject the new block just before the closing `}` of the connections {} section.
  # Strategy: find line number of the line that is exactly `}` right before `pools {`
  # and insert our block before it.

  POOL_LINE=$(grep -n "^pools {" "$SWANCTL_CONF" | head -1 | cut -d: -f1)
  if [ -z "$POOL_LINE" ]; then
    fail "Cannot find 'pools {' section in $SWANCTL_CONF — manual edit required"
    fail "Add this block inside the connections {} section:"
    cat << 'SHOWBLOCK'

    ikev1-xauth-mainmode {
        version = 1
        proposals = aes256-sha256-modp1024,aes256-sha1-modp1024,aes128-sha1-modp1024,aes256-sha1-modp2048,3des-sha1-modp1024
        rekey_time = 0s
        dpd_delay = 30s
        dpd_timeout = 90s
        local_addrs = %any
        aggressive = no
        encap = yes
        unique = never

        local {
            auth = psk
            id = SERVER_HOSTNAME
        }
        remote {
            auth = xauth
            id = %any
        }
        children {
            ikev1-xauth-mainmode {
                local_ts      = 0.0.0.0/0
                updown        = /opt/ghostwire/scripts/ghostwire-updown.sh
                esp_proposals = aes256-sha256,aes256-sha1,aes128-sha1,3des-sha1
                dpd_action    = clear
            }
        }
        pools = vpn-pool
    }
SHOWBLOCK
  else
    # Find the `}` line just before `pools {` — that closes connections {}
    CLOSE_CONN_LINE=$((POOL_LINE - 1))
    # Walk backwards to find the first `}` line
    while IFS= read -r line; do
      trimmed="${line#"${line%%[! ]*}"}"  # ltrim
      if [ "$trimmed" = "}" ]; then
        break
      fi
      CLOSE_CONN_LINE=$((CLOSE_CONN_LINE - 1))
    done < <(tail -n "+$((POOL_LINE - 20))" "$SWANCTL_CONF" | head -20 | tac)

    # Use a Python one-liner to do the insertion cleanly (avoids sed multiline pain)
    python3 - "$SWANCTL_CONF" "$INSTALL_DIR" "$SERVER_ID" << 'PYEOF'
import sys, re

conf_path  = sys.argv[1]
install_dir = sys.argv[2]
server_id   = sys.argv[3] if len(sys.argv) > 3 else "%any"

new_block = f"""
    # ── IKEv1 / XAuth PSK — Main Mode ────────────────────────────────────────
    # iOS built-in "IPSec" (Settings → VPN → Type: IPSec) uses IKEv1 Main Mode.
    # aggressive = no is required — iOS never sends Aggressive Mode for this profile.
    # Added by fix-strongswan.sh
    ikev1-xauth-mainmode {{
        version = 1
        proposals = aes256-sha256-modp1024,aes256-sha1-modp1024,aes128-sha1-modp1024,aes256-sha1-modp2048,3des-sha1-modp1024
        rekey_time = 0s
        dpd_delay = 30s
        dpd_timeout = 90s
        local_addrs = %any
        aggressive = no
        encap = yes
        unique = never

        local {{
            auth = psk
            id = {server_id}
        }}
        remote {{
            auth = xauth
            id = %any
        }}
        children {{
            ikev1-xauth-mainmode {{
                local_ts      = 0.0.0.0/0
                updown        = {install_dir}/scripts/ghostwire-updown.sh
                esp_proposals = aes256-sha256,aes256-sha1,aes128-sha1,3des-sha1
                dpd_action    = clear
            }}
        }}
        pools = vpn-pool
    }}
"""

content = open(conf_path).read()

# Find the `pools {` keyword and insert our block just before it,
# inside the connections {} section closing brace.
# Pattern: find `\n}` followed (eventually) by `\npools {`
# We want to insert before the `}` that comes right before `pools {`.
match = re.search(r'(\n\})\s*\n(pools \{)', content)
if match:
    pos = match.start(1)  # position of `\n}`
    content = content[:pos] + new_block + content[pos:]
    open(conf_path, 'w').write(content)
    print("  ✓ ikev1-xauth-mainmode block injected successfully")
else:
    print("  ⚠ Could not find insertion point — appending to end of connections block")
    # Fallback: append to end of file before pools
    content = content.replace('\npools {', new_block + '\npools {', 1)
    open(conf_path, 'w').write(content)
PYEOF
    ok "ikev1-xauth-mainmode injected into ghostwire.conf"
  fi
fi


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FIX 3: strongswan-starter conflict + strongswan.conf
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
info "=== FIX 3: strongswan-starter conflict ==="

systemctl disable strongswan-starter 2>/dev/null && ok "strongswan-starter disabled" \
  || warn "strongswan-starter already disabled"
systemctl stop strongswan-starter 2>/dev/null && ok "strongswan-starter stopped" \
  || warn "strongswan-starter already stopped"

[ -f /etc/ipsec.conf ] || cat > /etc/ipsec.conf << 'EOF'
# GhostWire uses swanctl (charon-systemd) — this file is intentionally empty.
EOF
ok "/etc/ipsec.conf stub present"

# Ensure strongswan.conf has aggressive-mode PSK flag
if ! grep -q "i_dont_care_about_security_and_use_aggressive_mode_psk" /etc/strongswan.conf 2>/dev/null; then
  cat > /etc/strongswan.conf << 'SWCONF'
charon {
    load_modular = yes

    # Required for IKEv1 Aggressive Mode PSK (some Android clients + third-party).
    # iOS built-in IPSec uses Main Mode — covered by ikev1-xauth-mainmode.
    i_dont_care_about_security_and_use_aggressive_mode_psk = yes

    plugins {
        include strongswan.d/charon/*.conf
    }
}
include strongswan.d/*.conf
SWCONF
  ok "strongswan.conf updated"
else
  ok "strongswan.conf already correct"
fi

# Ensure authorities block exists
if ! grep -q "^authorities {" "$SWANCTL_CONF" 2>/dev/null; then
  cat >> "$SWANCTL_CONF" << 'AUTHEOF'

authorities {
    ghostwire-ca {
        cacert = ca.crt
    }
}
AUTHEOF
  ok "authorities block added to ghostwire.conf"
else
  ok "authorities block already present"
fi


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Verify ghostwire.conf connections
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
info "=== Verifying ghostwire.conf connection blocks ==="
for conn in ikev2-eap ikev2-psk ikev2-eap-psk ikev1-xauth-psk ikev1-xauth-mainmode l2tp-psk; do
  if grep -q "^    ${conn} {" "$SWANCTL_CONF" 2>/dev/null; then
    ok "  $conn"
  else
    warn "  $conn — MISSING (re-run install.sh to regenerate)"
  fi
done

# Check for iOS-critical config
echo ""
info "iOS compatibility checks..."
ISSUES=0
grep -q "fragmentation = yes"   "$SWANCTL_CONF" && ok "  fragmentation = yes"   || { fail "  MISSING: fragmentation = yes"; ISSUES=$((ISSUES+1)); }
grep -q "encap = yes"           "$SWANCTL_CONF" && ok "  encap = yes"           || { fail "  MISSING: encap = yes";         ISSUES=$((ISSUES+1)); }
grep -q "unique = never"        "$SWANCTL_CONF" && ok "  unique = never"        || { warn "  unique = never missing";       ISSUES=$((ISSUES+1)); }
grep -q "send_cert = always"    "$SWANCTL_CONF" && ok "  send_cert = always"    || { warn "  send_cert = always missing";   ISSUES=$((ISSUES+1)); }
! grep -q "eap_id = %any"       "$SWANCTL_CONF" && ok "  No rogue eap_id line"  || { fail "  eap_id = %any found — remove it!"; ISSUES=$((ISSUES+1)); }

if [ "$ISSUES" -gt 0 ]; then
  warn "$ISSUES issue(s) found — consider re-running install.sh"
fi


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Restart strongSwan and reload config
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
info "=== Restarting strongSwan ==="

systemctl enable strongswan 2>/dev/null || true
systemctl restart strongswan
sleep 3

if systemctl is-active --quiet strongswan; then
  ok "strongswan.service is running"
else
  fail "strongswan.service failed to start!"
  systemctl status strongswan --no-pager -l | tail -30
  exit 1
fi

info "Loading swanctl connections and credentials..."
swanctl --load-all 2>/dev/null  && ok "swanctl --load-all OK"  || warn "swanctl --load-all had warnings"
swanctl --load-creds 2>/dev/null && ok "swanctl --load-creds OK" || warn "swanctl --load-creds had warnings"

echo ""
info "Loaded connections:"
swanctl --list-conns 2>/dev/null | grep -E "^[a-z]" | head -20 || warn "No connections listed"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Final summary
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ""
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo -e "${CYAN}   Fix Summary${NC}"
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo ""
for svc in strongswan xl2tpd ghostwire-backend; do
  st=$(systemctl is-active "$svc" 2>/dev/null || echo "not-installed")
  case "$st" in
    active)        ok "$svc: active" ;;
    not-installed) warn "$svc: not installed" ;;
    *)             fail "$svc: $st" ;;
  esac
done
echo ""
echo -e "  What was fixed:"
echo -e "  ${GREEN}1.${NC} EAP-MSCHAPv2 plugin force-enabled (fixes 'loading EAP_MSCHAPV2 method failed')"
echo -e "  ${GREEN}2.${NC} ikev1-xauth-mainmode added (fixes iOS IPSec Main Mode rejection)"
echo -e "  ${GREEN}3.${NC} strongswan-starter disabled, charon-systemd active"
echo ""
echo "  Test with:"
echo "    sudo journalctl -u strongswan -f   (watch logs while connecting)"
echo "    sudo swanctl --list-sas             (active sessions after connect)"
echo ""

#!/bin/bash
# =============================================================================
# GhostWire — Uninstaller
# Removes every rule, file and service that the installer created.
# Existing iptables rules that GhostWire did NOT create are left untouched.
# =============================================================================

RED=$'\033[0;31m'; YELLOW=$'\033[1;33m'; GREEN=$'\033[0;32m'
BLUE=$'\033[0;34m'; NC=$'\033[0m'

INSTALL_DIR="/opt/ghostwire"
ENV_FILE="${INSTALL_DIR}/.env"

info()  { echo -e "${BLUE}[→]${NC} $1"; }
log()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }

[ "$EUID" -eq 0 ] || { echo -e "${RED}Run as root: sudo bash uninstall.sh${NC}"; exit 1; }

echo ""
echo -e "${YELLOW}  ⚠  This will remove GhostWire and all VPN user credentials.${NC}"
echo -e "${YELLOW}  All VPN sessions will be terminated.${NC}"
echo -e "${YELLOW}  iptables rules added by GhostWire will be removed.${NC}"
echo -e "${YELLOW}  Pre-existing iptables rules will NOT be touched.${NC}"
echo ""
read -p "Type 'REMOVE' to confirm: " CONFIRM
[ "$CONFIRM" = "REMOVE" ] || { echo "Aborted."; exit 0; }
echo ""

# ── 1. Stop & disable GhostWire services ─────────────────────────────────────
info "Stopping GhostWire services..."
for svc in ghostwire-backend ghostwire-ddns ghostwire-monitor; do
  systemctl stop    "$svc" 2>/dev/null || true
  systemctl disable "$svc" 2>/dev/null || true
done
rm -f /etc/systemd/system/ghostwire-*.service
systemctl daemon-reload 2>/dev/null || true
log "GhostWire services removed"

# ── 2. Stop & disable xl2tpd (L2TP/IPSec) ───────────────────────────────────
info "Stopping xl2tpd (L2TP/IPSec)..."
systemctl stop    xl2tpd 2>/dev/null || true
systemctl disable xl2tpd 2>/dev/null || true
log "xl2tpd stopped"

# ── 3. Terminate active VPN sessions via swanctl ──────────────────────────────
info "Terminating VPN sessions..."
swanctl --terminate --ike ikev2-eap      2>/dev/null || true
swanctl --terminate --ike ikev2-psk      2>/dev/null || true
swanctl --terminate --ike ikev2-eap-psk  2>/dev/null || true
swanctl --terminate --ike ikev1-xauth-psk 2>/dev/null || true
swanctl --terminate --ike l2tp-psk       2>/dev/null || true
log "VPN sessions terminated"

# ── 4. Remove iptables rules tagged 'ghostwire' ──────────────────────────────
info "Removing GhostWire iptables rules..."

_flush_tagged() {
  local table="$1"
  local chain="$2"
  local changed=1
  while [ "$changed" -eq 1 ]; do
    changed=0
    while IFS= read -r line_num; do
      iptables -t "$table" -D "$chain" "$line_num" 2>/dev/null && changed=1 && break
    done < <(
      iptables -t "$table" --line-numbers -n -L "$chain" 2>/dev/null \
        | grep 'ghostwire' \
        | awk '{print $1}' \
        | sort -rn
    )
  done
}

_flush_tagged nat    POSTROUTING
_flush_tagged filter FORWARD
_flush_tagged filter INPUT

# Persist the cleaned ruleset
if command -v netfilter-persistent &>/dev/null; then
  netfilter-persistent save &>/dev/null || true
elif command -v iptables-save &>/dev/null; then
  mkdir -p /etc/iptables
  iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
fi
log "iptables rules removed"

# ── 5. Remove sysctl IP-forwarding config ────────────────────────────────────
info "Removing sysctl config..."
rm -f /etc/sysctl.d/99-ghostwire.conf
sysctl --system &>/dev/null || true
log "sysctl config removed"

# ── 6. Remove swanctl GhostWire config ───────────────────────────────────────
info "Removing swanctl config..."
rm -f /etc/swanctl/conf.d/ghostwire.conf
log "swanctl config removed"

# ── 7. Remove swanctl certificates and keys ──────────────────────────────────
info "Removing swanctl certificates and keys..."
rm -f /etc/swanctl/x509/server.crt
rm -f /etc/swanctl/x509ca/ghostwire-ca.crt
rm -f /etc/swanctl/private/server.key
log "Certificates and keys removed"

# ── 8. Remove strongSwan config stubs written by GhostWire ───────────────────
info "Removing strongSwan config stubs..."
# Remove /etc/ipsec.conf only if it contains our stub marker
if [ -f /etc/ipsec.conf ] && grep -q "GhostWire uses swanctl" /etc/ipsec.conf 2>/dev/null; then
  rm -f /etc/ipsec.conf
  log "/etc/ipsec.conf stub removed"
else
  warn "/etc/ipsec.conf left untouched (not a GhostWire stub)"
fi
# Remove updown plugin config
rm -f /etc/strongswan.d/charon/updown.conf
# Remove strongswan.conf only if it is exactly our generated stub
if [ -f /etc/strongswan.conf ] && grep -q "load_modular = yes" /etc/strongswan.conf 2>/dev/null; then
  rm -f /etc/strongswan.conf
  log "/etc/strongswan.conf removed"
fi

# ── 9. Remove L2TP / PPP config written by GhostWire ────────────────────────
info "Removing L2TP/IPSec config..."
rm -f /etc/xl2tpd/xl2tpd.conf
rm -f /etc/ppp/options.xl2tpd
# Remove only GhostWire-managed lines from chap-secrets
if [ -f /etc/ppp/chap-secrets ]; then
  # Delete blocks delimited by "# ghostwire-user:" markers
  python3 - << 'PYEOF'
import re, sys
try:
    with open("/etc/ppp/chap-secrets") as f:
        content = f.read()
    # Remove ghostwire-managed lines (marker comment + credential line)
    lines = content.splitlines()
    filtered = []
    skip = False
    for line in lines:
        if line.strip().startswith("# ghostwire-user:"):
            skip = True
            continue
        if skip:
            skip = False
            continue
        filtered.append(line)
    with open("/etc/ppp/chap-secrets", "w") as f:
        f.write("\n".join(filtered) + "\n")
    print("chap-secrets cleaned")
except Exception as e:
    print(f"chap-secrets cleanup warning: {e}", file=sys.stderr)
PYEOF
fi
log "L2TP/IPSec config removed"

# ── 10. Reload strongSwan so removed config takes effect ─────────────────────
info "Reloading strongSwan..."
systemctl restart strongswan 2>/dev/null \
  && swanctl --load-all 2>/dev/null || true
log "strongSwan reloaded"

# ── 11. Remove GhostWire files ───────────────────────────────────────────────
info "Removing files..."
rm -rf "$INSTALL_DIR"
rm -rf /var/log/ghostwire
log "Files removed"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  GhostWire has been fully removed.                     ${NC}"
echo -e "${GREEN}  strongSwan and xl2tpd are still installed (other      ${NC}"
echo -e "${GREEN}  services may use them). To remove:                    ${NC}"
echo -e "${GREEN}    apt remove strongswan xl2tpd ppp                   ${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo ""

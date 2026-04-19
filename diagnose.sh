#!/bin/bash
# GhostWire — Diagnostic script
# Run: sudo bash diagnose.sh

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'; NC=$'\033[0m'

ok()   { echo -e "${GREEN}  [✓]${NC} $1"; }
fail() { echo -e "${RED}  [✗]${NC} $1"; }
warn() { echo -e "${YELLOW}  [!]${NC} $1"; }
info() { echo -e "${CYAN}  [→]${NC} $1"; }

echo ""
echo "  👻 GhostWire Diagnostic Report"
echo "  ================================"
echo ""

echo -e "${CYAN}── Services ─────────────────────────────────────────${NC}"
for svc in ghostwire-backend ghostwire-monitor strongswan xl2tpd; do
  status=$(systemctl is-active "$svc" 2>/dev/null || echo "not-found")
  if [ "$status" = "active" ]; then
    ok "$svc: active"
  elif [ "$status" = "not-found" ]; then
    warn "$svc: not installed"
  else
    fail "$svc: $status"
  fi
done
# Warn if legacy stroke service is still enabled (it conflicts with swanctl)
if systemctl is-enabled strongswan-starter 2>/dev/null | grep -q "enabled"; then
  fail "strongswan-starter is ENABLED — this conflicts with swanctl/charon-systemd!"
  fail "Fix: sudo systemctl disable --now strongswan-starter"
else
  ok "strongswan-starter: disabled (correct — using swanctl)"
fi

echo ""
echo -e "${CYAN}── Network ──────────────────────────────────────────${NC}"
LOCAL_IP=$(hostname -I | awk '{print $1}')
PUBLIC_IP=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null || echo "unreachable")
PANEL_PORT=$(grep PANEL_PORT /opt/ghostwire/.env 2>/dev/null | cut -d= -f2 || echo "8080")

info "Local IP:  $LOCAL_IP"
info "Public IP: $PUBLIC_IP"

if nc -z localhost "$PANEL_PORT" 2>/dev/null; then
  ok "Panel port $PANEL_PORT: open"
else
  fail "Panel port $PANEL_PORT: not listening"
fi

for port in 500 4500; do
  if ss -uln | grep -q ":$port "; then
    ok "UDP $port: listening"
  else
    warn "UDP $port: not listening"
  fi
done

echo ""
echo -e "${CYAN}── strongSwan ───────────────────────────────────────${NC}"
if command -v swanctl &>/dev/null; then
  swanctl --version 2>/dev/null | head -1 | while read line; do info "$line"; done
  swanctl --list-sas 2>/dev/null | grep -E "ESTABLISHED|INSTALLED" | head -10 | while read line; do info "$line"; done || warn "swanctl --list-sas returned nothing (no active SAs or charon not running)"
else
  fail "swanctl command not found — is strongswan-swanctl installed?"
fi

echo ""
echo -e "${CYAN}── Database ─────────────────────────────────────────${NC}"
DB_PATH=$(grep DB_PATH /opt/ghostwire/.env 2>/dev/null | cut -d= -f2 || echo "/opt/ghostwire/data/ghostwire.db")
if [ -f "$DB_PATH" ]; then
  SIZE=$(du -sh "$DB_PATH" | cut -f1)
  ok "Database: $DB_PATH ($SIZE)"
else
  fail "Database not found: $DB_PATH"
fi

echo ""
echo -e "${CYAN}── Certificates ─────────────────────────────────────${NC}"
for cert in /opt/ghostwire/data/certs/ca.crt /opt/ghostwire/data/certs/server.crt /etc/swanctl/x509/server.crt; do
  if [ -f "$cert" ]; then
    EXPIRY=$(openssl x509 -in "$cert" -noout -enddate 2>/dev/null | cut -d= -f2 || echo "unknown")
    ok "$(basename $cert): expires $EXPIRY"
  else
    warn "$cert: not found"
  fi
done

echo ""
echo -e "${CYAN}── Recent Backend Logs ──────────────────────────────${NC}"
tail -20 /var/log/ghostwire/backend.log 2>/dev/null || warn "No backend log found"

echo ""
echo -e "${CYAN}── API Health ───────────────────────────────────────${NC}"
PING=$(curl -s --max-time 3 "http://localhost:${PANEL_PORT}/api/vpn/ping" 2>/dev/null || echo "{}")
if echo "$PING" | grep -q '"status":"ok"'; then
  ok "API: responding ($(echo $PING | grep -o '"brand":"[^"]*"' | cut -d'"' -f4))"
else
  fail "API: not responding — check 'journalctl -u ghostwire-backend -n 50'"
fi

echo ""

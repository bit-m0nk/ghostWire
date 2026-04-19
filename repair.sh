#!/bin/bash
# =============================================================================
# GhostWire — Repair / Diagnose script
# Run after a failed install when the dashboard isn't reachable:
#   sudo bash /opt/ghostwire/repair.sh
# =============================================================================
set -e

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'; BLUE=$'\033[0;34m'; NC=$'\033[0m'

log()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }
info()  { echo -e "${BLUE}[→]${NC} $1"; }
hdr()   { echo -e "\n${CYAN}══ $1 ══${NC}"; }

[ "$EUID" -eq 0 ] || { err "Run as root: sudo bash repair.sh"; exit 1; }

INSTALL_DIR="/opt/ghostwire"
ENV_FILE="$INSTALL_DIR/.env"

echo ""
echo -e "${CYAN}  👻 GhostWire — Repair & Diagnose${NC}"
echo ""

# ── Read PANEL_PORT from .env ─────────────────────────────────────────────────
PANEL_PORT=$(grep -E "^PANEL_PORT=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]') || true
PANEL_PORT=${PANEL_PORT:-8080}
info "Panel port from .env: $PANEL_PORT"

# ── 1. Check service status ───────────────────────────────────────────────────
hdr "Service Status"
systemctl status ghostwire-backend --no-pager -l 2>/dev/null || err "ghostwire-backend service not found"

# ── 2. Last 60 lines of backend log ──────────────────────────────────────────
hdr "Backend Log (last 60 lines)"
journalctl -u ghostwire-backend -n 60 --no-pager 2>/dev/null \
  || tail -60 /var/log/ghostwire/backend.log 2>/dev/null \
  || warn "No log available"

# ── 2b. Auto-fix: strawberry graphiql= → graphql_ide= (strawberry ≥0.235) ────
SCHEMA_FILE="$INSTALL_DIR/backend/app/domains/graphql/schema.py"
if grep -q 'graphiql=True' "$SCHEMA_FILE" 2>/dev/null; then
  warn "Detected deprecated 'graphiql=True' in GraphQLRouter — patching to 'graphql_ide=\"graphiql\"'..."
  sed -i 's/graphiql=True/graphql_ide="graphiql"/' "$SCHEMA_FILE"
  log "Patched $SCHEMA_FILE"
fi

# ── 3. Test uvicorn can import main.py ───────────────────────────────────────
hdr "Import Test"
info "Testing Python import of app.main..."
cd "$INSTALL_DIR/backend"
PYTHONPATH="$INSTALL_DIR/backend" \
  "$INSTALL_DIR/venv/bin/python3" -c "import app.main; print('  Import OK')" \
  && log "app.main imports cleanly" \
  || err "Import failed — see traceback above"

# ── 4. Check port availability ───────────────────────────────────────────────
hdr "Port Check"
if ss -tlnp 2>/dev/null | grep -q ":${PANEL_PORT}"; then
  warn "Something is already listening on port $PANEL_PORT:"
  ss -tlnp | grep ":${PANEL_PORT}" || true
else
  log "Port $PANEL_PORT is free — nothing blocking it"
fi

# ── 5. Check frontend dist ───────────────────────────────────────────────────
hdr "Frontend"
if [ -f "$INSTALL_DIR/frontend_dist/index.html" ]; then
  log "frontend_dist/index.html exists"
elif [ -f "$INSTALL_DIR/frontend/dist/index.html" ]; then
  warn "Frontend built in frontend/dist but not deployed to frontend_dist"
  info "Fixing by copying..."
  cp -r "$INSTALL_DIR/frontend/dist" "$INSTALL_DIR/frontend_dist"
  log "Deployed to frontend_dist"
else
  warn "No built frontend found — rebuilding..."
  bash "$INSTALL_DIR/build-frontend.sh" && log "Frontend built OK" || err "Frontend build failed"
fi

# ── 6. Reinstall Python requirements ─────────────────────────────────────────
hdr "Python Dependencies"
info "Reinstalling requirements (this fixes missing packages)..."
"$INSTALL_DIR/venv/bin/pip" install -q -r "$INSTALL_DIR/backend/requirements.txt" \
  && log "Requirements OK" \
  || err "pip install failed — check network / disk space"

# ── 7. Restart and wait ───────────────────────────────────────────────────────
hdr "Restarting Backend"
systemctl daemon-reload
systemctl restart ghostwire-backend
info "Waiting up to 20 seconds for backend to answer..."
tries=0; up=false
while [ $tries -lt 20 ]; do
  if curl -sf --max-time 1 "http://127.0.0.1:${PANEL_PORT}/api/health" &>/dev/null \
  || curl -sf --max-time 1 "http://127.0.0.1:${PANEL_PORT}/" &>/dev/null; then
    up=true; break
  fi
  sleep 1; tries=$((tries+1))
done

LOCAL_IP=$(hostname -I | awk '{print $1}')
echo ""
if $up; then
  echo -e "${GREEN}════════════════════════════════════════════${NC}"
  log "Dashboard is UP!"
  echo -e "  ${CYAN}Open:${NC}  http://${LOCAL_IP}:${PANEL_PORT}"
  echo -e "${GREEN}════════════════════════════════════════════${NC}"
else
  echo -e "${RED}════════════════════════════════════════════${NC}"
  err "Backend still not responding on port ${PANEL_PORT}"
  err "Check the import test output above for the Python error"
  echo -e "${RED}════════════════════════════════════════════${NC}"
  exit 1
fi

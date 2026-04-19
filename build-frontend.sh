#!/bin/bash
# GhostWire — Build frontend dashboard
# Usage: sudo bash /opt/ghostwire/build-frontend.sh

set -e

GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; RED=$'\033[0;31m'; NC=$'\033[0m'

log()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

INSTALL_DIR="/opt/ghostwire"

echo ""
echo "  👻 GhostWire — Building Frontend Dashboard"
echo ""

# Check Node.js
if ! command -v node &>/dev/null; then
  warn "Node.js not found — installing..."
  apt-get update -qq && apt-get install -y nodejs npm
fi

NODE_VER=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VER" -lt 18 ]; then
  warn "Node.js v${NODE_VER} is too old (need 18+). Installing NodeSource LTS..."
  curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -
  apt-get install -y nodejs
fi

log "Node.js $(node --version) / npm $(npm --version)"

cd "$INSTALL_DIR/frontend"

log "Installing npm dependencies..."
npm install --silent

log "Building production bundle..."
# Use npx to invoke vite directly — avoids exit 126 caused by missing
# execute permission on the node_modules/.bin/vite symlink on some systems.
npx --no-install vite build

log "Deploying to $INSTALL_DIR/frontend_dist ..."
rm -rf "$INSTALL_DIR/frontend_dist"
cp -r dist "$INSTALL_DIR/frontend_dist"

log "Restarting backend..."
systemctl restart ghostwire-backend 2>/dev/null || true

echo ""
log "Frontend built successfully!"
echo "  Open http://$(hostname -I | awk '{print $1}'):$(grep PANEL_PORT $INSTALL_DIR/.env 2>/dev/null | cut -d= -f2 || echo 8080)"
echo ""

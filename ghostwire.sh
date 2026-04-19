#!/bin/bash
# =============================================================================
# GhostWire — Quick Installer
# This script is fetched by:  curl -fsSL https://ghostwire.sh | sudo bash
#
# It clones the repo (or downloads a release tarball) then hands off to
# the real install.sh which does all the actual work.
# =============================================================================
set -euo pipefail

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'; NC=$'\033[0m'

REPO="https://github.com/ghostwire-vpn/ghostwire"
INSTALL_DIR="/opt/ghostwire"
BRANCH="${GW_BRANCH:-main}"

log()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info()  { echo -e "${CYAN}[→]${NC} $1"; }

cat << 'BANNER'

   ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗██╗    ██╗██╗██████╗ ███████╗
  ██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝██║    ██║██║██╔══██╗██╔════╝
  ██║  ███╗███████║██║   ██║███████╗   ██║   ██║ █╗ ██║██║██████╔╝█████╗
  ██║   ██║██╔══██║██║   ██║╚════██║   ██║   ██║███╗██║██║██╔══██╗██╔══╝
  ╚██████╔╝██║  ██║╚██████╔╝███████║   ██║   ╚███╔███╔╝██║██║  ██║███████╗
   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝    ╚══╝╚══╝ ╚═╝╚═╝  ╚═╝╚══════╝

BANNER

echo -e "${GREEN}  Self-Hosted IKEv2/IPSec VPN${NC} — github.com/ghostwire-vpn/ghostwire"
echo ""

# Root check
[ "$EUID" -eq 0 ] || error "Run as root: curl -fsSL https://ghostwire.sh | sudo bash"

# Check we're on a supported system
if ! command -v apt-get &>/dev/null; then
    error "GhostWire requires a Debian/Ubuntu-based system (apt-get not found)"
fi

# Fetch the code
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Existing install found — pulling latest code..."
    git -C "$INSTALL_DIR" pull --quiet
    log "Repository updated"
elif command -v git &>/dev/null; then
    info "Cloning GhostWire repository..."
    git clone --quiet --depth=1 --branch "$BRANCH" "$REPO" "$INSTALL_DIR"
    log "Repository cloned to $INSTALL_DIR"
else
    info "git not found — installing it first..."
    apt-get install -y git -qq
    git clone --quiet --depth=1 --branch "$BRANCH" "$REPO" "$INSTALL_DIR"
    log "Repository cloned to $INSTALL_DIR"
fi

# Hand off to the real installer
echo ""
info "Starting GhostWire installer..."
echo ""
exec bash "$INSTALL_DIR/install.sh" "$@"

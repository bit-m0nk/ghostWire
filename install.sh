#!/bin/bash
# =============================================================================
# GhostWire — Self-Hosted IKEv2/IPSec VPN + L2TP/IPSec
# One-command installer  |  sudo bash install.sh
# =============================================================================
set -e

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'; CYAN=$'\033[0;36m'; NC=$'\033[0m'

INSTALL_DIR="/opt/ghostwire"
ENV_FILE="/opt/ghostwire/.env"
GW_USER="ghostwire"

log()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info()  { echo -e "${BLUE}[→]${NC} $1"; }
ask()   { echo -e "${CYAN}[?]${NC} $1"; }

banner() {
cat << 'BANNER'

   ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗██╗    ██╗██╗██████╗ ███████╗
  ██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝██║    ██║██║██╔══██╗██╔════╝
  ██║  ███╗███████║██║   ██║███████╗   ██║   ██║ █╗ ██║██║██████╔╝█████╗
  ██║   ██║██╔══██║██║   ██║╚════██║   ██║   ██║███╗██║██║██╔══██╗██╔══╝
  ╚██████╔╝██║  ██║╚██████╔╝███████║   ██║   ╚███╔███╔╝██║██║  ██║███████╗
   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝    ╚══╝╚══╝ ╚═╝╚═╝  ╚═╝╚══════╝

BANNER
  echo -e "${GREEN}  Self-Hosted IKEv2/IPSec + L2TP/IPSec VPN — Raspberry Pi & Linux${NC}"
  echo -e "${CYAN}  Open Source  |  Zero External Dependencies  |  Private by Default${NC}"
  echo ""
}

check_root() {
  [ "$EUID" -eq 0 ] || error "Run as root: sudo bash install.sh"
}

detect_ip() {
  LOCAL_IP=$(hostname -I | awk '{print $1}')
  PUBLIC_IP=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null || \
              curl -s --max-time 5 https://ifconfig.me 2>/dev/null || \
              echo "unknown")
}

collect_config() {
  # ── Non-interactive mode (web wizard passes all values via env vars) ─────────
  if [[ "${GW_NONINTERACTIVE:-}" == "1" ]]; then
    VPN_BRAND="${GW_BRAND:-GhostWire}"
    ADMIN_USER="${GW_ADMIN_USER:-admin}"
    ADMIN_PASS="${GW_ADMIN_PASS:-}"
    PANEL_PORT="${GW_PANEL_PORT:-8080}"
    VPN_SUBNET="${GW_VPN_SUBNET:-10.10.0.0/24}"
    PUBLIC_IP="${GW_PUBLIC_IP:-$PUBLIC_IP}"
    LOCAL_IP="${GW_LOCAL_IP:-$LOCAL_IP}"
    USE_DDNS="${GW_USE_DDNS:-false}"
    DDNS_PRIMARY="${GW_DDNS_PRIMARY:-}"
    DDNS_HOSTNAME="${GW_DDNS_HOSTNAME:-$PUBLIC_IP}"
    DYNU_HOSTNAME="${GW_DDNS_HOSTNAME:-}"
    DYNU_USERNAME="${GW_DYNU_USERNAME:-}"
    DYNU_IP_UPDATE_PASS="${GW_DYNU_PASS:-}"
    NOIP_HOSTNAME="${GW_NOIP_HOSTNAME:-}"
    NOIP_USERNAME="${GW_NOIP_USERNAME:-}"
    NOIP_PASSWORD="${GW_NOIP_PASS:-}"
    PSK=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
    [ ${#ADMIN_PASS} -ge 12 ] || error "Admin password must be at least 12 characters (GW_ADMIN_PASS)"
    log "Non-interactive mode — using provided configuration"
    return
  fi

  echo ""
  echo -e "${CYAN}════════════════════════════════════════════${NC}"
  echo -e "${CYAN}           CONFIGURATION SETUP              ${NC}"
  echo -e "${CYAN}════════════════════════════════════════════${NC}"
  echo ""

  ask "Brand / VPN name shown to users [default: GhostWire]:"
  read -r VPN_BRAND; VPN_BRAND=${VPN_BRAND:-GhostWire}

  ask "Admin username [default: admin]:"
  read -r ADMIN_USER; ADMIN_USER=${ADMIN_USER:-admin}

  ask "Admin password (min 12 chars):"
  read -rs ADMIN_PASS; echo ""
  [ ${#ADMIN_PASS} -ge 12 ] || error "Password must be at least 12 characters"

  # DDNS
  echo ""
  echo -e "  ${CYAN}DDNS Setup${NC}"
  echo "  ──────────"
  ask "Enable DDNS? (recommended for dynamic IPs) [Y/n]:"
  read -r USE_DDNS_INPUT

  DDNS_PRIMARY=""
  DYNU_HOSTNAME=""; DYNU_USERNAME=""; DYNU_IP_UPDATE_PASS=""
  NOIP_HOSTNAME=""; NOIP_USERNAME=""; NOIP_PASSWORD=""

  if [[ "$USE_DDNS_INPUT" =~ ^[Nn]$ ]]; then
    USE_DDNS="false"
    DDNS_HOSTNAME="$PUBLIC_IP"
    warn "No-DDNS mode: you will receive alerts when your IP changes."
  else
    USE_DDNS="true"
    echo ""
    echo "  Supported providers: (1) Dynu  (2) No-IP"
    ask "Choose provider [1/2]:"
    read -r DDNS_CHOICE

    if [[ "$DDNS_CHOICE" == "2" ]]; then
      DDNS_PRIMARY="noip"
      ask "No-IP hostname (e.g. myvpn.ddns.net):"
      read -r NOIP_HOSTNAME
      ask "No-IP username:"
      read -r NOIP_USERNAME
      ask "No-IP password:"
      read -rs NOIP_PASSWORD; echo ""
      DDNS_HOSTNAME="$NOIP_HOSTNAME"
    else
      DDNS_PRIMARY="dynu"
      ask "Dynu hostname (e.g. myvpn.dynu.net):"
      read -r DYNU_HOSTNAME
      ask "Dynu username:"
      read -r DYNU_USERNAME
      ask "Dynu IP Update Password (from dynu.com/ControlPanel/APICredentials):"
      read -rs DYNU_IP_UPDATE_PASS; echo ""
      DDNS_HOSTNAME="$DYNU_HOSTNAME"
    fi
  fi

  # Panel port
  echo ""
  ask "Admin panel port [default: 8080]:"
  read -r PANEL_PORT; PANEL_PORT=${PANEL_PORT:-8080}

  # VPN subnet
  ask "VPN subnet [default: 10.10.0.0/24]:"
  read -r VPN_SUBNET; VPN_SUBNET=${VPN_SUBNET:-10.10.0.0/24}

  # PSK
  PSK=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
  info "Generated PSK for L2TP/IPSec and IKEv2-PSK: $PSK"

  echo ""
  log "Configuration collected"
}

install_dependencies() {
  info "Installing system dependencies..."
  apt-get update -qq
  apt-get install -y \
    strongswan strongswan-pki libcharon-extra-plugins \
    libcharon-extauth-plugins libstrongswan-extra-plugins \
    xl2tpd ppp \
    python3 python3-pip python3-venv \
    openssl curl fail2ban \
    iptables-persistent \
    dnsmasq \
    2>/dev/null

  # Node.js for frontend
  if ! command -v node &>/dev/null || [ "$(node --version | cut -dv -f2 | cut -d. -f1)" -lt 18 ]; then
    info "Installing Node.js LTS..."
    curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - 2>/dev/null
    apt-get install -y nodejs 2>/dev/null
  fi

  log "Dependencies installed"
}

setup_directories() {
  info "Creating directory structure..."
  mkdir -p "$INSTALL_DIR"/{data/certs,logs}
  mkdir -p /var/log/ghostwire
  chmod 750 "$INSTALL_DIR/data"
  log "Directories created"
}

copy_files() {
  info "Copying GhostWire files..."
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/" 2>/dev/null || true
  chmod +x "$INSTALL_DIR/build-frontend.sh" 2>/dev/null || true
  chmod +x "$INSTALL_DIR/scripts"/*.sh 2>/dev/null || true
  log "Files copied to $INSTALL_DIR"
}

write_env() {
  info "Writing .env configuration..."
  cat > "$ENV_FILE" << EOF
# GhostWire Configuration
# Generated by installer on $(date)

VPN_BRAND=${VPN_BRAND}
INSTALL_DIR=${INSTALL_DIR}
PANEL_PORT=${PANEL_PORT}

# Database (SQLite default — set DB_URL for Postgres)
DB_PATH=${INSTALL_DIR}/data/ghostwire.db

# VPN / Network
LOCAL_IP=${LOCAL_IP}
PUBLIC_IP=${PUBLIC_IP}
VPN_SUBNET=${VPN_SUBNET}
PSK=${PSK}

# DDNS
USE_DDNS=${USE_DDNS}
DDNS_PRIMARY=${DDNS_PRIMARY}
DDNS_HOSTNAME=${DDNS_HOSTNAME}
DYNU_HOSTNAME=${DYNU_HOSTNAME}
DYNU_USERNAME=${DYNU_USERNAME}
DYNU_IP_UPDATE_PASS=${DYNU_IP_UPDATE_PASS}
NOIP_HOSTNAME=${NOIP_HOSTNAME}
NOIP_USERNAME=${NOIP_USERNAME}
NOIP_PASSWORD=${NOIP_PASSWORD}

# Notifications (configure via dashboard)
TG_BOT_TOKEN=
TG_CHAT_ID=
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
NOTIFY_EMAIL=

# Security
JWT_SECRET=$(openssl rand -hex 32)
JWT_EXPIRE_HOURS=24
EOF
  chmod 600 "$ENV_FILE"
  log ".env written"
}

setup_python() {
  info "Setting up Python virtual environment..."
  python3 -m venv "$INSTALL_DIR/venv"
  "$INSTALL_DIR/venv/bin/pip" install --upgrade pip --quiet
  "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/backend/requirements.txt" --quiet
  log "Python environment ready"
}

generate_certs() {
  info "Generating CA and server certificates..."
  "$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/backend/scripts/generate_ca.py" \
    --brand "$VPN_BRAND" \
    --hostname "$DDNS_HOSTNAME" \
    --public-ip "$PUBLIC_IP" \
    --output-dir "$INSTALL_DIR/data/certs" \
    --certs-dir /etc/swanctl
  log "Certificates generated"
}

init_database() {
  info "Initialising database..."
  PYTHONPATH="$INSTALL_DIR/backend" \
    "$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/backend/scripts/init_db.py" \
      --env-file "$ENV_FILE" \
      --admin-user "$ADMIN_USER" \
      --admin-pass "$ADMIN_PASS"
  log "Database initialised"
}

configure_strongswan() {
  info "Configuring strongSwan (swanctl/vici)..."

  # Determine server identity (prefer DDNS hostname, fall back to raw IP)
  SERVER_ID="$DDNS_HOSTNAME"
  [ -z "$SERVER_ID" ] && SERVER_ID="$PUBLIC_IP"

  # Derive VPN gateway IP and client pool from VPN_SUBNET
  # e.g. 10.10.0.0/24 → gateway=10.10.0.1, pool=10.10.0.2-10.10.0.254
  # 10.10.0.1 is RESERVED for the gateway — clients start at .2
  VPN_GW=$(echo "$VPN_SUBNET" | cut -d/ -f1 | sed 's/\.[0-9]*$/.1/')
  VPN_POOL_START=$(echo "$VPN_SUBNET" | cut -d/ -f1 | sed 's/\.[0-9]*$/.2/')
  VPN_POOL_END=$(echo "$VPN_SUBNET" | cut -d/ -f1 | sed 's/\.[0-9]*$/.254/')

  # ── Ensure we use charon-systemd (swanctl) — NOT the legacy stroke/ipsec starter ──
  systemctl disable strongswan-starter 2>/dev/null || true
  systemctl stop    strongswan-starter 2>/dev/null || true

  # Create a stub /etc/ipsec.conf so ipsec_starter (if ever invoked manually)
  # does not crash with "no files found matching /etc/ipsec.conf".
  cat > /etc/ipsec.conf << 'IPSECSTUB'
# GhostWire uses swanctl (charon-systemd) — this file is intentionally empty.
# Do not add connections here; use /etc/swanctl/conf.d/ghostwire.conf instead.
IPSECSTUB

  # Enable the modern charon-systemd service (unit name: strongswan)
  systemctl enable strongswan 2>/dev/null || true

  # strongswan.conf — charon plugin loader config
  # Must include updown plugin (in libcharon-extra-plugins) for connect/disconnect hooks
  mkdir -p /etc/strongswan.d/charon
  cat > /etc/strongswan.conf << 'SWCONF'
charon {
    load_modular = yes

    # Required for IKEv1 Aggressive Mode PSK (iOS "IPSec / Cisco" type).
    # Without this flag, charon refuses Aggressive Mode initiations and iOS
    # shows "The VPN server did not respond" immediately.
    # Risk: the PSK hash is exposed in the clear during handshake and can be
    # offline-brute-forced. Mitigate with a long random PSK (GhostWire default
    # is 32 random chars).
    i_dont_care_about_security_and_use_aggressive_mode_psk = yes

    plugins {
        include strongswan.d/charon/*.conf
    }
}
include strongswan.d/*.conf
SWCONF

  # Ensure updown plugin config exists
  cat > /etc/strongswan.d/charon/updown.conf << 'UPDOWN'
updown {
    load = yes
}
UPDOWN

  # Enable xauth-generic plugin — required for IKEv1 XAuth (iOS IPSec + Android XAuth PSK)
  cat > /etc/strongswan.d/charon/xauth-generic.conf << 'XAUTH'
xauth-generic {
    load = yes
}
XAUTH

  # Create swanctl directory layout
  mkdir -p /etc/swanctl/conf.d /etc/swanctl/x509 /etc/swanctl/x509ca /etc/swanctl/private

  # Write swanctl connection config with all auth methods for full device coverage
  cat > /etc/swanctl/conf.d/ghostwire.conf << EOF
connections {

    # ── IKEv2 / EAP-MSCHAPv2 + cert server auth ──────────────────────────────
    # iOS built-in IKEv2 (Settings → VPN → IKEv2), Android strongSwan app,
    # Linux NetworkManager, Windows built-in IKEv2.
    #
    # iOS-specific requirements (must ALL be present):
    #   fragmentation = yes   — iOS sends large IKE_AUTH packets with the cert
    #                           chain; without fragmentation the packet is silently
    #                           dropped and iOS shows "The VPN server did not respond"
    #   encap = yes           — iOS is almost always behind NAT; forces UDP
    #                           encapsulation (port 4500) even when NAT is not
    #                           detected (equivalent to forceencaps in ipsec.conf)
    #   unique = never        — iOS reconnects with the same IKE identity; without
    #                           this, charon tears down the old SA on the second
    #                           connect attempt and iOS sees a mid-handshake drop
    #   reauth_time = 0s      — disable periodic re-authentication; iOS does not
    #                           handle mid-session EAP re-auth gracefully
    #   proposals with ecp256 — iOS 16+ initiates with aes256-sha256-prfsha256-ecp256
    #                           as its FIRST choice; modp2048 is listed as fallback
    #   send_cert = always    — iOS does not send CERTREQ, so we must always push
    #                           the server certificate unprompted
    ikev2-eap {
        version = 2
        proposals = aes256-sha256-ecp256,aes256-sha256-modp2048,aes128-sha256-ecp256,aes128-sha256-modp2048,aes256-sha1-modp2048
        rekey_time = 0s
        reauth_time = 0s
        dpd_delay = 30s
        dpd_timeout = 90s
        send_cert = always
        fragmentation = yes
        encap = yes
        unique = never
        local_addrs = %any

        local {
            auth = pubkey
            certs = server.crt
            id = ${SERVER_ID}
        }
        remote {
            auth = eap-mschapv2
            # eap_id intentionally omitted: setting eap_id triggers an EAP-Identity
            # request round-trip that iOS/macOS do NOT support. iOS sends its EAP
            # identity directly inside EAP-MSCHAPv2 — no separate Identity exchange.
            # Omitting this skips the unsupported phase and fixes the EAP/FAIL error.
        }
        children {
            ikev2-eap {
                local_ts      = 0.0.0.0/0
                updown        = ${INSTALL_DIR}/scripts/ghostwire-updown.sh
                # Non-PFS proposals first (iOS needs to match without PFS KE), PFS variants follow
                esp_proposals = aes256gcm16,aes256-sha256,aes128-sha256,aes256gcm16-ecp256,aes256-sha256-ecp256
                dpd_action    = clear
            }
        }
        pools = vpn-pool
    }

    # ── IKEv2 / PSK ─────────────────────────────────────────────────────────
    # Android built-in "IKEv2/IPSec PSK", iOS built-in IKEv2 PSK mobileconfig
    ikev2-psk {
        version = 2
        proposals = aes256-sha256-ecp256,aes256-sha256-modp2048,aes128-sha256-modp2048,aes256-sha1-modp2048
        rekey_time = 0s
        reauth_time = 0s
        dpd_delay = 30s
        dpd_timeout = 90s
        fragmentation = yes
        encap = yes
        unique = never
        local_addrs = %any

        local {
            auth = psk
            id = ${SERVER_ID}
        }
        remote {
            auth = psk
            id = %any
        }
        children {
            ikev2-psk {
                local_ts      = 0.0.0.0/0
                updown        = ${INSTALL_DIR}/scripts/ghostwire-updown.sh
                esp_proposals = aes256gcm16,aes256-sha256,aes128-sha256,aes256-sha1
                dpd_action    = clear
            }
        }
        pools = vpn-pool
    }

    # ── IKEv2 / EAP-MSCHAPv2 + PSK server auth ───────────────────────────────
    # Android built-in "IKEv2/IPSec MSCHAPv2" (server auth = PSK, not cert)
    ikev2-eap-psk {
        version = 2
        proposals = aes256-sha256-ecp256,aes256-sha256-modp2048,aes128-sha256-modp2048
        rekey_time = 0s
        reauth_time = 0s
        dpd_delay = 30s
        dpd_timeout = 90s
        fragmentation = yes
        encap = yes
        unique = never
        local_addrs = %any

        local {
            auth = psk
            id = ${SERVER_ID}
        }
        remote {
            auth = eap-mschapv2
            # eap_id omitted — same reason as ikev2-eap above (iOS compatibility)
        }
        children {
            ikev2-eap-psk {
                local_ts      = 0.0.0.0/0
                updown        = ${INSTALL_DIR}/scripts/ghostwire-updown.sh
                esp_proposals = aes256gcm16,aes256-sha256,aes128-sha256
                dpd_action    = clear
            }
        }
        pools = vpn-pool
    }

    # ── IKEv1 / XAuth PSK ────────────────────────────────────────────────────
    # iOS "IPSec" type (Settings → VPN → Type: IPSec) — Cisco-compatible XAuth PSK
    # Android built-in "IPSec Xauth PSK" (legacy IKEv1)
    #
    # iOS 15+ sends IKEv1 Main Mode (aggressive = no). Older iOS and Android
    # use Aggressive Mode. We maintain two separate connection blocks to handle
    # both. The Main Mode block (ikev1-xauth-psk) is matched first by charon.
    #
    # NOTE: swanctl does NOT support having two separate "local" or "remote"
    # sections in the same connection block (unlike ipsec.conf).
    # XAuth is enabled globally via strongswan.conf:
    #   charon { plugins { xauth-generic { } } }
    # and is triggered automatically for IKEv1 when auth = xauth is set in
    # a single local/remote section (one auth round-trip: PSK phase1 + XAuth phase2).
    # The correct swanctl pattern is auth = xauth in the remote block — charon
    # handles the two-phase sequence internally.
    # IKEv1 XAuth - Main Mode (iOS 15+ uses Main Mode, NOT Aggressive Mode)
    #
    # IMPORTANT: local.id must be %any (not the server hostname/IP).
    # iOS sends its own internal VPN gateway address as the remote-ID during
    # Main Mode phase-1. charon selects a connection by matching both local AND
    # remote IDs; if local.id is set to the DDNS hostname, charon cannot match
    # because the IKE packets arrive on the LAN IP (192.168.x.x), not on the
    # public hostname. Setting %any tells charon to accept any local identity
    # for this connection, which is the correct behaviour for a road-warrior PSK
    # server — the PSK shared-secret (in the secrets block) is the actual
    # authentication credential, not the IKE identity.
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
            id = %any
        }
        remote {
            auth = xauth
            id = %any
        }
        children {
            ikev1-xauth-psk {
                local_ts      = 0.0.0.0/0
                updown        = ${INSTALL_DIR}/scripts/ghostwire-updown.sh
                esp_proposals = aes256-sha256,aes256-sha1,aes128-sha1,3des-sha1
                dpd_action    = clear
            }
        }
        pools = vpn-pool
    }

    # IKEv1 XAuth - Aggressive Mode (Android built-in IPSec Xauth PSK, older clients)
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
                updown        = ${INSTALL_DIR}/scripts/ghostwire-updown.sh
                esp_proposals = aes256-sha256,aes256-sha1,aes128-sha1,3des-sha1
                dpd_action    = clear
            }
        }
        pools = vpn-pool
    }

    # ── L2TP/IPSec transport mode ─────────────────────────────────────────────
    # Android built-in "L2TP/IPSec PSK" — IKEv1 transport mode, PPP inside
    l2tp-psk {
        version = 1
        proposals = aes256-sha256-modp2048,aes256-sha1-modp2048,aes128-sha1-modp2048,3des-sha1-modp1024
        rekey_time = 0s
        dpd_delay = 30s
        dpd_timeout = 90s
        local_addrs = %any
        aggressive = no

        local {
            auth = psk
            id = ${SERVER_ID}
        }
        remote {
            auth = psk
            id = %any
        }
        children {
            l2tp-psk {
                # Transport mode — not tunnel (L2TP wraps PPP itself)
                mode      = transport
                local_ts  = dynamic[udp/l2tp]
                remote_ts = dynamic[udp/l2tp]
                updown    = ${INSTALL_DIR}/scripts/ghostwire-updown.sh
                esp_proposals = aes256-sha256,aes256-sha1,aes128-sha1,3des-sha1
                dpd_action    = clear
            }
        }
    }
}

pools {
    vpn-pool {
        # .1 is reserved for the ghostwire0 gateway — clients start at .2
        addrs = ${VPN_POOL_START}-${VPN_POOL_END}
        # Point clients at our dnsmasq instance (DNS ad-blocking) first,
        # with Cloudflare as fallback (dnsmasq forwards there anyway)
        dns   = ${VPN_GW}, 1.1.1.1
    }
}

secrets {
    private {
        file = server.key
    }
    ike-psk {
        # id = %any ensures this PSK is offered for any IKE identity, which is
        # required for XAuth Main Mode. Without an explicit id charon may refuse
        # to match the secret when the initiator identity differs from SERVER_ID.
        id = %any
        secret = "${PSK}"
    }
}
authorities {
    # ghostwire-ca tells charon which CA cert to trust for IKEv2 server cert verification.
    # Without this block iOS gets an unverifiable cert chain and drops the connection silently.
    ghostwire-ca {
        cacert = ca.crt
    }
}
EOF

  log "strongSwan configured"
}

configure_l2tp() {
  info "Configuring xl2tpd (L2TP/IPSec PSK)..."

  # Derive PPP IP pool from VPN subnet:
  # VPN_SUBNET = 10.10.0.0/24 → l2tp_local=10.10.0.1 (gateway), l2tp_pool=10.10.0.200-10.10.0.250
  # Note: .1 is the gateway IP (on ghostwire0) — xl2tpd uses it as the PPP local end
  L2TP_LOCAL=$(echo "$VPN_SUBNET" | cut -d/ -f1 | sed 's/\.[0-9]*$/.1/')
  L2TP_POOL=$(echo "$VPN_SUBNET" | cut -d/ -f1 | sed 's/\.[0-9]*$/.200/')-$(echo "$VPN_SUBNET" | cut -d/ -f1 | sed 's/\.[0-9]*$/.250/')

  mkdir -p /etc/xl2tpd

  cat > /etc/xl2tpd/xl2tpd.conf << EOF
[global]
ipsec saref = yes
listen-addr = ${LOCAL_IP}

[lns default]
ip range = ${L2TP_POOL}
local ip = ${L2TP_LOCAL}
require chap = yes
refuse pap = yes
require authentication = yes
name = ${VPN_BRAND}
ppp debug = no
pppoptfile = /etc/ppp/options.xl2tpd
length bit = yes
EOF

  cat > /etc/ppp/options.xl2tpd << 'PPPOPT'
ipcp-accept-local
ipcp-accept-remote
ms-dns 1.1.1.1
ms-dns 8.8.8.8
noccp
noauth
logfile /var/log/ghostwire/l2tp-ppp.log
idle 1800
mtu 1280
mru 1280
nodefaultroute
debug
lock
proxyarp
connect-delay 5000
PPPOPT

  # Ensure chap-secrets exists
  [ -f /etc/ppp/chap-secrets ] || cat > /etc/ppp/chap-secrets << 'CHAP'
# chap-secrets - secrets for authenticating VPN users
# Format: username  service  password  ip-addresses
# GhostWire manages entries below this line automatically
CHAP

  # Enable xl2tpd
  systemctl enable xl2tpd 2>/dev/null || true

  log "xl2tpd configured (L2TP local: $L2TP_LOCAL, pool: $L2TP_POOL)"
}

setup_vpn_interface() {
  info "Creating dedicated VPN gateway interface (ghostwire0)..."

  # ghostwire0 is a dummy interface that permanently holds the VPN gateway IP
  # (10.10.0.1 by default). This gives:
  #   • dnsmasq a stable interface to bind to at boot (fixes "Cannot assign
  #     requested address" because the IP now exists before dnsmasq starts)
  #   • strongSwan/xl2tpd clean routing — VPN traffic stays on a separate
  #     interface, separate from the LAN/WAN iface
  #   • iptables rules a reliable interface name to match on
  VPN_GW=$(echo "$VPN_SUBNET" | cut -d/ -f1 | sed 's/\.[0-9]*$/.1/')

  # Bring it up immediately for this boot
  if ! ip link show ghostwire0 &>/dev/null 2>&1; then
    ip link add ghostwire0 type dummy 2>/dev/null || true
  fi
  ip addr flush dev ghostwire0 2>/dev/null || true
  ip addr add "${VPN_GW}/24" dev ghostwire0 2>/dev/null || true
  ip link set ghostwire0 up 2>/dev/null || true

  # Persist across reboots via systemd-networkd
  mkdir -p /etc/systemd/network

  cat > /etc/systemd/network/50-ghostwire0.netdev << EOF
[NetDev]
Name=ghostwire0
Kind=dummy
EOF

  cat > /etc/systemd/network/50-ghostwire0.network << EOF
[Match]
Name=ghostwire0

[Network]
# GhostWire VPN gateway — clients use this as their default gateway
Address=${VPN_GW}/24
EOF

  # Load dummy kernel module so the interface survives a reboot
  modprobe dummy 2>/dev/null || true
  grep -qx "dummy" /etc/modules 2>/dev/null || echo "dummy" >> /etc/modules

  # Enable systemd-networkd if not already enabled (needed to apply .netdev/.network)
  systemctl enable systemd-networkd 2>/dev/null || true
  systemctl start  systemd-networkd 2>/dev/null || true

  # Also write a /etc/network/interfaces.d snippet for systems using ifupdown
  if [ -d /etc/network/interfaces.d ]; then
    cat > /etc/network/interfaces.d/ghostwire0 << EOF
auto ghostwire0
iface ghostwire0 inet static
    address ${VPN_GW}
    netmask 255.255.255.0
    pre-up ip link add ghostwire0 type dummy 2>/dev/null || true
    up     ip link set ghostwire0 up
EOF
  fi

  # Store VPN_GW in .env so other components (dnsmasq, firewall) can read it
  grep -q "^VPN_GW=" "$ENV_FILE" 2>/dev/null \
    && sed -i "s|^VPN_GW=.*|VPN_GW=${VPN_GW}|" "$ENV_FILE" \
    || echo "VPN_GW=${VPN_GW}" >> "$ENV_FILE"

  log "ghostwire0 created — gateway IP: ${VPN_GW}/24"
}

configure_firewall() {
  info "Configuring firewall (iptables)..."
  WAN_IFACE=$(ip route | grep default | awk '{print $5}' | head -1)
  [ -z "$WAN_IFACE" ] && WAN_IFACE="eth0"

  # Store resolved interface in .env so uninstaller can use it later
  grep -q "^WAN_IFACE=" "$ENV_FILE" 2>/dev/null \
    && sed -i "s|^WAN_IFACE=.*|WAN_IFACE=${WAN_IFACE}|" "$ENV_FILE" \
    || echo "WAN_IFACE=${WAN_IFACE}" >> "$ENV_FILE"
  grep -q "^GW_PANEL_PORT_RULE=" "$ENV_FILE" 2>/dev/null \
    || echo "GW_PANEL_PORT_RULE=${PANEL_PORT}" >> "$ENV_FILE"

  set +e

  _ipt_add() {
    local table="filter"
    if [ "$1" = "-t" ]; then table="$2"; shift 2; fi
    local chain="$1"; shift
    if ! iptables -t "$table" -C "$chain" "$@" 2>/dev/null; then
      iptables -t "$table" -A "$chain" "$@"
    fi
    return 0
  }

  local TAG="ghostwire"

  # NAT masquerade for VPN clients — two rules:
  #   1. Subnet-based: catches IKEv2 tunnel traffic (virtual IPs from the pool)
  #   2. Interface-based: catches any traffic arriving on ghostwire0 (belt+suspenders)
  _ipt_add -t nat POSTROUTING \
    -s "$VPN_SUBNET" -o "$WAN_IFACE" -j MASQUERADE \
    -m comment --comment "${TAG}"
  _ipt_add -t nat POSTROUTING \
    -i ghostwire0 -o "$WAN_IFACE" -j MASQUERADE \
    -m comment --comment "${TAG}-gw"

  # Forward: VPN subnet → internet
  _ipt_add FORWARD \
    -s "$VPN_SUBNET" -j ACCEPT \
    -m comment --comment "${TAG}"
  # Forward: ghostwire0 → WAN (internet access for VPN clients)
  _ipt_add FORWARD \
    -i ghostwire0 -o "$WAN_IFACE" -j ACCEPT \
    -m comment --comment "${TAG}-gw-out"
  # Forward: WAN → ghostwire0 (return traffic for established connections)
  _ipt_add FORWARD \
    -i "$WAN_IFACE" -o ghostwire0 -m state --state RELATED,ESTABLISHED -j ACCEPT \
    -m comment --comment "${TAG}-gw-in"

  # Forward: return traffic for established/related connections (general)
  _ipt_add FORWARD \
    -m state --state RELATED,ESTABLISHED -j ACCEPT \
    -m comment --comment "${TAG}"

  # IKEv2/IPSec ports
  _ipt_add INPUT -p udp --dport 500  -j ACCEPT -m comment --comment "${TAG}"
  _ipt_add INPUT -p udp --dport 4500 -j ACCEPT -m comment --comment "${TAG}"

  # L2TP port
  _ipt_add INPUT -p udp --dport 1701 -j ACCEPT -m comment --comment "${TAG}"

  # Admin panel port
  _ipt_add INPUT -p tcp --dport "$PANEL_PORT" -j ACCEPT \
    -m comment --comment "${TAG}"

  # IP forwarding
  echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-ghostwire.conf
  sysctl -p /etc/sysctl.d/99-ghostwire.conf &>/dev/null

  # Persist rules
  if command -v netfilter-persistent &>/dev/null; then
    netfilter-persistent save &>/dev/null || true
  elif command -v iptables-save &>/dev/null; then
    mkdir -p /etc/iptables
    iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
  fi

  set -e

  log "Firewall configured (WAN: $WAN_IFACE)"
}

setup_dnsmasq() {
  info "Configuring dnsmasq for DNS ad-blocking..."

  # Derive VPN gateway IP (same logic as configure_strongswan / setup_vpn_interface)
  VPN_GW=$(echo "$VPN_SUBNET" | cut -d/ -f1 | sed 's/\.[0-9]*$/.1/')

  # Create required directories
  mkdir -p /var/log/dnsmasq
  mkdir -p /etc/dnsmasq.d/ghostwire
  mkdir -p /opt/ghostwire/blocklists
  chmod 755 /var/log/dnsmasq

  # Write the main dnsmasq config.
  # Key settings:
  #   log-queries        — log every DNS query so GhostWire can parse block/allow events
  #   log-facility       — write query log to a dedicated file (not syslog)
  #   conf-dir           — include per-user override snippets written by the backend
  #   no-resolv          — don't read /etc/resolv.conf; use the explicit server= lines
  #   server             — upstream resolvers (Cloudflare + Google, change if preferred)
  #   bind-dynamic       — IMPORTANT: unlike bind-interfaces, bind-dynamic retries
  #                        binding when an interface/address appears AFTER dnsmasq
  #                        starts. This is required because ghostwire0 (10.10.0.1)
  #                        may come up after dnsmasq during boot. With bind-interfaces
  #                        dnsmasq fails immediately with "Cannot assign requested
  #                        address". bind-dynamic is available in dnsmasq ≥2.62
  #                        (all Debian/Ubuntu/Raspbian releases since 2014).
  #   listen-address     — VPN pool gateway IP where clients send DNS queries
  #   bogus-priv         — never forward PTR queries for private IP ranges
  #   domain-needed      — never forward bare (no-dot) names upstream
  cat > /etc/dnsmasq.conf << DNSMASQ_EOF
# GhostWire dnsmasq configuration
# Managed by GhostWire installer — manual edits will survive reinstalls
# but will be overwritten by repair.sh

# ── Logging (required for DNS analytics) ────────────────────────────────────
log-queries
log-facility=/var/log/dnsmasq/query.log

# ── Upstream DNS resolvers ───────────────────────────────────────────────────
no-resolv
server=1.1.1.1
server=1.0.0.1
server=8.8.8.8

# ── Interface binding ────────────────────────────────────────────────────────
# bind-dynamic (NOT bind-interfaces): retries binding when ghostwire0 appears
# after dnsmasq starts. bind-interfaces would fail with "Cannot assign requested
# address" at boot because ghostwire0 may not exist yet.
bind-dynamic
listen-address=127.0.0.1
listen-address=${VPN_GW}

# ── Security ─────────────────────────────────────────────────────────────────
bogus-priv
domain-needed
# Stop dnsmasq from reading /etc/hosts for ad purposes
no-hosts

# ── GhostWire blocklist and per-user overrides ───────────────────────────────
# The backend writes merged blocklist + per-user overrides here:
conf-dir=/opt/ghostwire/blocklists,*.conf
conf-dir=/etc/dnsmasq.d/ghostwire,*.conf
DNSMASQ_EOF

  # Ensure log rotation for the query log
  cat > /etc/logrotate.d/dnsmasq-ghostwire << 'LOGROTATE_EOF'
/var/log/dnsmasq/query.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        pkill -HUP dnsmasq 2>/dev/null || true
    endscript
}
LOGROTATE_EOF

  # Enable and start dnsmasq
  systemctl enable dnsmasq 2>/dev/null || true
  systemctl restart dnsmasq 2>/dev/null || warn "dnsmasq start failed — DNS blocking will not be active"

  # Verify it's running
  if systemctl is-active --quiet dnsmasq; then
    log "dnsmasq configured and running (DNS ad-blocking ready)"
  else
    warn "dnsmasq is not running — check: sudo systemctl status dnsmasq"
    warn "DNS blocking will show 'No data' until dnsmasq is running"
  fi
}

install_systemd_services() {
  info "Installing systemd services..."

  for svc in ghostwire-backend ghostwire-ddns ghostwire-monitor; do
    if [ -f "$INSTALL_DIR/systemd/${svc}.service" ]; then
      sed "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
        "$INSTALL_DIR/systemd/${svc}.service" \
        > "/etc/systemd/system/${svc}.service"
    fi
  done

  systemctl daemon-reload
  systemctl enable ghostwire-backend
  [ "$USE_DDNS" = "true" ] && systemctl enable ghostwire-ddns || true
  systemctl enable ghostwire-monitor

  log "Systemd services installed"
}

build_frontend() {
  info "Building frontend dashboard..."
  local build_log
  build_log=$( bash "$INSTALL_DIR/build-frontend.sh" 2>&1 ) && BUILD_OK=true || BUILD_OK=false
  echo "$build_log" | tail -10
  if $BUILD_OK; then
    log "Frontend built"
  else
    warn "Frontend build had errors — backend and VPN are still functional."
    warn "Re-run manually: sudo bash $INSTALL_DIR/build-frontend.sh"
  fi
}

start_services() {
  info "Starting services..."
  # Use strongswan (charon-systemd / swanctl) — NEVER strongswan-starter (legacy stroke)
  systemctl restart strongswan 2>/dev/null || true
  sleep 3   # wait for charon VICI socket to be ready
  swanctl --load-all   2>/dev/null || true
  swanctl --load-creds 2>/dev/null || true

  # Start L2TP
  systemctl restart xl2tpd 2>/dev/null || warn "xl2tpd failed to start (L2TP will be unavailable)"

  # Start backend
  systemctl restart ghostwire-backend
  sleep 2

  info "Waiting for dashboard to come online on port ${PANEL_PORT}..."
  local tries=0
  local backend_up=false
  while [ $tries -lt 25 ]; do
    if curl -sf --max-time 1 "http://127.0.0.1:${PANEL_PORT}/api/health" &>/dev/null || \
       curl -sf --max-time 1 "http://127.0.0.1:${PANEL_PORT}/" &>/dev/null; then
      backend_up=true
      break
    fi
    sleep 1
    tries=$((tries+1))
  done

  if [ "$backend_up" = "false" ]; then
    error_no_exit() { echo -e "${RED}[✗]${NC} $1"; }
    error_no_exit "Backend did not come up on port ${PANEL_PORT} after 25 seconds."
    error_no_exit "Dumping last 40 lines of backend log:"
    echo "──────────────────────────────────────────"
    journalctl -u ghostwire-backend -n 40 --no-pager 2>/dev/null \
      || tail -40 /var/log/ghostwire/backend.log 2>/dev/null \
      || echo "(no log available)"
    echo "──────────────────────────────────────────"
    echo ""
    echo "  To investigate manually:"
    echo "    sudo journalctl -u ghostwire-backend -n 80 --no-pager"
    echo "    sudo tail -80 /var/log/ghostwire/backend.log"
    echo "    sudo systemctl status ghostwire-backend"
    echo ""
    exit 1
  fi

  [ "$USE_DDNS" = "true" ] && systemctl restart ghostwire-ddns || true
  systemctl restart ghostwire-monitor

  log "Services started — backend is live on port ${PANEL_PORT}"
}

print_summary() {
  LOCAL_IP=$(hostname -I | awk '{print $1}')
  echo ""
  echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
  echo -e "${GREEN}        👻 GhostWire Installation Complete!         ${NC}"
  echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
  echo ""
  echo -e "  ${CYAN}▶  Dashboard URL:${NC}  http://${LOCAL_IP}:${PANEL_PORT}"
  echo -e "  ${CYAN}   Admin User:   ${NC}  ${ADMIN_USER}"
  echo -e "  ${CYAN}   VPN Server:   ${NC}  ${DDNS_HOSTNAME:-$PUBLIC_IP}"
  echo -e "  ${CYAN}   Protocols:    ${NC}  IKEv2/EAP  |  IKEv2/PSK  |  IPSec Xauth PSK  |  L2TP/IPSec"
  echo -e "  ${CYAN}   VPN Subnet:   ${NC}  ${VPN_SUBNET}"
  echo -e "  ${CYAN}   PSK:          ${NC}  ${PSK}"
  echo ""
  echo -e "  ${YELLOW}Next steps:${NC}"
  echo "  1. Open the dashboard URL above in your browser"
  echo "  2. Add VPN users and download their profiles"
  echo "  3. Configure SMTP / notifications in Settings"
  echo ""
  echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
  echo ""
  echo "  → http://${LOCAL_IP}:${PANEL_PORT}"
  echo ""
}

# ── Main flow ─────────────────────────────────────────────────────────────────
banner
check_root
detect_ip
collect_config
install_dependencies
setup_directories
copy_files
write_env
setup_python
generate_certs
init_database
configure_strongswan
configure_l2tp
setup_vpn_interface
configure_firewall
setup_dnsmasq
install_systemd_services
build_frontend
start_services
print_summary

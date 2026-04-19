# 👻 GhostWire

**Self-hosted IKEv2/IPSec VPN for Raspberry Pi and Linux.**  
Beautiful dashboard · DNS ad blocking · Multi-server · Plugin system · Zero dependencies outside your server.

[![License: MIT](https://img.shields.io/badge/License-MIT-6366f1.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![Vue](https://img.shields.io/badge/Vue-3-42b883)](https://vuejs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)](https://fastapi.tiangolo.com)

---

## Install in 3 minutes

```bash
curl -fsSL https://ghostwire.sh | sudo bash
```

Or clone and run:

```bash
git clone https://github.com/ghostwire-vpn/ghostwire
cd ghostwire
sudo bash install.sh
```

**Requires:** Debian/Ubuntu/Raspberry Pi OS · root · 512 MB RAM minimum

---

## Web Installer (alternative)

If you prefer a guided browser UI instead of the terminal wizard:

```bash
sudo python3 installer/wizard.py
# Open http://<your-pi-ip>:8080
```

---

## Docker

```bash
cp .env.example .env   # fill in your values
docker compose up -d
```

---

## Features

| Feature | Details |
|---|---|
| **VPN Protocol** | IKEv2/IPSec + EAP-MSCHAPv2 via strongSwan |
| **Dashboard** | Vue 3 SPA — live sessions, bytes, country flags |
| **DNS Ad Blocking** | dnsmasq + blocklist syncer · per-user toggles |
| **Analytics** | GraphQL endpoint · daily rollups · top blocked domains |
| **2FA** | TOTP authenticator apps + email OTP |
| **Multi-server** | Manage a fleet of VPN nodes from one panel |
| **Bot Notifications** | Telegram · Discord · Slack |
| **Plugin System** | Install community plugins via zip upload |
| **Theming** | 5 built-in themes + custom CSS variable editor |
| **Backup/Restore** | AES-256-GCM encrypted `.gwbak` archives |
| **Auto-update** | Dashboard banner when new GitHub release is available |
| **Database** | SQLite (zero config) · Postgres for multi-server |

---

## Writing a Plugin

```json
{
  "slug": "my-plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "You",
  "description": "Does something useful",
  "pip_requirements": ["httpx"]
}
```

Zip the folder and upload from **Dashboard → Plugins → Install Plugin**.

---

## License

MIT — do whatever you want. A ⭐ on GitHub is appreciated.

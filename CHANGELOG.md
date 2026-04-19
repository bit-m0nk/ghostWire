# Changelog

All notable changes are documented here, grouped by build phase.

---

## [6.0.0] — GitHub Launch

### Added
- **Web installer wizard** (`installer/wizard.py`) — browser-guided setup, no terminal required. Auto-detects LAN/public IP, live installation log stream, runs on stdlib + Jinja2 only
- **Docker Compose stack** — `docker-compose.yml` with backend + frontend builder + optional Postgres + optional Watchtower. Multi-arch `Dockerfile.backend` (amd64 + arm64 / Raspberry Pi)
- **Auto-update checker** — `GET /api/updates/status` polls GitHub Releases API (cached 6h). Dashboard shows update banner when a newer version is available
- **Public landing page** (`landing/`) — Jinja2 static page: hero, dashboard mockup, features grid, animated terminal demo, compare table, CTA. No JS required for core content
- **`ghostwire.sh`** — curl-pipe-bash entry point; clones repo then hands off to `install.sh`
- **Non-interactive install mode** — `install.sh` now accepts all config via `GW_*` env vars (used by the web wizard)
- Scheduler: update check runs every 6 hours alongside existing jobs
- `.env.example` with all settings documented

---

## [5.0.0] — Developer Layer

### Added
- **Plugin system** — `domains/plugins/`. Scan `/opt/ghostwire/plugins/` for `ghostwire_plugin.json` manifests. Zip upload installer via dashboard. Runtime pip dep install. Optional `router.py` per plugin registers new API routes without restart
- **Theming engine** — `domains/themes/`. 5 built-in themes: Indigo (default), Midnight Blue, Forest, Rose, Amber. Theme applied at boot via `GET /api/themes/active` (no auth). Live-preview custom theme builder with color pickers per CSS variable
- **Encrypted backup/restore** — `domains/backup/`. AES-256-GCM + PBKDF2-SHA256 (480k iterations). `.gwbak` format: magic header + salt + nonce + GCM tag + ciphertext. Selective restore: database, themes, plugin configs, config files independently toggleable. Peek endpoint validates passphrase before commit
- `App.vue` bootstraps active theme CSS variables before login screen renders
- Event bus: `PLUGIN_ACTIVATED`, `PLUGIN_DEACTIVATED`, `PLUGIN_DELETED`, `THEME_ACTIVATED`, `BACKUP_CREATED`, `BACKUP_RESTORED`

---

## [4.0.0] — Multi-Server & Bots

### Added
- **Multi-server node management** — `domains/nodes/`. Fleet dashboard with CPU/RAM bars, latency sparklines, status colour-coding, 30s auto-poll
- **Bot integrations** — `domains/bots/`. Telegram, Discord, Slack — one codebase, user picks from config. Event bus subscribers fire automatically on VPN connect/disconnect, user events, node state changes
- **Self-service user portal** — `PortalView.vue`. Live active sessions with bytes + country, available servers list with flags and latency, DNS toggle, profile download
- Node health checks every 3 minutes via scheduler
- `GET /vpn/sessions/my` and `GET /vpn/sessions/active` endpoints
- Postgres support: swap SQLite → Postgres with `DB_URL` env var, zero code changes
- Primary node auto-seeded on startup

---

## [3.0.0] — DNS & Analytics

### Added
- **DNS ad blocking** — `domains/dns/`. dnsmasq conf writer, blocklist downloader (hosts-format + plain domain lists), per-user toggles, custom whitelist/blacklist, global overrides
- **Analytics domain** — `domains/analytics/`. `DailySummary` rollup table, nightly scheduler job, dashboard summary row
- **GraphQL endpoint** — Strawberry schema at `/api/graphql`. Queries: `topBlockedDomains`, `hourlyStats`, `summary`, `userSummaries`, `recentEvents`. GraphiQL playground enabled
- 5 new event bus events for DNS domain
- Default blocklist sources seeded on startup
- Dashboard: DNS summary row with block rate bar and top-6 blocked domains

---

## [2.0.0] — Users & Security

### Added
- **Two-factor authentication** — TOTP via pyotp + email OTP. Full setup/confirm/disable flow. Admin force-reset for lost phone recovery. 5-minute challenge token expiry
- **Custom fields builder** — Admin defines extra profile fields from the UI (key/label/type/required). Stored as JSON schema in DB. Per-user values editable from admin panel
- **API key management** — `gw_` prefixed keys shown once, bcrypt-hashed at rest. Max 10 keys per user. `verify_api_key()` middleware ready for Phase 4
- Login returns `{needs_2fa, method, challenge_token}` when 2FA is enabled; `POST /auth/verify-2fa` completes login
- In-memory OTP store with TTL (Redis drop-in comment flagged for multi-server)

---

## [1.0.0] — Foundation

### Added
- Renamed from piVPN to GhostWire across 70 files
- New install path `/opt/ghostwire`, service names, DB filename, log dir, localStorage keys, logo component, colour accent (#6366f1 indigo-purple)
- `infrastructure/db/` — DB abstraction layer. `get_db()`, `Base`, `engine`. SQLite default, Postgres via single env var
- `infrastructure/events/` — In-process event bus with `bus.emit()` / `bus.on()` / `bus.subscribe()`. 7 domains wired
- `domains/` — 7 bounded contexts: auth, users, vpn, stats, profiles, system, config. No domain imports another domain's router
- Apple bundle IDs updated (`com.ghostwire.*`)

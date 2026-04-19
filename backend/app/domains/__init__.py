"""GhostWire — Domains package.

Each sub-package is a bounded context:
  auth     — login, token, password change
  users    — user CRUD, VPN credential management (admin)
  vpn      — session control, VPN restart, server info
  stats    — dashboard, active sessions, audit log queries
  profiles — VPN config file generation and download
  system   — system info, cert regeneration, service status
  config   — SMTP, DDNS, notifications settings
  audit    — AuditLog model (shared, no router of its own)

Phase 3 will add:
  dns      — dnsmasq blocklist, per-user toggles
  analytics — GraphQL endpoint, domain visit logs

Phase 4 will add:
  nodes    — multi-server management
  bots     — Telegram/Discord/Slack integration
"""

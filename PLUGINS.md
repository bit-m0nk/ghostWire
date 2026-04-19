# GhostWire Plugins

Plugins are self-contained folders dropped into `/opt/ghostwire/plugins/`. Each
plugin is a mini Python package that can:

- Add new **API routes** (FastAPI `APIRouter`) mounted under `/api/plugins/<slug>/`
- Run **background logic** by hooking into the event bus
- Expose a **settings UI** through a config JSON schema
- Have **pip dependencies** installed automatically

The Admin panel's **Plugins** page lets you upload, activate/deactivate, and
configure plugins — no SSH or restarts required.

---

## Plugin structure

```
my-plugin/
├── ghostwire_plugin.json   ← required manifest
├── router.py               ← optional: FastAPI routes
├── __init__.py             ← optional
└── requirements.txt        ← optional: extra pip deps (listed in manifest instead)
```

### `ghostwire_plugin.json` — required fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `slug` | string | ✅ | Unique identifier, lowercase, no spaces (e.g. `"bandwidth-alert"`) |
| `name` | string | ✅ | Human-readable display name |
| `version` | string | ✅ | SemVer string e.g. `"1.0.0"` |
| `author` | string | | Your name / handle |
| `description` | string | | Short description shown in the UI |
| `homepage` | string | | URL to docs / source |
| `pip_requirements` | list[str] | | Extra pip packages (e.g. `["httpx>=0.25", "orjson"]`) |

Example:
```json
{
  "slug": "bandwidth-alert",
  "name": "Bandwidth Alert",
  "version": "1.0.0",
  "author": "you",
  "description": "Sends a webhook when a user exceeds a data cap.",
  "pip_requirements": []
}
```

---

## `router.py` — adding API routes

Export a FastAPI `router` object. GhostWire registers it under
`/api/plugins/<slug>/` when the plugin is activated.

```python
from fastapi import APIRouter
router = APIRouter()

@router.get("/hello")
def hello():
    return {"message": "Hello from my plugin!"}
```

The route above becomes: `GET /api/plugins/my-plugin/hello`

> **Note:** Route changes take effect after the next backend restart because
> FastAPI mounts routers at startup. The plugin is still marked active
> immediately — only the HTTP routes need a restart.

---

## Config storage

Use the config API to persist plugin settings without a database:

```python
# Read config set by admin via the UI
from app.domains.plugins.service import get_plugin_config
cfg = get_plugin_config(db, "my-slug")   # returns a dict
webhook_url = cfg.get("webhook_url", "")
```

The admin can set these values from the Plugins page → ⚙ Configure button.

---

## Event bus hooks

React to VPN events without polling:

```python
from app.infrastructure.events.bus import bus, Events

@bus.on(Events.VPN_SESSION_STARTED)
def on_connect(payload: dict):
    username   = payload["username"]
    client_ip  = payload["client_ip"]
    # do something ...
```

Available events: `VPN_SESSION_STARTED`, `VPN_SESSION_ENDED`,
`USER_CREATED`, `USER_DELETED`, `DNS_USER_SETTINGS_UPDATED`,
`PLUGIN_ACTIVATED`, `PLUGIN_DEACTIVATED`.

---

## Deploying a plugin

**Option A — Upload via UI (recommended)**

1. Create your plugin folder, add `ghostwire_plugin.json`, zip the folder.
2. Admin panel → **Plugins** → **Upload Plugin** → choose the zip.
3. Click **Activate**.

**Option B — Drop folder directly on the server**

```bash
sudo cp -r my-plugin/ /opt/ghostwire/plugins/
sudo systemctl restart ghostwire-backend
```

The backend automatically discovers the folder on startup.

---

## Example plugin

See the included `example-plugin/` folder (or `example-plugin.zip`) for a
fully-working plugin that adds a `/api/plugins/example-plugin/status` endpoint
and logs a message whenever a VPN session starts.

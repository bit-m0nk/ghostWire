"""GhostWire — Auto-update checker (Phase 6)

Checks GitHub releases API for a newer version of GhostWire.
Results are cached for 6 hours so the dashboard doesn't hammer the API.
No data is sent to GitHub beyond a standard GET request.
"""
import json
import logging
import threading
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from app.core.security import require_admin

log = logging.getLogger("ghostwire.updates")

router = APIRouter()

CURRENT_VERSION   = "1.0.0"
GITHUB_REPO       = "ghostwire-vpn/ghostwire"
RELEASES_API_URL  = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CHANGELOG_BASE    = f"https://github.com/{GITHUB_REPO}/releases/tag"
CACHE_TTL_SECONDS = 6 * 3600   # 6 hours

# ── In-memory cache ───────────────────────────────────────────────────────────
_cache_lock = threading.Lock()
_cache: dict = {
    "fetched_at":       None,   # datetime | None
    "latest_version":   None,   # str | None
    "release_name":     None,
    "release_url":      None,
    "published_at":     None,
    "has_update":       False,
    "error":            None,
}


def _parse_version(v: str) -> tuple:
    """'v1.2.3' or '1.2.3' → (1, 2, 3)"""
    v = v.lstrip("v")
    try:
        return tuple(int(x) for x in v.split(".")[:3])
    except Exception:
        return (0, 0, 0)


def _is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


def fetch_latest_release() -> dict:
    """Hit the GitHub Releases API and update the in-memory cache."""
    try:
        req = urllib.request.Request(
            RELEASES_API_URL,
            headers={
                "Accept":     "application/vnd.github+json",
                "User-Agent": f"GhostWire/{CURRENT_VERSION}",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())

        latest_tag     = data.get("tag_name", "").lstrip("v")
        has_update     = _is_newer(latest_tag, CURRENT_VERSION)

        with _cache_lock:
            _cache["fetched_at"]     = datetime.now(timezone.utc)
            _cache["latest_version"] = latest_tag
            _cache["release_name"]   = data.get("name", latest_tag)
            _cache["release_url"]    = data.get("html_url", f"{CHANGELOG_BASE}/{latest_tag}")
            _cache["published_at"]   = data.get("published_at")
            _cache["has_update"]     = has_update
            _cache["error"]          = None
        log.info(f"Update check: current={CURRENT_VERSION} latest={latest_tag} has_update={has_update}")
    except Exception as e:
        with _cache_lock:
            _cache["fetched_at"] = datetime.now(timezone.utc)
            _cache["error"]      = str(e)
        log.debug(f"Update check failed: {e}")

    with _cache_lock:
        return dict(_cache)


def get_update_status() -> dict:
    """Return cached status, refreshing if cache is stale."""
    with _cache_lock:
        fetched = _cache["fetched_at"]

    if fetched is None or (datetime.now(timezone.utc) - fetched).total_seconds() > CACHE_TTL_SECONDS:
        return fetch_latest_release()

    with _cache_lock:
        return dict(_cache)


# ── Background refresh (called from scheduler every 6h) ───────────────────────
def background_update_check():
    """Called once at startup (delayed) and then every 6h by the scheduler."""
    time.sleep(30)   # Wait 30s after boot before the first check
    fetch_latest_release()


def start_update_checker():
    t = threading.Thread(target=background_update_check, daemon=True)
    t.start()


# ── API endpoints ─────────────────────────────────────────────────────────────

@router.get("/status")
def update_status(_=Depends(require_admin)):
    """
    Returns the update check result.
    Uses cached data (refreshed every 6h).
    Response:
      {
        "current_version": "1.0.0",
        "latest_version":  "1.0.0",
        "has_update":      true,
        "release_name":    "v1.0.0 — Initial Release",
        "release_url":     "https://github.com/.../releases/tag/v5.1.0",
        "published_at":    "2025-09-01T12:00:00Z",
        "checked_at":      "2025-09-02T08:30:00Z",
        "error":           null
      }
    """
    status = get_update_status()
    return {
        "current_version": CURRENT_VERSION,
        "latest_version":  status.get("latest_version"),
        "has_update":      status.get("has_update", False),
        "release_name":    status.get("release_name"),
        "release_url":     status.get("release_url"),
        "published_at":    status.get("published_at"),
        "checked_at":      status["fetched_at"].isoformat() if status.get("fetched_at") else None,
        "error":           status.get("error"),
    }


@router.post("/refresh")
def refresh_update_check(_=Depends(require_admin)):
    """Force an immediate re-check (bypasses cache)."""
    with _cache_lock:
        _cache["fetched_at"] = None   # Expire cache
    status = get_update_status()
    return {
        "current_version": CURRENT_VERSION,
        "latest_version":  status.get("latest_version"),
        "has_update":      status.get("has_update", False),
        "release_name":    status.get("release_name"),
        "release_url":     status.get("release_url"),
        "error":           status.get("error"),
    }

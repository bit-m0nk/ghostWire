"""GhostWire — Plugin service (Phase 5)

Handles:
 - Scanning PLUGINS_DIR for plugin folders
 - Reading ghostwire_plugin.json manifests
 - Installing/uninstalling pip deps in a subprocess
 - Activating plugins (importing their router.py and mounting routes)
 - Listing available plugins (installed + from a remote registry URL)
"""
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domains.plugins.models import Plugin
from app.infrastructure.events.bus import bus, Events

log = logging.getLogger("ghostwire.plugins")

PLUGINS_DIR = Path(getattr(settings, "PLUGINS_DIR", "/opt/ghostwire/plugins"))

MANIFEST_FILE = "ghostwire_plugin.json"

# Registry of FastAPI routers injected at runtime (slug -> APIRouter)
_mounted_routers: dict = {}


# ─────────────────────────────────────────────────────────────────────────────
# Manifest helpers
# ─────────────────────────────────────────────────────────────────────────────

def _read_manifest(plugin_dir: Path) -> Optional[dict]:
    """Return parsed manifest dict or None if invalid."""
    manifest_path = plugin_dir / MANIFEST_FILE
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path) as f:
            data = json.load(f)
        required = {"slug", "name", "version"}
        if not required.issubset(data.keys()):
            log.warning(f"Plugin manifest missing required keys at {plugin_dir}")
            return None
        return data
    except Exception as e:
        log.warning(f"Plugin manifest parse error at {plugin_dir}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Directory scanner
# ─────────────────────────────────────────────────────────────────────────────

def scan_plugins_dir() -> list[dict]:
    """Return a list of manifest dicts for every valid plugin on disk."""
    if not PLUGINS_DIR.exists():
        return []
    results = []
    for entry in sorted(PLUGINS_DIR.iterdir()):
        if entry.is_dir():
            manifest = _read_manifest(entry)
            if manifest:
                manifest["install_path"] = str(entry)
                results.append(manifest)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# DB sync — ensures every on-disk plugin has a Plugin row
# ─────────────────────────────────────────────────────────────────────────────

def sync_plugins_from_disk(db: Session) -> None:
    """Upsert Plugin rows for every manifest found on disk."""
    for manifest in scan_plugins_dir():
        slug = manifest["slug"]
        row = db.query(Plugin).filter(Plugin.slug == slug).first()
        if row is None:
            row = Plugin(
                slug=slug,
                name=manifest.get("name", slug),
                version=manifest.get("version", "0.0.0"),
                author=manifest.get("author", ""),
                description=manifest.get("description", ""),
                homepage=manifest.get("homepage", ""),
                pip_deps="\n".join(manifest.get("pip_requirements", [])),
                install_path=manifest["install_path"],
                status="inactive",
            )
            db.add(row)
        else:
            # Refresh metadata from disk
            row.name = manifest.get("name", row.name)
            row.version = manifest.get("version", row.version)
            row.author = manifest.get("author", row.author)
            row.description = manifest.get("description", row.description)
            row.homepage = manifest.get("homepage", row.homepage)
            row.pip_deps = "\n".join(manifest.get("pip_requirements", []))
            row.install_path = manifest["install_path"]
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Pip helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pip_install(packages: list[str]) -> tuple[bool, str]:
    if not packages:
        return True, ""
    cmd = [sys.executable, "-m", "pip", "install", "--quiet"] + packages
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        return False, result.stderr[:500]
    return True, ""


def _pip_uninstall(packages: list[str]) -> None:
    if not packages:
        return
    cmd = [sys.executable, "-m", "pip", "uninstall", "-y"] + packages
    subprocess.run(cmd, capture_output=True, text=True, timeout=60)


# ─────────────────────────────────────────────────────────────────────────────
# Activate / deactivate
# ─────────────────────────────────────────────────────────────────────────────

def activate_plugin(db: Session, slug: str) -> tuple[bool, str]:
    """
    Install pip deps, import the plugin's router (if any), and mark active.
    Returns (success, error_message).
    """
    row = db.query(Plugin).filter(Plugin.slug == slug).first()
    if not row:
        return False, "Plugin not found"
    if row.status == "active":
        return True, ""

    plugin_dir = Path(row.install_path)
    if not plugin_dir.exists():
        row.status = "error"
        row.error_msg = "Plugin directory missing"
        db.commit()
        return False, row.error_msg

    # Install pip deps
    deps = [d.strip() for d in (row.pip_deps or "").splitlines() if d.strip()]
    if deps:
        ok, err = _pip_install(deps)
        if not ok:
            row.status = "error"
            row.error_msg = f"pip install failed: {err}"
            db.commit()
            return False, row.error_msg

    # Add plugin directory to sys.path if not already present
    parent = str(plugin_dir.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    # Attempt to import optional router.py
    try:
        plugin_package = plugin_dir.name
        router_module_name = f"{plugin_package}.router"
        import importlib
        if router_module_name not in sys.modules:
            mod = importlib.import_module(router_module_name)
        else:
            mod = sys.modules[router_module_name]
        if hasattr(mod, "router"):
            _mounted_routers[slug] = mod.router
            log.info(f"Plugin '{slug}': router registered (restart required to mount routes)")
    except ModuleNotFoundError:
        pass  # No router.py — fine, plugin is still valid
    except Exception as e:
        log.warning(f"Plugin '{slug}' router import error: {e}")

    row.status = "active"
    row.error_msg = ""
    db.commit()
    bus.emit(Events.PLUGIN_ACTIVATED, {"slug": slug, "name": row.name})
    log.info(f"Plugin '{slug}' activated")
    return True, ""


def deactivate_plugin(db: Session, slug: str) -> None:
    row = db.query(Plugin).filter(Plugin.slug == slug).first()
    if not row:
        return
    row.status = "inactive"
    db.commit()
    _mounted_routers.pop(slug, None)
    bus.emit(Events.PLUGIN_DEACTIVATED, {"slug": slug})
    log.info(f"Plugin '{slug}' deactivated")


def delete_plugin(db: Session, slug: str) -> tuple[bool, str]:
    """Remove plugin from disk and DB."""
    import shutil
    row = db.query(Plugin).filter(Plugin.slug == slug).first()
    if not row:
        return False, "Plugin not found"

    deactivate_plugin(db, slug)

    plugin_dir = Path(row.install_path)
    if plugin_dir.exists():
        try:
            shutil.rmtree(plugin_dir)
        except Exception as e:
            return False, f"Could not delete directory: {e}"

    db.delete(row)
    db.commit()
    bus.emit(Events.PLUGIN_DELETED, {"slug": slug})
    return True, ""


def update_plugin_config(db: Session, slug: str, config: dict) -> bool:
    row = db.query(Plugin).filter(Plugin.slug == slug).first()
    if not row:
        return False
    row.config_json = json.dumps(config)
    db.commit()
    return True


def get_plugin_config(db: Session, slug: str) -> dict:
    row = db.query(Plugin).filter(Plugin.slug == slug).first()
    if not row:
        return {}
    try:
        return json.loads(row.config_json or "{}")
    except Exception:
        return {}


def get_mounted_routers() -> dict:
    """Return slug -> router for all active plugins that exposed a router."""
    return dict(_mounted_routers)


# ─────────────────────────────────────────────────────────────────────────────
# Plugin upload (zip extraction)
# ─────────────────────────────────────────────────────────────────────────────

def install_plugin_from_zip(db: Session, zip_bytes: bytes) -> tuple[bool, str, Optional[str]]:
    """
    Extract a zip uploaded via the UI.
    The zip must contain exactly one top-level folder with a ghostwire_plugin.json.
    Returns (success, error_message, slug_or_None).
    """
    import io
    import zipfile

    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception:
        return False, "Invalid zip file", None

    # Find the plugin root folder (first top-level dir)
    names = zf.namelist()
    top_dirs = {n.split("/")[0] for n in names if "/" in n}
    if not top_dirs:
        return False, "Zip has no sub-folder; place plugin code inside a folder", None
    if len(top_dirs) > 1:
        return False, "Zip must contain exactly one top-level plugin folder", None

    folder_name = top_dirs.pop()
    manifest_path_in_zip = f"{folder_name}/{MANIFEST_FILE}"
    if manifest_path_in_zip not in names:
        return False, f"Missing {MANIFEST_FILE} in plugin folder", None

    # Read and validate manifest
    try:
        manifest_data = json.loads(zf.read(manifest_path_in_zip))
    except Exception:
        return False, "Could not parse ghostwire_plugin.json", None

    required = {"slug", "name", "version"}
    if not required.issubset(manifest_data.keys()):
        return False, "Manifest missing required fields: slug, name, version", None

    slug = manifest_data["slug"]
    dest = PLUGINS_DIR / folder_name

    # Remove existing install if present
    if dest.exists():
        import shutil
        shutil.rmtree(dest)

    # Extract
    zf.extractall(PLUGINS_DIR)

    # Upsert DB row
    row = db.query(Plugin).filter(Plugin.slug == slug).first()
    if row is None:
        row = Plugin(
            slug=slug,
            name=manifest_data.get("name", slug),
            version=manifest_data.get("version", "0.0.0"),
            author=manifest_data.get("author", ""),
            description=manifest_data.get("description", ""),
            homepage=manifest_data.get("homepage", ""),
            pip_deps="\n".join(manifest_data.get("pip_requirements", [])),
            install_path=str(dest),
            status="inactive",
        )
        db.add(row)
    else:
        row.version = manifest_data.get("version", row.version)
        row.name = manifest_data.get("name", row.name)
        row.install_path = str(dest)
        row.pip_deps = "\n".join(manifest_data.get("pip_requirements", []))
        row.status = "inactive"

    db.commit()
    log.info(f"Plugin '{slug}' installed from zip")
    return True, "", slug

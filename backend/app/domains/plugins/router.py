"""GhostWire — Plugin router (Phase 5)

Admin-only endpoints for the plugin system.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.core.security import require_admin
from app.infrastructure.db import get_db
from app.domains.plugins.models import Plugin
from app.domains.plugins import service

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────────

class PluginOut(BaseModel):
    id: int
    slug: str
    name: str
    version: str
    author: str
    description: str
    homepage: str
    status: str
    pip_deps: str
    error_msg: str
    install_path: str

    class Config:
        from_attributes = True


class PluginConfigIn(BaseModel):
    config: dict


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/", response_model=list[PluginOut])
def list_plugins(db: Session = Depends(get_db), _=Depends(require_admin)):
    """Return all registered plugins with their current status."""
    service.sync_plugins_from_disk(db)
    return db.query(Plugin).order_by(Plugin.name).all()


@router.get("/{slug}", response_model=PluginOut)
def get_plugin(slug: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    row = db.query(Plugin).filter(Plugin.slug == slug).first()
    if not row:
        raise HTTPException(404, "Plugin not found")
    return row


@router.post("/upload", response_model=PluginOut)
async def upload_plugin(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Install a plugin from a .zip upload."""
    data = await file.read()
    ok, err, slug = service.install_plugin_from_zip(db, data)
    if not ok:
        raise HTTPException(400, err)
    row = db.query(Plugin).filter(Plugin.slug == slug).first()
    return row


@router.post("/{slug}/activate")
def activate_plugin(slug: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    ok, err = service.activate_plugin(db, slug)
    if not ok:
        raise HTTPException(400, err)
    return {"status": "active", "slug": slug}


@router.post("/{slug}/deactivate")
def deactivate_plugin(slug: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    service.deactivate_plugin(db, slug)
    return {"status": "inactive", "slug": slug}


@router.delete("/{slug}")
def delete_plugin(slug: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    ok, err = service.delete_plugin(db, slug)
    if not ok:
        raise HTTPException(400, err)
    return {"deleted": True}


@router.get("/{slug}/config")
def get_plugin_config(slug: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    return service.get_plugin_config(db, slug)


@router.put("/{slug}/config")
def update_plugin_config(
    slug: str,
    body: PluginConfigIn,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    ok = service.update_plugin_config(db, slug, body.config)
    if not ok:
        raise HTTPException(404, "Plugin not found")
    return {"saved": True}


@router.post("/rescan")
def rescan_plugins(db: Session = Depends(get_db), _=Depends(require_admin)):
    """Re-scan the plugins directory and sync DB rows."""
    service.sync_plugins_from_disk(db)
    count = db.query(Plugin).count()
    return {"synced": True, "total": count}

"""GhostWire — Backup/Restore router (Phase 5)"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.core.security import require_admin
from app.infrastructure.db import get_db
from app.domains.backup import service

router = APIRouter()


class BackupRequest(BaseModel):
    passphrase: str


class RestoreOptions(BaseModel):
    passphrase: str
    restore_db: bool = True
    restore_themes: bool = True
    restore_plugins: bool = True
    restore_config: bool = False


class PeekRequest(BaseModel):
    passphrase: str


@router.post("/create")
def create_backup(body: BackupRequest, db: Session = Depends(get_db), _=Depends(require_admin)):
    """Generate an encrypted .gwbak and return it as a binary download."""
    if not body.passphrase or len(body.passphrase) < 8:
        raise HTTPException(400, "Passphrase must be at least 8 characters")
    encrypted, filename = service.create_backup(db, body.passphrase)
    return Response(
        content=encrypted,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/peek")
async def peek_backup(
    passphrase: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Decrypt just the manifest of a .gwbak — validate before full restore."""
    data = await file.read()
    try:
        manifest = service.peek_backup(data, passphrase)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return manifest


@router.post("/restore")
async def restore_backup(
    passphrase: str,
    restore_db: bool = True,
    restore_themes: bool = True,
    restore_plugins: bool = True,
    restore_config: bool = False,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Upload a .gwbak file and restore selected sections."""
    data = await file.read()
    try:
        summary = service.restore_backup(
            db=db,
            encrypted_bytes=data,
            passphrase=passphrase,
            restore_db=restore_db,
            restore_themes=restore_themes,
            restore_plugins=restore_plugins,
            restore_config=restore_config,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return summary

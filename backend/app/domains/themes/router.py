"""GhostWire — Theme router (Phase 5)"""
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.core.security import require_admin, get_current_user
from app.infrastructure.db import get_db
from app.domains.themes.models import Theme, BUILTIN_THEMES

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────────

class ThemeOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    variables: dict
    is_builtin: bool
    is_active: bool

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_ext(cls, row: Theme):
        try:
            variables = json.loads(row.variables or "{}")
        except Exception:
            variables = {}
        return cls(
            id=row.id, slug=row.slug, name=row.name, description=row.description,
            variables=variables, is_builtin=row.is_builtin, is_active=row.is_active,
        )


class ThemeCreateIn(BaseModel):
    slug: str
    name: str
    description: Optional[str] = ""
    variables: dict


class ThemeUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    variables: Optional[dict] = None


# ─── Seed helper (called from main.py lifespan) ───────────────────────────────

def seed_builtin_themes(db: Session) -> None:
    for t in BUILTIN_THEMES:
        row = db.query(Theme).filter(Theme.slug == t["slug"]).first()
        if row is None:
            db.add(Theme(
                slug=t["slug"],
                name=t["name"],
                description=t["description"],
                variables=json.dumps(t["variables"]),
                is_builtin=True,
                is_active=t.get("is_active", False),
            ))
    db.commit()


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/", response_model=list[ThemeOut])
def list_themes(db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = db.query(Theme).order_by(Theme.is_builtin.desc(), Theme.name).all()
    return [ThemeOut.from_orm_ext(r) for r in rows]


@router.get("/active")
def get_active_theme(db: Session = Depends(get_db)):
    """Public — returns CSS variable JSON for the currently active theme.
    Called by the frontend before login to apply theme without auth."""
    row = db.query(Theme).filter(Theme.is_active == True).first()
    if not row:
        # Fallback to indigo
        row = db.query(Theme).filter(Theme.slug == "indigo").first()
    if not row:
        return {"variables": {}}
    try:
        variables = json.loads(row.variables or "{}")
    except Exception:
        variables = {}
    return {"slug": row.slug, "name": row.name, "variables": variables}


@router.post("/activate/{slug}")
def activate_theme(slug: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    row = db.query(Theme).filter(Theme.slug == slug).first()
    if not row:
        raise HTTPException(404, "Theme not found")
    # Deactivate all others
    db.query(Theme).update({Theme.is_active: False})
    row.is_active = True
    db.commit()
    return {"activated": slug}


@router.post("/", response_model=ThemeOut)
def create_theme(body: ThemeCreateIn, db: Session = Depends(get_db), _=Depends(require_admin)):
    if db.query(Theme).filter(Theme.slug == body.slug).first():
        raise HTTPException(400, "Slug already exists")
    row = Theme(
        slug=body.slug,
        name=body.name,
        description=body.description or "",
        variables=json.dumps(body.variables),
        is_builtin=False,
        is_active=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ThemeOut.from_orm_ext(row)


@router.put("/{slug}", response_model=ThemeOut)
def update_theme(slug: str, body: ThemeUpdateIn, db: Session = Depends(get_db), _=Depends(require_admin)):
    row = db.query(Theme).filter(Theme.slug == slug).first()
    if not row:
        raise HTTPException(404, "Theme not found")
    if row.is_builtin:
        raise HTTPException(400, "Cannot edit built-in themes; create a custom theme instead")
    if body.name is not None:
        row.name = body.name
    if body.description is not None:
        row.description = body.description
    if body.variables is not None:
        row.variables = json.dumps(body.variables)
    db.commit()
    db.refresh(row)
    return ThemeOut.from_orm_ext(row)


@router.delete("/{slug}")
def delete_theme(slug: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    row = db.query(Theme).filter(Theme.slug == slug).first()
    if not row:
        raise HTTPException(404, "Theme not found")
    if row.is_builtin:
        raise HTTPException(400, "Cannot delete built-in themes")
    if row.is_active:
        raise HTTPException(400, "Cannot delete the active theme; switch to another first")
    db.delete(row)
    db.commit()
    return {"deleted": True}

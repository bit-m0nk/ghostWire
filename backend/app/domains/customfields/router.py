"""GhostWire — Custom fields domain router

Two responsibilities:
  1. Admin schema builder — define/update the list of extra fields
  2. Per-user values — read/write the JSON blob in users.custom_fields
"""
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.infrastructure.db import get_db
from app.domains.customfields.models import CustomFieldSchema
from app.domains.users.models import User
from app.core.security import require_admin, get_current_user

router = APIRouter()
log = logging.getLogger("ghostwire.customfields")

# Allowed field types
_VALID_TYPES = {"text", "textarea", "select", "number", "email", "url", "date"}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class FieldDef(BaseModel):
    key:      str
    label:    str
    type:     str = "text"
    required: bool = False
    options:  Optional[list[str]] = None   # only for type=select

    @field_validator("key")
    @classmethod
    def validate_key(cls, v):
        import re
        v = v.strip().lower()
        if not re.match(r'^[a-z0-9_]{1,32}$', v):
            raise ValueError("key must be 1-32 lowercase letters, digits, or underscores")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v not in _VALID_TYPES:
            raise ValueError(f"type must be one of: {', '.join(sorted(_VALID_TYPES))}")
        return v


class SchemaUpdate(BaseModel):
    fields: list[FieldDef]

    @field_validator("fields")
    @classmethod
    def no_duplicate_keys(cls, v):
        keys = [f.key for f in v]
        if len(keys) != len(set(keys)):
            raise ValueError("Field keys must be unique")
        if len(keys) > 20:
            raise ValueError("Maximum 20 custom fields")
        return v


class UserFieldValues(BaseModel):
    values: dict[str, Any]


# ── Admin: schema management ──────────────────────────────────────────────────

@router.get("/schema")
async def get_schema(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return the current active field schema (empty list if none defined)."""
    schema = db.query(CustomFieldSchema).filter(
        CustomFieldSchema.is_active == True
    ).order_by(CustomFieldSchema.created_at.desc()).first()

    if not schema:
        return {"fields": [], "schema_id": None}

    try:
        fields = json.loads(schema.schema_json)
    except Exception:
        fields = []

    return {"fields": fields, "schema_id": schema.id}


@router.put("/schema")
async def update_schema(
    data: SchemaUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Replace the active schema. Old schema is deactivated (kept for history).
    Returns the new schema_id.
    """
    # Deactivate all existing schemas
    db.query(CustomFieldSchema).filter(
        CustomFieldSchema.is_active == True
    ).update({"is_active": False})

    # Create new schema
    new_schema = CustomFieldSchema(
        schema_json=json.dumps([f.model_dump() for f in data.fields]),
        created_by=admin.username,
        is_active=True,
    )
    db.add(new_schema)
    db.commit()
    db.refresh(new_schema)

    log.info(f"Custom field schema updated by {admin.username} — {len(data.fields)} fields")
    return {
        "schema_id": new_schema.id,
        "fields":    data.fields,
        "message":   f"Schema updated with {len(data.fields)} field(s)",
    }


# ── Per-user field values ─────────────────────────────────────────────────────

def _get_active_schema(db: Session) -> list[dict]:
    schema = db.query(CustomFieldSchema).filter(
        CustomFieldSchema.is_active == True
    ).order_by(CustomFieldSchema.created_at.desc()).first()
    if not schema:
        return []
    try:
        return json.loads(schema.schema_json)
    except Exception:
        return []


@router.get("/users/{user_id}/fields")
async def get_user_fields(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return the custom field values for a specific user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    schema = _get_active_schema(db)
    try:
        values = json.loads(user.custom_fields) if user.custom_fields else {}
    except Exception:
        values = {}

    return {"schema": schema, "values": values}


@router.put("/users/{user_id}/fields")
async def update_user_fields(
    user_id: str,
    data: UserFieldValues,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Set custom field values for a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    schema = _get_active_schema(db)
    valid_keys = {f["key"] for f in schema}

    # Only store values for keys that exist in the current schema
    filtered = {k: v for k, v in data.values.items() if k in valid_keys}

    # Validate required fields
    for field in schema:
        if field.get("required") and not filtered.get(field["key"]):
            raise HTTPException(400, f"Field '{field['label']}' is required")

    user.custom_fields = json.dumps(filtered)
    db.commit()

    return {"values": filtered, "message": "Custom fields updated"}


@router.get("/my-fields")
async def get_my_fields(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Portal endpoint — user reads their own custom field values."""
    schema = _get_active_schema(db)
    try:
        values = json.loads(current_user.custom_fields) if current_user.custom_fields else {}
    except Exception:
        values = {}
    return {"schema": schema, "values": values}

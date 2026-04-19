"""GhostWire — Custom fields schema model (customfields domain)

Admin creates a schema: a list of field definitions stored in DB.
Each user's values are stored as JSON in users.custom_fields.

Schema example stored in DB:
  [
    {"key": "department", "label": "Department", "type": "text",    "required": false},
    {"key": "phone",      "label": "Phone",      "type": "text",    "required": false},
    {"key": "tier",       "label": "Tier",       "type": "select",  "required": true,
     "options": ["Basic", "Pro", "Enterprise"]}
  ]
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, Boolean
from app.infrastructure.db import Base


class CustomFieldSchema(Base):
    """
    Stores the admin-defined schema for user profile custom fields.
    There is exactly one active schema at a time (is_active=True).
    Old schemas are kept for audit history but ignored by the app.
    """
    __tablename__ = "custom_field_schemas"

    id         = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    schema_json = Column(Text, nullable=False, default="[]")   # JSON array of FieldDef
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_by  = Column(String(64), nullable=True)
    is_active   = Column(Boolean, default=True, index=True)

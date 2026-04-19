"""GhostWire — Nodes domain router (Phase 4)

Multi-server node management. Admin-only.

Endpoints:
  GET    /nodes/                     — list all nodes + live status
  POST   /nodes/                     — add a new node
  GET    /nodes/fleet                — aggregated fleet summary
  GET    /nodes/{id}                 — single node detail
  PATCH  /nodes/{id}                 — update node config
  DELETE /nodes/{id}                 — remove a node
  POST   /nodes/{id}/check           — trigger immediate health check
  GET    /nodes/{id}/history         — health log for the last 24h
  POST   /nodes/check-all            — ping all nodes now (background)
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.domains.users.models import User
from app.domains.nodes.models import ServerNode, NodeHealthLog
from app.domains.nodes import service as node_svc
from app.infrastructure.db import get_db
from app.infrastructure.events.bus import bus, Events

log = logging.getLogger("ghostwire.nodes")
router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class NodeCreate(BaseModel):
    name:       str
    hostname:   str
    port:       int     = 8080
    api_key:    Optional[str] = None
    location:   str     = ""
    flag:       str     = "🌐"
    notes:      str     = ""


class NodeUpdate(BaseModel):
    name:       Optional[str] = None
    hostname:   Optional[str] = None
    port:       Optional[int] = None
    api_key:    Optional[str] = None
    location:   Optional[str] = None
    flag:       Optional[str] = None
    is_enabled: Optional[bool] = None
    notes:      Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_node_or_404(db: Session, node_id: str) -> ServerNode:
    node = db.query(ServerNode).filter(ServerNode.id == node_id).first()
    if not node:
        raise HTTPException(404, "Node not found")
    return node


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
async def list_nodes(
    db:    Session = Depends(get_db),
    admin: User    = Depends(require_admin),
):
    """List all registered nodes with current status."""
    nodes = db.query(ServerNode).order_by(ServerNode.is_primary.desc(), ServerNode.name).all()
    return [node_svc.node_to_dict(n) for n in nodes]


@router.get("/fleet")
async def fleet_summary(
    db:    Session = Depends(get_db),
    admin: User    = Depends(require_admin),
):
    """Aggregated fleet stats — for the dashboard widget."""
    return node_svc.get_fleet_summary(db)


@router.post("/")
async def add_node(
    data:  NodeCreate,
    db:    Session = Depends(get_db),
    admin: User    = Depends(require_admin),
):
    """Register a new remote node."""
    # Prevent duplicate hostname:port
    existing = db.query(ServerNode).filter(
        ServerNode.hostname == data.hostname,
        ServerNode.port     == data.port,
    ).first()
    if existing:
        raise HTTPException(409, f"Node {data.hostname}:{data.port} already registered")

    node = ServerNode(
        name     = data.name,
        hostname = data.hostname,
        port     = data.port,
        api_key  = data.api_key,
        location = data.location,
        flag     = data.flag,
        notes    = data.notes,
    )
    db.add(node)
    db.commit()
    db.refresh(node)

    bus.emit(Events.NODE_ADDED, {"node_id": node.id, "name": node.name})
    log.info(f"Node added: {node.name} ({node.hostname}:{node.port})")
    return node_svc.node_to_dict(node)


@router.get("/{node_id}")
async def get_node(
    node_id: str,
    db:      Session = Depends(get_db),
    admin:   User    = Depends(require_admin),
):
    node = _get_node_or_404(db, node_id)
    return node_svc.node_to_dict(node)


@router.patch("/{node_id}")
async def update_node(
    node_id: str,
    data:    NodeUpdate,
    db:      Session = Depends(get_db),
    admin:   User    = Depends(require_admin),
):
    node = _get_node_or_404(db, node_id)
    if node.is_primary:
        raise HTTPException(400, "Cannot edit the primary node via this endpoint")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(node, field, value)

    node.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(node)
    bus.emit(Events.NODE_UPDATED, {"node_id": node.id})
    return node_svc.node_to_dict(node)


@router.delete("/{node_id}")
async def delete_node(
    node_id: str,
    db:      Session = Depends(get_db),
    admin:   User    = Depends(require_admin),
):
    node = _get_node_or_404(db, node_id)
    if node.is_primary:
        raise HTTPException(400, "Cannot delete the primary node")

    db.query(NodeHealthLog).filter(NodeHealthLog.node_id == node_id).delete()
    db.delete(node)
    db.commit()
    bus.emit(Events.NODE_REMOVED, {"node_id": node_id})
    return {"message": f"Node '{node.name}' removed"}


@router.post("/{node_id}/check")
async def check_node(
    node_id:    str,
    background: BackgroundTasks,
    db:         Session = Depends(get_db),
    admin:      User    = Depends(require_admin),
):
    """Trigger an immediate health check on this node (runs in background)."""
    node = _get_node_or_404(db, node_id)

    def _do_check():
        with __import__("app.infrastructure.db", fromlist=["SessionLocal"]).SessionLocal() as _db:
            n = _db.query(ServerNode).filter(ServerNode.id == node_id).first()
            if n:
                node_svc.check_node(_db, n)

    background.add_task(_do_check)
    return {"message": f"Health check triggered for '{node.name}'"}


@router.post("/check-all")
async def check_all_nodes(
    background: BackgroundTasks,
    db:         Session = Depends(get_db),
    admin:      User    = Depends(require_admin),
):
    """Ping all enabled non-primary nodes (background task)."""
    def _do_check_all():
        from app.infrastructure.db import SessionLocal
        with SessionLocal() as _db:
            node_svc.check_all_nodes(_db)

    background.add_task(_do_check_all)
    return {"message": "Health check triggered for all nodes"}


@router.get("/{node_id}/history")
async def node_history(
    node_id: str,
    limit:   int     = 48,
    db:      Session = Depends(get_db),
    admin:   User    = Depends(require_admin),
):
    """Return recent health log entries for charting."""
    _get_node_or_404(db, node_id)
    rows = (
        db.query(NodeHealthLog)
        .filter(NodeHealthLog.node_id == node_id)
        .order_by(NodeHealthLog.checked_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "checked_at":     r.checked_at.isoformat() if r.checked_at else None,
            "status":         r.status,
            "latency_ms":     r.latency_ms,
            "active_sessions": r.active_sessions,
            "cpu_percent":    r.cpu_percent,
            "mem_percent":    r.mem_percent,
            "error_message":  r.error_message,
        }
        for r in reversed(rows)
    ]

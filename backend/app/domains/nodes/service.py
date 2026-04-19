"""GhostWire — Node service (Phase 4)

Handles:
- Health pinging remote nodes via their API
- Aggregating stats (sessions, users, CPU, mem) from all nodes
- Pruning old NodeHealthLog rows
"""
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.domains.nodes.models import ServerNode, NodeHealthLog
from app.infrastructure.db import SessionLocal

log = logging.getLogger("ghostwire.nodes")

# How long to wait for a remote node to respond
NODE_PING_TIMEOUT = 8.0


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def check_node(db: Session, node: ServerNode) -> dict:
    """Ping a single node's /api/system/info endpoint. Updates node in place."""
    start = time.monotonic()
    headers = {}
    if node.api_key:
        headers["Authorization"] = f"Bearer {node.api_key}"

    url = f"http://{node.hostname}:{node.port}/api/system/info"

    try:
        resp = httpx.get(url, headers=headers, timeout=NODE_PING_TIMEOUT)
        latency_ms = round((time.monotonic() - start) * 1000, 1)

        if resp.status_code == 200:
            data = resp.json()
            node.status          = "online"
            node.latency_ms      = latency_ms
            node.last_seen       = _utcnow()
            node.error_message   = None
            node.cpu_percent     = data.get("cpu_percent")
            node.mem_percent     = data.get("mem_percent")
            node.uptime_seconds  = data.get("uptime_seconds")
        elif resp.status_code == 401:
            node.status        = "degraded"
            node.error_message = "Auth failed — check API key"
            latency_ms         = None
        else:
            node.status        = "degraded"
            node.error_message = f"HTTP {resp.status_code}"
            latency_ms         = None

    except httpx.ConnectError:
        node.status        = "offline"
        node.error_message = "Connection refused"
        latency_ms         = None
    except httpx.TimeoutException:
        node.status        = "offline"
        node.error_message = f"Timed out after {NODE_PING_TIMEOUT}s"
        latency_ms         = None
    except Exception as exc:
        node.status        = "offline"
        node.error_message = str(exc)[:200]
        latency_ms         = None

    node.last_check_at = _utcnow()

    # --- try to get active sessions count separately ---
    if node.status == "online":
        try:
            sess_url = f"http://{node.hostname}:{node.port}/api/vpn/sessions/active"
            sr = httpx.get(sess_url, headers=headers, timeout=NODE_PING_TIMEOUT)
            if sr.status_code == 200:
                node.active_sessions = len(sr.json())
        except Exception:
            pass
        try:
            users_url = f"http://{node.hostname}:{node.port}/api/users/"
            ur = httpx.get(users_url, headers=headers, timeout=NODE_PING_TIMEOUT)
            if ur.status_code == 200:
                node.total_users = len(ur.json())
        except Exception:
            pass

    db.add(NodeHealthLog(
        node_id         = node.id,
        status          = node.status,
        latency_ms      = latency_ms,
        active_sessions = node.active_sessions,
        cpu_percent     = node.cpu_percent,
        mem_percent     = node.mem_percent,
        error_message   = node.error_message,
    ))
    db.commit()
    return {"node_id": node.id, "status": node.status}


def check_all_nodes(db: Session) -> list[dict]:
    """Scheduled job — ping every enabled, non-primary node."""
    nodes = db.query(ServerNode).filter(
        ServerNode.is_enabled == True,
        ServerNode.is_primary == False,
    ).all()

    results = []
    for node in nodes:
        results.append(check_node(db, node))

    # Prune old health logs (keep 24h)
    cutoff = _utcnow() - timedelta(hours=24)
    db.query(NodeHealthLog).filter(NodeHealthLog.checked_at < cutoff).delete()
    db.commit()

    return results


def get_fleet_summary(db: Session) -> dict:
    """Aggregate stats across all nodes for the dashboard fleet widget."""
    nodes = db.query(ServerNode).filter(ServerNode.is_enabled == True).all()
    total       = len(nodes)
    online      = sum(1 for n in nodes if n.status == "online")
    offline     = sum(1 for n in nodes if n.status == "offline")
    degraded    = sum(1 for n in nodes if n.status == "degraded")
    sessions    = sum(n.active_sessions or 0 for n in nodes)
    users       = sum(n.total_users or 0 for n in nodes)

    return {
        "total":    total,
        "online":   online,
        "offline":  offline,
        "degraded": degraded,
        "total_active_sessions": sessions,
        "total_users": users,
    }


def node_to_dict(node: ServerNode) -> dict:
    return {
        "id":             node.id,
        "name":           node.name,
        "hostname":       node.hostname,
        "port":           node.port,
        "location":       node.location,
        "flag":           node.flag,
        "is_primary":     node.is_primary,
        "is_enabled":     node.is_enabled,
        "status":         node.status,
        "latency_ms":     node.latency_ms,
        "last_seen":      node.last_seen.isoformat() if node.last_seen else None,
        "last_check_at":  node.last_check_at.isoformat() if node.last_check_at else None,
        "active_sessions": node.active_sessions,
        "total_users":    node.total_users,
        "cpu_percent":    node.cpu_percent,
        "mem_percent":    node.mem_percent,
        "uptime_seconds": node.uptime_seconds,
        "error_message":  node.error_message,
        "notes":          node.notes,
        "created_at":     node.created_at.isoformat() if node.created_at else None,
    }

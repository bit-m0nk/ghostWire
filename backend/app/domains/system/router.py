"""GhostWire — System management routes (system domain)"""
import subprocess
import os
import psutil
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.db import get_db
from app.domains.audit.models import AuditLog
from app.domains.users.models import User
from app.core.security import require_admin
from app.core.config import settings
from app.infrastructure.events import bus, Events

router = APIRouter()


class RegenerateRequest(BaseModel):
    new_ip: str = ""
    new_hostname: str = ""


@router.get("/info")
async def system_info(admin: User = Depends(require_admin)):
    try:
        mem  = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        cpu  = psutil.cpu_percent(interval=1)
        uptime_secs = (datetime.now() - datetime.fromtimestamp(psutil.boot_time())).total_seconds()
        uptime_str = (
            f"{int(uptime_secs // 86400)}d "
            f"{int((uptime_secs % 86400) // 3600)}h "
            f"{int((uptime_secs % 3600) // 60)}m"
        )

        ss_result = subprocess.run(
            ["systemctl", "is-active", "strongswan-starter"],
            capture_output=True, text=True
        )
        vpn_running = ss_result.stdout.strip() == "active"
        if not vpn_running:
            ss2 = subprocess.run(
                ["systemctl", "is-active", "strongswan"],
                capture_output=True, text=True
            )
            vpn_running = ss2.stdout.strip() == "active"

        last_ip_file = Path(settings.INSTALL_DIR) / "data" / "last_known_ip.txt"
        current_ip = last_ip_file.read_text().strip() if last_ip_file.exists() else settings.PUBLIC_IP

        cpu_temp = None
        try:
            temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
            if temp_path.exists():
                cpu_temp = round(int(temp_path.read_text().strip()) / 1000, 1)
        except Exception:
            pass
        if cpu_temp is None:
            try:
                temps = psutil.sensors_temperatures()
                for key in ("cpu_thermal", "cpu-thermal", "coretemp", "k10temp"):
                    if key in temps and temps[key]:
                        cpu_temp = round(temps[key][0].current, 1)
                        break
            except Exception:
                pass

        return {
            "cpu_percent":      round(cpu, 1),
            "cpu_temp_c":       cpu_temp,
            "memory_total_mb":  round(mem.total / 1024 / 1024),
            "memory_used_mb":   round(mem.used / 1024 / 1024),
            "memory_percent":   round(mem.percent, 1),
            "disk_total_gb":    round(disk.total / 1024 / 1024 / 1024, 1),
            "disk_used_gb":     round(disk.used / 1024 / 1024 / 1024, 1),
            "disk_percent":     round(disk.percent, 1),
            "uptime":           uptime_str,
            "vpn_running":      vpn_running,
            "current_ip":       current_ip,
            "server_hostname":  settings.server_hostname,
            "ddns_enabled":     settings.ddns_enabled,
            "brand":            settings.VPN_BRAND,
            "panel_port":       settings.PANEL_PORT,
            "vpn_subnet":       settings.VPN_SUBNET,
        }
    except Exception as e:
        raise HTTPException(500, f"System info error: {e}")


@router.post("/regenerate-certs")
async def regenerate_certs(
    data: RegenerateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        import sys
        sys.path.insert(0, str(Path(settings.INSTALL_DIR) / "backend" / "scripts"))
        from generate_ca import CertificateAuthority

        new_ip       = data.new_ip or settings.PUBLIC_IP
        new_hostname = data.new_hostname or settings.server_hostname

        ca = CertificateAuthority(
            brand=settings.VPN_BRAND,
            hostname=new_hostname,
            public_ip=new_ip,
            certs_dir=settings.CERTS_DIR,
            output_dir=str(Path(settings.INSTALL_DIR) / "data" / "certs"),
        )
        ca.regenerate_server_cert(new_ip=new_ip, new_hostname=new_hostname)

        subprocess.run(["swanctl", "--load-creds"], capture_output=True)
        subprocess.run(["swanctl", "--load-conns"], capture_output=True)

        db.add(AuditLog(
            actor=admin.username,
            action="REGENERATE_CERTS",
            target=f"new_ip={new_ip}",
            level="warning"
        ))
        db.commit()

        bus.emit(Events.SYSTEM_CERT_REGENERATED, {
            "actor": admin.username,
            "new_ip": new_ip,
            "new_hostname": new_hostname,
        })

        return {
            "message":      "Server certificate regenerated",
            "new_ip":       new_ip,
            "new_hostname": new_hostname,
            "note":         "All users must re-download their VPN config profiles",
        }
    except Exception as e:
        raise HTTPException(500, f"Certificate regeneration failed: {e}")


@router.get("/current-ip")
async def current_ip(admin: User = Depends(require_admin)):
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://api.ipify.org")
            ip = r.text.strip()
        return {"ip": ip, "server_hostname": settings.server_hostname}
    except Exception as e:
        raise HTTPException(500, f"Could not detect IP: {e}")


@router.get("/services")
async def service_status(admin: User = Depends(require_admin)):
    services = [
        "strongswan-starter", "strongswan",
        "ghostwire-backend", "ghostwire-ddns", "ghostwire-monitor",
        "fail2ban",
    ]
    result = {}
    for svc in services:
        r = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True)
        result[svc] = r.stdout.strip()
    return result

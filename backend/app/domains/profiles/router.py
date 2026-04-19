"""GhostWire — Profile download routes (profiles domain)"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pathlib import Path

from app.infrastructure.db import get_db
from app.domains.users.models import User
from app.core.security import get_current_user
from app.core.config import settings
from app.services.profile_generator import (
    generate_mobileconfig,
    generate_sswan,
    generate_sswan_psk,
    generate_sswan_xauth,
    generate_pbk,
    generate_nmconnection,
    generate_windows_ps1,
    generate_manual_instructions,
)

router = APIRouter()

_FLAG_PATH = Path(settings.INSTALL_DIR) / "data" / "profile_update_required.flag"


def _require_vpn_user(user: User) -> None:
    if not user.vpn_username:
        raise HTTPException(
            400,
            "No VPN credentials assigned to your account. Contact your admin.",
        )


def _require_password(vpn_password: str) -> None:
    if not vpn_password or not vpn_password.strip():
        raise HTTPException(
            400,
            "vpn_password query parameter is required. "
            "Enter your VPN password in the portal first."
        )


# ── CA certificates — PUBLIC (no auth required) ───────────────────────────────

@router.get("/ca.crt", include_in_schema=True)
async def download_ca_pem():
    path = Path(settings.INSTALL_DIR) / "data" / "certs" / "ca.crt"
    if not path.exists():
        raise HTTPException(404, f"CA certificate not found at {path}.")
    return Response(
        content=path.read_bytes(),
        media_type="application/x-pem-file",
        headers={
            "Content-Disposition": f'attachment; filename="{settings.VPN_BRAND}_CA.crt"',
            "Cache-Control": "no-cache",
        },
    )


@router.get("/ca.der", include_in_schema=True)
async def download_ca_der():
    path = Path(settings.INSTALL_DIR) / "data" / "certs" / "ca.der"
    if not path.exists():
        pem_path = Path(settings.INSTALL_DIR) / "data" / "certs" / "ca.crt"
        if pem_path.exists():
            try:
                from cryptography import x509
                from cryptography.hazmat.backends import default_backend
                from cryptography.hazmat.primitives.serialization import Encoding
                cert = x509.load_pem_x509_certificate(pem_path.read_bytes(), default_backend())
                der_bytes = cert.public_bytes(Encoding.DER)
                path.write_bytes(der_bytes)
            except Exception as e:
                raise HTTPException(500, f"Failed to convert CA cert to DER: {e}")
        else:
            raise HTTPException(404, "CA certificate not found.")
    return Response(
        content=path.read_bytes(),
        media_type="application/x-x509-ca-cert",
        headers={
            "Content-Disposition": f'attachment; filename="{settings.VPN_BRAND}_CA.der"',
            "Cache-Control": "no-cache",
        },
    )


@router.get("/ca.cer", include_in_schema=True)
async def download_ca_cer():
    path = Path(settings.INSTALL_DIR) / "data" / "certs" / "ca.der"
    if not path.exists():
        pem_path = Path(settings.INSTALL_DIR) / "data" / "certs" / "ca.crt"
        if pem_path.exists():
            try:
                from cryptography import x509
                from cryptography.hazmat.backends import default_backend
                from cryptography.hazmat.primitives.serialization import Encoding
                cert = x509.load_pem_x509_certificate(pem_path.read_bytes(), default_backend())
                path.write_bytes(cert.public_bytes(Encoding.DER))
            except Exception as e:
                raise HTTPException(500, f"Failed to convert CA cert: {e}")
        else:
            raise HTTPException(404, "CA certificate not found.")
    return Response(
        content=path.read_bytes(),
        media_type="application/x-x509-ca-cert",
        headers={
            "Content-Disposition": f'attachment; filename="{settings.VPN_BRAND}_CA.cer"',
            "Cache-Control": "no-cache",
        },
    )


@router.get("/ca.pem", include_in_schema=True)
async def download_ca_pem_alias():
    path = Path(settings.INSTALL_DIR) / "data" / "certs" / "ca.crt"
    if not path.exists():
        raise HTTPException(404, "CA certificate not found.")
    return Response(
        content=path.read_bytes(),
        media_type="application/x-pem-file",
        headers={
            "Content-Disposition": f'attachment; filename="{settings.VPN_BRAND}_CA.pem"',
            "Cache-Control": "no-cache",
        },
    )


# ── Profile downloads — require auth + vpn_password ──────────────────────────

@router.get("/download/mobileconfig")
async def download_mobileconfig(
    vpn_password: str = "",
    current_user: User = Depends(get_current_user),
):
    _require_vpn_user(current_user)
    _require_password(vpn_password)
    content = generate_mobileconfig(current_user.vpn_username, vpn_password)
    return Response(
        content=content.encode(),
        media_type="application/x-apple-aspen-config",
        headers={
            "Content-Disposition":
                f'attachment; filename="{settings.VPN_BRAND}_VPN.mobileconfig"',
        },
    )


@router.get("/download/sswan")
async def download_sswan(
    vpn_password: str = "",
    current_user: User = Depends(get_current_user),
):
    """strongSwan app profile — IKEv2/EAP with cert server auth."""
    _require_vpn_user(current_user)
    _require_password(vpn_password)
    content = generate_sswan(current_user.vpn_username, vpn_password)
    return Response(
        content=content.encode(),
        media_type="application/json",
        headers={
            "Content-Disposition":
                f'attachment; filename="{settings.VPN_BRAND}_VPN.sswan"',
        },
    )


@router.get("/download/sswan-psk")
async def download_sswan_psk(
    vpn_password: str = "",
    current_user: User = Depends(get_current_user),
):
    """
    strongSwan app / Android built-in profile — IKEv2/EAP-MSCHAPv2 with PSK server auth.
    Required for Android's built-in IKEv2/IPSec MSCHAPv2 connection type.
    """
    _require_vpn_user(current_user)
    _require_password(vpn_password)
    content = generate_sswan_psk(current_user.vpn_username, vpn_password)
    return Response(
        content=content.encode(),
        media_type="application/json",
        headers={
            "Content-Disposition":
                f'attachment; filename="{settings.VPN_BRAND}_VPN_MSCHAPv2.sswan"',
        },
    )


@router.get("/download/sswan-xauth")
async def download_sswan_xauth(
    vpn_password: str = "",
    current_user: User = Depends(get_current_user),
):
    """
    strongSwan app profile — IKEv1/XAuth PSK.
    For Android built-in 'IPSec Xauth PSK' mode via strongSwan app.
    """
    _require_vpn_user(current_user)
    _require_password(vpn_password)
    content = generate_sswan_xauth(current_user.vpn_username, vpn_password)
    return Response(
        content=content.encode(),
        media_type="application/json",
        headers={
            "Content-Disposition":
                f'attachment; filename="{settings.VPN_BRAND}_VPN_XauthPSK.sswan"',
        },
    )


@router.get("/download/pbk")
async def download_pbk(
    vpn_password: str = "",
    current_user: User = Depends(get_current_user),
):
    _require_vpn_user(current_user)
    _require_password(vpn_password)
    content = generate_pbk(current_user.vpn_username, vpn_password)
    return Response(
        content=content.encode("utf-8"),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition":
                f'attachment; filename="{settings.VPN_BRAND}_VPN.pbk"',
        },
    )


@router.get("/download/ps1")
async def download_ps1(
    vpn_password: str = "",
    current_user: User = Depends(get_current_user),
):
    _require_vpn_user(current_user)
    _require_password(vpn_password)
    content = generate_windows_ps1(current_user.vpn_username, vpn_password)
    # Encode with UTF-8 BOM (\xef\xbb\xbf).
    # Windows PowerShell uses the BOM to detect UTF-8 encoding instead of
    # falling back to the system ANSI codepage (cp1252 / cp932 etc.).
    # Without the BOM, any non-ASCII character in the script (even inside a
    # comment) causes a parser error or mojibake on non-English Windows installs.
    bom = b"\xef\xbb\xbf"
    filename = f"Install_{settings.VPN_BRAND}_VPN.ps1"
    # IMPORTANT: use application/octet-stream, NOT text/plain.
    # Edge and Chrome treat text/plain .ps1 responses as "open in browser"
    # or silently rename the file to .txt, breaking the Right-click → Run
    # with PowerShell workflow. octet-stream forces a download with the exact
    # filename given in Content-Disposition.
    # RFC 5987 filename* encoding ensures the brand name (which may contain
    # spaces or non-ASCII) survives HTTP header encoding on all browsers.
    try:
        filename_encoded = filename.encode("ascii").decode("ascii")
        # Pure ASCII — safe for the plain filename= parameter
        disposition = f'attachment; filename="{filename_encoded}"'
    except (UnicodeEncodeError, UnicodeDecodeError):
        # Non-ASCII brand name — use RFC 5987 filename* parameter
        from urllib.parse import quote
        disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=bom + content.encode("utf-8"),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/download/nmconnection")
async def download_nmconnection(
    vpn_password: str = "",
    current_user: User = Depends(get_current_user),
):
    _require_vpn_user(current_user)
    _require_password(vpn_password)
    content = generate_nmconnection(current_user.vpn_username, vpn_password)
    return Response(
        content=content.encode(),
        media_type="text/plain",
        headers={
            "Content-Disposition":
                f'attachment; filename="{settings.VPN_BRAND}_VPN.nmconnection"',
        },
    )


@router.get("/manual")
async def manual_instructions(
    vpn_password: str = "",
    current_user: User = Depends(get_current_user),
):
    _require_vpn_user(current_user)
    _require_password(vpn_password)
    return generate_manual_instructions(current_user.vpn_username, vpn_password)


# ── Profile update flag ───────────────────────────────────────────────────────

@router.get("/update-status")
async def profile_update_status(current_user: User = Depends(get_current_user)):
    return {"update_required": _FLAG_PATH.exists()}


@router.post("/update-acknowledged")
async def profile_update_acknowledged(current_user: User = Depends(get_current_user)):
    if getattr(current_user, "is_admin", False):
        try:
            _FLAG_PATH.unlink(missing_ok=True)
        except Exception as e:
            raise HTTPException(500, f"Could not clear flag: {e}")
        return {"cleared": True}
    return {"cleared": False, "message": "Flag visible until admin acknowledges"}

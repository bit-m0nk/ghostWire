"""
GhostWire — VPN Profile Generator
Generates connection profiles for all platforms.

Android VPN type coverage:
  ikev2-eap     → Android strongSwan app .sswan (cert server auth + EAP-MSCHAPv2)
  ikev2-eap-psk → Android built-in "IKEv2/IPSec MSCHAPv2" (.sswan-psk)
  ikev2-psk     → Android built-in "IKEv2/IPSec PSK" (manual only)
  ikev1-xauth   → Android built-in "IPSec Xauth PSK" (IKEv1 + XAuth, .sswan-xauth)
  l2tp-psk      → Android built-in "L2TP/IPSec PSK" (manual only — xl2tpd)

strongSwan swanctl docs: https://docs.strongswan.org/docs/latest/
"""
import base64
import json
import uuid
from pathlib import Path
from app.core.config import settings


def _get_ca_b64() -> str:
    """Return base64-encoded CA certificate in DER format."""
    ca_der = Path(settings.INSTALL_DIR) / "data" / "certs" / "ca.der"
    ca_pem = Path(settings.INSTALL_DIR) / "data" / "certs" / "ca.crt"
    if ca_der.exists():
        return base64.b64encode(ca_der.read_bytes()).decode()
    if ca_pem.exists():
        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.serialization import Encoding
            cert = x509.load_pem_x509_certificate(ca_pem.read_bytes(), default_backend())
            return base64.b64encode(cert.public_bytes(Encoding.DER)).decode()
        except Exception:
            pass
    return ""


def _get_ca_cn() -> str:
    """Return the CN of the CA cert — used for ServerCertificateIssuerCommonName."""
    ca_pem = Path(settings.INSTALL_DIR) / "data" / "certs" / "ca.crt"
    if ca_pem.exists():
        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend
            from cryptography.x509.oid import NameOID
            cert = x509.load_pem_x509_certificate(ca_pem.read_bytes(), default_backend())
            cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
            return cn[0].value if cn else ""
        except Exception:
            pass
    return ""


def _get_ca_pem() -> str:
    p = Path(settings.INSTALL_DIR) / "data" / "certs" / "ca.crt"
    return p.read_text().strip() if p.exists() else ""


# ─────────────────────────────────────────────────────────────────────────────
# iOS / macOS .mobileconfig
# ─────────────────────────────────────────────────────────────────────────────

def generate_mobileconfig(vpn_username: str, vpn_password: str, display_name: str = None) -> str:
    """
    iOS / macOS .mobileconfig — IKEv2 EAP-MSCHAPv2 (recommended) + IPSec XAuth (fallback).

    IKEv2 EAP-MSCHAPv2 layout per strongSwan official docs:
      AuthenticationMethod = Certificate  → server proves identity with RSA cert
      ExtendedAuthEnabled  = 1            → client authenticates via EAP password
      PayloadCertificateUUID              → NOT SET (that's only for EAP-TLS)
      ServerCertificateIssuerCommonName   → triggers iOS CERTREQ so server sends cert
      ServerCertificateCommonName         → iOS verifies server cert SAN matches this
    """
    server = settings.server_hostname
    brand  = settings.VPN_BRAND
    ca_b64 = _get_ca_b64()
    ca_cn  = _get_ca_cn()
    psk    = settings.PSK

    uid_root  = str(uuid.uuid4())
    uid_ikev2 = str(uuid.uuid4())
    uid_ipsec = str(uuid.uuid4())
    uid_cert  = str(uuid.uuid4())

    cert_payload = f"""    <dict>
      <key>PayloadCertificateFileName</key>
      <string>{brand}_CA.der</string>
      <key>PayloadContent</key>
      <data>{ca_b64}</data>
      <key>PayloadDescription</key>
      <string>{brand} Root CA</string>
      <key>PayloadDisplayName</key>
      <string>{brand} CA</string>
      <key>PayloadIdentifier</key>
      <string>com.ghostwire.ca.{uid_cert}</string>
      <key>PayloadType</key>
      <string>com.apple.security.root</string>
      <key>PayloadUUID</key>
      <string>{uid_cert}</string>
      <key>PayloadVersion</key>
      <integer>1</integer>
    </dict>""" if ca_b64 else ""

    issuer_cn_block = f"""        <key>ServerCertificateIssuerCommonName</key>
        <string>{ca_cn}</string>""" if ca_cn else ""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>PayloadContent</key>
  <array>
{cert_payload}
    <dict>
      <key>PayloadDescription</key>
      <string>{brand} IKEv2 — recommended</string>
      <key>PayloadDisplayName</key>
      <string>{brand} IKEv2</string>
      <key>PayloadIdentifier</key>
      <string>com.ghostwire.ikev2.{uid_ikev2}</string>
      <key>PayloadType</key>
      <string>com.apple.vpn.managed</string>
      <key>PayloadUUID</key>
      <string>{uid_ikev2}</string>
      <key>PayloadVersion</key>
      <integer>1</integer>
      <key>UserDefinedName</key>
      <string>{brand} IKEv2</string>
      <key>VPNType</key>
      <string>IKEv2</string>
      <key>IKEv2</key>
      <dict>
        <key>RemoteAddress</key>
        <string>{server}</string>
        <key>RemoteIdentifier</key>
        <string>{server}</string>
        <key>AuthenticationMethod</key>
        <string>Certificate</string>
{issuer_cn_block}
        <key>ServerCertificateCommonName</key>
        <string>{server}</string>
        <key>ExtendedAuthEnabled</key>
        <integer>1</integer>
        <key>AuthName</key>
        <string>{vpn_username}</string>
        <key>AuthPassword</key>
        <string>{vpn_password}</string>
        <key>IKESecurityAssociationParameters</key>
        <dict>
          <key>EncryptionAlgorithm</key>
          <string>AES-256</string>
          <key>IntegrityAlgorithm</key>
          <string>SHA2-256</string>
          <key>DiffieHellmanGroup</key>
          <integer>14</integer>
        </dict>
        <key>ChildSecurityAssociationParameters</key>
        <dict>
          <key>EncryptionAlgorithm</key>
          <string>AES-256</string>
          <key>IntegrityAlgorithm</key>
          <string>SHA2-256</string>
          <key>DiffieHellmanGroup</key>
          <integer>14</integer>
        </dict>
        <key>DeadPeerDetectionRate</key>
        <string>Medium</string>
        <key>DisableMOBIKE</key>
        <integer>0</integer>
        <key>DisableRedirect</key>
        <integer>0</integer>
        <key>EnableCertificateRevocationCheck</key>
        <integer>0</integer>
        <key>EnablePFS</key>
        <integer>1</integer>
        <key>UseConfigurationAttributeInternalIPSubnet</key>
        <integer>0</integer>
        <key>OnDemandEnabled</key>
        <integer>0</integer>
        <key>OverridePrimary</key>
        <integer>1</integer>
      </dict>
    </dict>

    <dict>
      <key>PayloadDescription</key>
      <string>{brand} IPSec — fallback</string>
      <key>PayloadDisplayName</key>
      <string>{brand} IPSec</string>
      <key>PayloadIdentifier</key>
      <string>com.ghostwire.ipsec.{uid_ipsec}</string>
      <key>PayloadType</key>
      <string>com.apple.vpn.managed</string>
      <key>PayloadUUID</key>
      <string>{uid_ipsec}</string>
      <key>PayloadVersion</key>
      <integer>1</integer>
      <key>UserDefinedName</key>
      <string>{brand} IPSec</string>
      <key>VPNType</key>
      <string>IPSec</string>
      <key>IPSec</key>
      <dict>
        <key>AuthenticationMethod</key>
        <string>SharedSecret</string>
        <key>RemoteAddress</key>
        <string>{server}</string>
        <key>SharedSecret</key>
        <string>{psk}</string>
        <key>GroupName</key>
        <string></string>
        <key>LocalIdentifier</key>
        <string></string>
        <key>LocalIdentifierType</key>
        <string>KeyID</string>
        <key>RemoteIdentifier</key>
        <string>{server}</string>
        <key>XAuthEnabled</key>
        <integer>1</integer>
        <key>XAuthName</key>
        <string>{vpn_username}</string>
        <key>XAuthPassword</key>
        <string>{vpn_password}</string>
        <key>PromptForVPNPIN</key>
        <false/>
        <key>OnDemandEnabled</key>
        <integer>0</integer>
      </dict>
    </dict>
  </array>

  <key>PayloadDescription</key>
  <string>{brand} VPN — IKEv2 + IPSec</string>
  <key>PayloadDisplayName</key>
  <string>{brand} VPN</string>
  <key>PayloadIdentifier</key>
  <string>com.ghostwire.profile.{uid_root}</string>
  <key>PayloadOrganization</key>
  <string>{brand}</string>
  <key>PayloadType</key>
  <string>Configuration</string>
  <key>PayloadUUID</key>
  <string>{uid_root}</string>
  <key>PayloadVersion</key>
  <integer>1</integer>
</dict>
</plist>"""


# ─────────────────────────────────────────────────────────────────────────────
# Android strongSwan app — .sswan profiles
# ─────────────────────────────────────────────────────────────────────────────

def generate_sswan(vpn_username: str, vpn_password: str) -> str:
    """
    Android .sswan profile — IKEv2/EAP-MSCHAPv2 with cert server auth.
    For use with the strongSwan VPN Client app from Play Store.
    remote.id must match the server cert SAN exactly.
    """
    server = settings.server_hostname
    brand  = settings.VPN_BRAND
    ca_pem = _get_ca_pem()

    profile = {
        "uuid":  str(uuid.uuid4()),
        "name":  f"{brand} VPN",
        "type":  "ikev2-eap",
        "remote": {
            "addr":     server,
            "id":       server,
            "cert-req": True,
        },
        "local": {
            "eap-id": vpn_username,
        },
        "ike-proposal": "aes256-sha256-modp2048,aes128-sha256-modp2048",
        "esp-proposal": "aes256-sha256,aes128-sha256",
    }
    if ca_pem:
        profile["remote"]["cacert"] = ca_pem

    return json.dumps(profile, indent=2)


def generate_sswan_psk(vpn_username: str, vpn_password: str) -> str:
    """
    Android .sswan profile — IKEv2/EAP-MSCHAPv2 with PSK server auth.
    For Android built-in "IKEv2/IPSec MSCHAPv2" (Settings → Network → VPN).
    Server authenticates with PSK instead of a certificate.
    """
    server = settings.server_hostname
    brand  = settings.VPN_BRAND
    psk    = settings.PSK

    profile = {
        "uuid":  str(uuid.uuid4()),
        "name":  f"{brand} VPN (MSCHAPv2)",
        "type":  "ikev2-eap",
        "remote": {
            "addr":     server,
            "id":       server,
            "cert-req": False,
        },
        "local": {
            "eap-id": vpn_username,
        },
        "ike-proposal": "aes256-sha256-modp2048,aes128-sha256-modp2048",
        "esp-proposal": "aes256-sha256,aes128-sha256",
        "secret": psk,
    }

    return json.dumps(profile, indent=2)


def generate_sswan_xauth(vpn_username: str, vpn_password: str) -> str:
    """
    Android .sswan profile — IKEv1/XAuth PSK.
    For Android built-in "IPSec Xauth PSK" (Settings → Network → VPN → Type: IPSec Xauth PSK).
    Uses IKEv1 with XAuth for user authentication on top of PSK.

    NOTE: The strongSwan Android app supports IKEv1 XAuth via type "ikev1-xauth-psk".
    For the Android BUILT-IN client, use manual setup (no .sswan import supported for IKEv1).
    This .sswan is for the strongSwan APP using IKEv1 XAuth mode.
    """
    server = settings.server_hostname
    brand  = settings.VPN_BRAND
    psk    = settings.PSK

    profile = {
        "uuid":  str(uuid.uuid4()),
        "name":  f"{brand} VPN (Xauth PSK)",
        "type":  "ikev1-xauth-psk",
        "remote": {
            "addr": server,
            "id":   server,
        },
        "local": {
            "eap-id": vpn_username,
        },
        "ike-proposal": "aes256-sha256-modp2048,aes256-sha1-modp2048,aes128-sha1-modp2048,3des-sha1-modp1024",
        "esp-proposal": "aes256-sha256,aes256-sha1,aes128-sha1,3des-sha1",
        "secret": psk,
    }

    return json.dumps(profile, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Windows
# ─────────────────────────────────────────────────────────────────────────────

def generate_pbk(vpn_username: str, vpn_password: str) -> str:
    """Windows .pbk phonebook — IKEv2 built-in client."""
    server = settings.server_hostname
    brand  = settings.VPN_BRAND
    guid   = "{" + "".join(format(b, "02X") for b in uuid.uuid4().bytes) + "}"
    return f"""[{brand} VPN]
MEDIA=rastapi
Port=VPN2-0
Device={brand} VPN
DEVICE=vpn
Type=IKEV2
IpPrioritizeRemote=1
OverridePref=8
RedialCount=3
RedialPause=5
DialParamsUID=1
Guid={guid}
VpnStrategy=14
ExcludedProtocols=0
LcpExtensions=1
DataEncryption=256
SwCompression=0
NegotiateMultilinkAlways=0
PppTextAuthentication=0
SecureFileAndPrint=1
SecureWorkstation=0
EncryptionType=10
AuthRestrictions=512
L2tpIPSecPskKey=
NumCustomIPSecPolicies=0
NumCustomIPSecOfferPolicies=0
ServerAddr={server}
PreviewPhoneNumber=1
ShowDialingProgress=1
IpAssign=1
IpNameAssign=1
IpDnsAddress=1.1.1.1
IpDns2Address=8.8.8.8
UserName={vpn_username}
Password={vpn_password}
Domain=
"""


# ─────────────────────────────────────────────────────────────────────────────
# Linux NetworkManager
# ─────────────────────────────────────────────────────────────────────────────

def generate_nmconnection(vpn_username: str, vpn_password: str) -> str:
    """Linux NetworkManager .nmconnection — IKEv2."""
    server  = settings.server_hostname
    brand   = settings.VPN_BRAND
    cid     = str(uuid.uuid4())
    ca_path = str(Path(settings.INSTALL_DIR) / "data" / "certs" / "ca.crt")
    return f"""[connection]
id={brand} VPN
uuid={cid}
type=vpn
autoconnect=false

[vpn]
service-type=org.freedesktop.NetworkManager.strongswan
address={server}
remote-id={server}
method=eap
eap-method=mschapv2
user-id={vpn_username}
virtual=true
certificate={ca_path}
encap=no
ipcomp=no

[vpn-secrets]
password={vpn_password}

[ipv4]
method=auto
dns=1.1.1.1;8.8.8.8;

[ipv6]
method=ignore
"""


# ─────────────────────────────────────────────────────────────────────────────
# Windows PowerShell auto-install
# ─────────────────────────────────────────────────────────────────────────────

def generate_windows_ps1(vpn_username: str, vpn_password: str) -> str:
    """Windows PowerShell -- adds IKEv2 VPN + installs CA cert. Run as Administrator.

    IMPORTANT: This function returns a plain ASCII/UTF-8 string.
    The download endpoint MUST encode it as UTF-8 with BOM (\xef\xbb\xbf) so that
    Windows PowerShell (which defaults to the system ANSI codepage) reads it
    correctly without mojibake on special characters.
    All non-ASCII glyphs (em-dash, box-drawing chars) have been replaced with
    plain ASCII equivalents so the script is safe on any Windows locale.
    """
    server = settings.server_hostname
    brand  = settings.VPN_BRAND
    ca_b64 = _get_ca_b64()

    cert_block = ""
    if ca_b64:
        cert_block = f"""
# --- Step 1: Install CA Certificate -----------------------------------------
Write-Host "Installing {brand} CA certificate..." -ForegroundColor Cyan
$certBytes = [Convert]::FromBase64String("{ca_b64}")
$certPath  = "$env:TEMP\\{brand}_CA.der"
[IO.File]::WriteAllBytes($certPath, $certBytes)
$cert  = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2
$cert.Import($certPath)
$store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root","LocalMachine")
$store.Open("ReadWrite")
$store.Add($cert)
$store.Close()
Remove-Item $certPath -ErrorAction SilentlyContinue
Write-Host "CA certificate installed." -ForegroundColor Green
"""

    # NOTE: All {{ }} are Python f-string escapes that produce literal { } in the .ps1.
    # All em-dashes (--) and box-drawing characters have been replaced with plain ASCII
    # so Windows PowerShell can parse the file regardless of the active code page.
    script = f"""# {brand} VPN -- Windows Setup Script
# Right-click this file and choose "Run with PowerShell" (as Administrator)
# Requires: PowerShell 5.0+  |  Windows 8.1 / 10 / 11 x64

# Allow this script to run in the current process only (no permanent policy change)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

$ErrorActionPreference = "Stop"
$VPNName  = "{brand} VPN"
$Server   = "{server}"
$Username = "{vpn_username}"
$Password = "{vpn_password}"
{cert_block}
# --- Step 2: Enable strong DH (MODP-2048) in Windows registry ---------------
Write-Host "Configuring Windows IKEv2 cipher policy..." -ForegroundColor Cyan
$regPath = "HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Rasman\\Parameters"
try {{
    Set-ItemProperty -Path $regPath -Name "NegotiateDH2048_AES256" -Value 2 -Type DWord -Force
    Write-Host "  Registry key set: NegotiateDH2048_AES256 = 2" -ForegroundColor Green
}} catch {{
    Write-Host "  Registry update skipped (non-fatal, defaults will be used): $_" -ForegroundColor Yellow
}}

# --- Step 3: Remove existing VPN entry if present ---------------------------
$existing = Get-VpnConnection -Name $VPNName -ErrorAction SilentlyContinue
if ($existing) {{
    Remove-VpnConnection -Name $VPNName -Force
    Write-Host "Removed old VPN entry." -ForegroundColor Yellow
}}

# --- Step 4: Add IKEv2 VPN connection ----------------------------------------
# AuthenticationMethod is set separately after creation to avoid the
# "conflicting PPP tunnel types" error on some Windows builds.
Write-Host "Adding $VPNName..." -ForegroundColor Cyan
Add-VpnConnection `
    -Name $VPNName `
    -ServerAddress $Server `
    -TunnelType "IKEv2" `
    -EncryptionLevel "Required" `
    -RememberCredential $true `
    -SplitTunneling $false `
    -PassThru | Out-Null

# Set EAP authentication separately
Set-VpnConnection -Name $VPNName -AuthenticationMethod EAP

Write-Host "$VPNName added." -ForegroundColor Green

# --- Step 5: Set IKEv2 cipher suite ------------------------------------------
try {{
    Set-VpnConnectionIPsecConfiguration `
        -ConnectionName $VPNName `
        -AuthenticationTransformConstants SHA256128 `
        -CipherTransformConstants AES256 `
        -EncryptionMethod AES256 `
        -IntegrityCheckMethod SHA256 `
        -DHGroup Group14 `
        -PfsGroup None `
        -Force
    Write-Host "IKEv2 cipher suite configured." -ForegroundColor Green
}} catch {{
    Write-Host "Cipher config skipped (non-fatal, defaults will be used): $_" -ForegroundColor Yellow
}}

# --- Step 6: Save credentials ------------------------------------------------
cmdkey /add:$Server /user:$Username /pass:$Password | Out-Null
Write-Host "Credentials saved." -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  $VPNName installed successfully!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Connect: Settings -> Network & Internet -> VPN -> $VPNName -> Connect"
Write-Host "  OR click the network icon in the taskbar -> $VPNName"
Write-Host ""
Write-Host "  Username : $Username"
Write-Host "  Password : $Password"
Write-Host ""
Write-Host "  TIP: If the connection fails on first attempt, disconnect and retry." -ForegroundColor Yellow
Write-Host "  The registry cipher change takes effect after one failed attempt." -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to exit"
"""
    return script


# ─────────────────────────────────────────────────────────────────────────────
# Manual setup instructions (all platforms)
# ─────────────────────────────────────────────────────────────────────────────

def generate_manual_instructions(vpn_username: str, vpn_password: str) -> dict:
    """Manual setup instructions for all platforms."""
    server = settings.server_hostname
    brand  = settings.VPN_BRAND
    psk    = settings.PSK

    return {
        "server":  server,
        "brand":   brand,
        "psk":     psk,
        "vpn_username": vpn_username,
        "ipsec_identifier": server,

        # ── iOS ──────────────────────────────────────────────────────────────
        "ios_ikev2": {
            "title": "iOS — IKEv2 Certificate (recommended — use .mobileconfig)",
            "path":  "Settings → General → VPN & Device Management → VPN → Add → IKEv2",
            "fields": {
                "Type":                "IKEv2",
                "Description":         f"{brand} VPN",
                "Server":              server,
                "Remote ID":           server,
                "Local ID":            "(leave blank)",
                "User Authentication": "Username",
                "Username":            vpn_username,
                "Password":            vpn_password,
            },
            "note": f"IMPORTANT: 'Remote ID' must be exactly '{server}'. Install CA cert first or use .mobileconfig which bundles it automatically."
        },

        "ios_ipsec": {
            "title": "iOS — IPSec/Cisco XAuth PSK (no cert needed)",
            "path":  "Settings → General → VPN & Device Management → VPN → Add → IPSec",
            "fields": {
                "Type":            "IPSec",
                "Description":     f"{brand} VPN",
                "Server":          server,
                "Account":         vpn_username,
                "Password":        vpn_password,
                "Use Certificate": "OFF",
                "Group Name":      brand,
                "Secret":          psk,
            },
            "note": "Leave Group Name as shown. No certificate installation needed."
        },

        # ── Android ──────────────────────────────────────────────────────────
        "android_mschapv2": {
            "title": "Android — IKEv2/IPSec MSCHAPv2 (built-in)",
            "path":  "Settings → Network → VPN → + → IKEv2/IPSec MSCHAPv2",
            "fields": {
                "Name":             f"{brand} VPN",
                "Type":             "IKEv2/IPSec MSCHAPv2",
                "Server address":   server,
                "IPSec identifier": server,
                "IPSec CA cert":    "Download and install ca.der from user portal",
                "Username":         vpn_username,
                "Password":         vpn_password,
            },
            "note": "IPSec identifier is required — enter the server hostname exactly. Install CA cert first."
        },

        "android_psk": {
            "title": "Android — IKEv2/IPSec PSK (built-in, no cert)",
            "path":  "Settings → Network → VPN → + → IKEv2/IPSec PSK",
            "fields": {
                "Name":                 f"{brand} VPN",
                "Type":                 "IKEv2/IPSec PSK",
                "Server address":       server,
                "IPSec identifier":     server,
                "IPSec pre-shared key": psk,
                "Username":             vpn_username,
                "Password":             vpn_password,
            },
            "note": "No certificate installation needed. Use if MSCHAPv2 is unavailable."
        },

        "android_xauth_psk": {
            "title": "Android — IPSec Xauth PSK (built-in, IKEv1)",
            "path":  "Settings → Network → VPN → + → IPSec Xauth PSK",
            "fields": {
                "Name":                 f"{brand} VPN",
                "Type":                 "IPSec Xauth PSK",
                "Server address":       server,
                "IPSec identifier":     server,
                "IPSec pre-shared key": psk,
                "Username":             vpn_username,
                "Password":             vpn_password,
            },
            "note": "Legacy IKEv1 XAuth. Works on all Android versions. No certificate needed."
        },

        "android_l2tp_psk": {
            "title": "Android — L2TP/IPSec PSK (built-in)",
            "path":  "Settings → Network → VPN → + → L2TP/IPSec PSK",
            "fields": {
                "Name":                 f"{brand} VPN",
                "Type":                 "L2TP/IPSec PSK",
                "Server address":       server,
                "L2TP secret":          "(leave blank)",
                "IPSec identifier":     server,
                "IPSec pre-shared key": psk,
                "Username":             vpn_username,
                "Password":             vpn_password,
            },
            "note": "Classic L2TP/IPSec. Works on all Android versions. No certificate needed. Leave 'L2TP secret' blank."
        },

        # ── Windows ──────────────────────────────────────────────────────────
        "windows": {
            "title": "Windows — built-in IKEv2",
            "path":  "Settings → Network & Internet → VPN → Add a VPN connection",
            "fields": {
                "VPN provider":           "Windows (built-in)",
                "Connection name":        f"{brand} VPN",
                "Server name or address": server,
                "VPN type":               "IKEv2",
                "Type of sign-in info":   "Username and password",
                "Username":               vpn_username,
                "Password":               vpn_password,
            },
            "note": "Run the .ps1 PowerShell script to also install the CA certificate automatically."
        },

        # ── Linux ─────────────────────────────────────────────────────────────
        "linux": {
            "title": "Linux — NetworkManager",
            "path":  "Terminal",
            "commands": [
                "# Import .nmconnection profile:",
                f"sudo nmcli connection import type vpn file {brand}_VPN.nmconnection",
                "",
                "# Connect:",
                f"sudo nmcli connection up '{brand} VPN'",
                "",
                "# Or install CA cert manually:",
                f"sudo cp {brand}_CA.crt /usr/local/share/ca-certificates/",
                "sudo update-ca-certificates",
            ]
        }
    }

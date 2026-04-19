"""GhostWire — Email service
Security policy (enforced here):
  - Invitation flow sends TWO separate emails:
      Email 1 (connection package): CA cert attachment + VPN server details + portal URL
      Email 2 (credentials):        Panel password + VPN password only — no cert, no config
  - Password reset can optionally resend the connection package email only
    (never re-sends passwords in the same email as connection details).
"""
import base64
import logging
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

log = logging.getLogger("ghostwire.email")


def _read_env() -> dict:
    """Read /opt/ghostwire/.env into a dict."""
    env_path = Path("/opt/ghostwire/.env")
    if not env_path.exists():
        return {}
    cfg = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        cfg[k.strip()] = v.strip()
    return cfg


def _smtp_settings() -> Optional[dict]:
    """Read SMTP settings. Returns None if SMTP_HOST not set."""
    cfg = _read_env()
    host = cfg.get("SMTP_HOST", "").strip()
    if not host:
        return None

    password = (
        cfg.get("SMTP_PASS", "") or
        cfg.get("SMTP_PASSWORD", "")
    ).strip()

    user      = cfg.get("SMTP_USER", "").strip()
    from_addr = cfg.get("SMTP_FROM", user).strip() or user
    brand     = cfg.get("VPN_BRAND", "GhostWire").strip()

    return {
        "host":     host,
        "port":     int(cfg.get("SMTP_PORT", "587")),
        "user":     user,
        "password": password,
        "from":     from_addr,
        "brand":    brand,
        "tls":      cfg.get("SMTP_TLS", "starttls").lower(),
    }


def _do_send(smtp: dict, to_email: str, msg: MIMEMultipart) -> None:
    """Low-level send. Raises on failure."""
    tls_mode = smtp.get("tls", "starttls")
    if tls_mode == "ssl":
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp["host"], smtp["port"], context=ctx) as s:
            if smtp["user"]:
                s.login(smtp["user"], smtp["password"])
            s.sendmail(smtp["from"], [to_email], msg.as_string())
    else:
        with smtplib.SMTP(smtp["host"], smtp["port"]) as s:
            if tls_mode == "starttls":
                s.starttls(context=ssl.create_default_context())
            if smtp["user"]:
                s.login(smtp["user"], smtp["password"])
            s.sendmail(smtp["from"], [to_email], msg.as_string())


def _send_message(
    smtp: dict,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str = "",
) -> None:
    """Low-level helper shared by otp_service etc. Raises on failure."""
    from_header = f"{smtp['brand']} <{smtp['from']}>"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_header
    msg["To"]      = to_email
    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    _do_send(smtp, to_email, msg)


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL 1 — Connection Package
# Contains: CA cert (attachment) + server details + portal URL + setup steps
# Does NOT contain any passwords.
# ─────────────────────────────────────────────────────────────────────────────

def build_connection_package_email(
    full_name: str,
    username: str,
    vpn_username: str,
    server_hostname: str,
    panel_url: str,
    brand: str = "GhostWire",
) -> tuple[str, str]:
    """Build (subject, html_body) for the connection package email (no passwords)."""
    subject = f"{brand} VPN — Connection Package"
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{subject}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0f1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#e2e8f0}}
.wrapper{{max-width:600px;margin:40px auto;background:#1a1d2e;border-radius:16px;overflow:hidden;border:1px solid #2d3748}}
.header{{background:linear-gradient(135deg,#6366f1 0%,#8b5cf6 50%,#06b6d4 100%);padding:40px 32px;text-align:center}}
.logo-row{{display:flex;align-items:center;justify-content:center;gap:12px;margin-bottom:12px}}
.logo-icon{{width:52px;height:52px;background:rgba(255,255,255,0.15);border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:26px}}
.brand-text{{font-size:26px;font-weight:800;color:#fff;letter-spacing:-0.5px}}
.brand-pi{{color:#c7d2fe}}.brand-vpn{{color:#a5f3fc}}
.header p{{color:rgba(255,255,255,0.75);font-size:14px;margin-top:4px}}
.body{{padding:32px}}
.greeting{{font-size:16px;margin-bottom:6px}}
.sub{{color:#94a3b8;font-size:13px;margin-bottom:24px}}
.info-card{{background:#0f1117;border:1px solid #2d3748;border-radius:12px;padding:18px;margin:16px 0}}
.info-card h3{{font-size:11px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:#6366f1;margin-bottom:12px}}
.info-row{{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid #1e2233}}
.info-row:last-child{{border-bottom:none}}
.info-label{{font-size:12px;color:#94a3b8}}
.info-value{{font-family:'Courier New',monospace;font-size:12px;color:#e2e8f0;background:#1a1d2e;padding:3px 8px;border-radius:5px;word-break:break-all}}
.cert-box{{background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);border-radius:10px;padding:14px 16px;margin:16px 0;font-size:13px;color:#a5b4fc}}
.steps h3{{font-size:11px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:#06b6d4;margin-bottom:14px;margin-top:20px}}
.step{{display:flex;gap:12px;margin-bottom:14px;align-items:flex-start}}
.step-num{{min-width:26px;height:26px;background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#fff;flex-shrink:0}}
.step-text{{font-size:13px;color:#cbd5e1;line-height:1.6;padding-top:3px}}
.step-text strong{{color:#e2e8f0}}
.notice{{background:rgba(6,182,212,0.08);border:1px solid rgba(6,182,212,0.25);border-radius:10px;padding:12px 14px;margin:16px 0;font-size:12px;color:#67e8f9}}
.cta{{text-align:center;margin:24px 0 8px}}
.cta a{{display:inline-block;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;text-decoration:none;padding:13px 30px;border-radius:10px;font-size:14px;font-weight:600}}
.footer{{background:#0f1117;padding:18px 32px;text-align:center;font-size:11px;color:#475569;border-top:1px solid #1e2233}}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <div class="logo-row">
      <div class="logo-icon">👻</div>
      <div class="brand-text"><span class="brand-pi">Ghost</span><span class="brand-vpn">Wire</span></div>
    </div>
    <p>Your VPN connection package — keep this email</p>
  </div>
  <div class="body">
    <p class="greeting">Hi <strong>{full_name}</strong>,</p>
    <p class="sub">Your {brand} VPN connection package is attached. This email contains your server details and the CA certificate. Your login credentials will arrive in a separate email.</p>

    <div class="info-card">
      <h3>🌐 Server Details</h3>
      <div class="info-row"><span class="info-label">Server</span><span class="info-value">{server_hostname}</span></div>
      <div class="info-row"><span class="info-label">Protocol</span><span class="info-value">IKEv2 / IPSec</span></div>
      <div class="info-row"><span class="info-label">Ports</span><span class="info-value">UDP 500, 4500</span></div>
      <div class="info-row"><span class="info-label">VPN Username</span><span class="info-value">{vpn_username}</span></div>
      <div class="info-row"><span class="info-label">Portal URL</span><span class="info-value">{panel_url}</span></div>
    </div>

    <div class="cert-box">
      📎 <strong>CA Certificate attached</strong> — The file <code>{brand}_CA.crt</code> is attached to this email.
      Install it on your device before connecting, or use the .mobileconfig profile from the portal which bundles it automatically.
    </div>

    <div class="steps">
      <h3>📱 Quick Setup</h3>
      <div class="step">
        <div class="step-num">1</div>
        <div class="step-text"><strong>Get your passwords</strong> — check the separate credentials email that was sent alongside this one.</div>
      </div>
      <div class="step">
        <div class="step-num">2</div>
        <div class="step-text"><strong>Log in to the portal</strong> at <a href="{panel_url}" style="color:#6366f1">{panel_url}</a> with your username and panel password.</div>
      </div>
      <div class="step">
        <div class="step-num">3</div>
        <div class="step-text"><strong>iPhone / iPad:</strong> Download the .mobileconfig from the portal and open it in Safari → Settings → General → VPN &amp; Device Management → Install.</div>
      </div>
      <div class="step">
        <div class="step-num">4</div>
        <div class="step-text"><strong>Android / Windows / Linux:</strong> Download the matching profile from the portal and follow the on-screen instructions.</div>
      </div>
    </div>

    <div class="notice">
      💡 The easiest way to connect on iPhone is via the <strong>.mobileconfig profile</strong> from the portal — it installs the CA cert and configures both IKEv2 and IPSec automatically.
    </div>

    <div class="cta"><a href="{panel_url}">Open VPN Portal →</a></div>
  </div>
  <div class="footer">
    Sent by {brand} VPN &nbsp;·&nbsp; {server_hostname}<br>
    If you did not expect this email, please ignore it.
  </div>
</div>
</body>
</html>"""
    return subject, html


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL 2 — Credentials only
# Contains: panel password + VPN password — no cert, no config details
# ─────────────────────────────────────────────────────────────────────────────

def build_credentials_email(
    full_name: str,
    username: str,
    panel_password: str,
    vpn_password: str,
    panel_url: str,
    brand: str = "GhostWire",
) -> tuple[str, str]:
    """Build (subject, html_body) for the credentials-only email."""
    subject = f"{brand} VPN — Your Login Credentials"
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{subject}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0f1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#e2e8f0}}
.wrapper{{max-width:600px;margin:40px auto;background:#1a1d2e;border-radius:16px;overflow:hidden;border:1px solid #2d3748}}
.header{{background:linear-gradient(135deg,#7c3aed 0%,#6366f1 100%);padding:32px;text-align:center}}
.header h1{{font-size:20px;font-weight:800;color:#fff;margin-bottom:4px}}
.header p{{color:rgba(255,255,255,0.7);font-size:13px}}
.body{{padding:32px}}
.greeting{{font-size:16px;margin-bottom:6px}}
.sub{{color:#94a3b8;font-size:13px;margin-bottom:24px}}
.creds-card{{background:#0f1117;border:1px solid #2d3748;border-radius:12px;padding:18px;margin:16px 0}}
.creds-card h3{{font-size:11px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:#8b5cf6;margin-bottom:12px}}
.cred-row{{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid #1e2233}}
.cred-row:last-child{{border-bottom:none}}
.cred-label{{font-size:12px;color:#94a3b8}}
.cred-value{{font-family:'Courier New',monospace;font-size:13px;color:#e2e8f0;background:#1a1d2e;padding:4px 10px;border-radius:5px;word-break:break-all;font-weight:600}}
.warning{{background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);border-radius:10px;padding:12px 14px;margin:16px 0;font-size:12px;color:#fbbf24}}
.security-note{{background:rgba(16,185,129,0.06);border:1px solid rgba(16,185,129,0.2);border-radius:10px;padding:12px 14px;margin:16px 0;font-size:12px;color:#6ee7b7}}
.footer{{background:#0f1117;padding:18px 32px;text-align:center;font-size:11px;color:#475569;border-top:1px solid #1e2233}}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>🔑 Your Credentials</h1>
    <p>Keep this email private — do not forward it</p>
  </div>
  <div class="body">
    <p class="greeting">Hi <strong>{full_name}</strong>,</p>
    <p class="sub">Here are your {brand} VPN login credentials. Your connection package (with the CA certificate and setup instructions) was sent in a separate email.</p>

    <div class="creds-card">
      <h3>🖥 Portal Login — {panel_url}</h3>
      <div class="cred-row"><span class="cred-label">Username</span><span class="cred-value">{username}</span></div>
      <div class="cred-row"><span class="cred-label">Password</span><span class="cred-value">{panel_password}</span></div>
    </div>

    <div class="creds-card">
      <h3>🌐 VPN Password</h3>
      <div class="cred-row"><span class="cred-label">VPN Password</span><span class="cred-value">{vpn_password}</span></div>
      <div class="cred-row"><span class="cred-label">Note</span><span class="cred-label" style="text-align:right;color:#64748b">Enter this in the portal to download your config profile</span></div>
    </div>

    <div class="warning">⚠ Save these credentials somewhere safe — this email is the only time these passwords will be sent to you. Delete this email once saved.</div>

    <div class="security-note">🔒 These credentials were sent in a separate email from your connection package intentionally. If either email is intercepted, the attacker cannot connect without both.</div>
  </div>
  <div class="footer">
    Sent by {brand} VPN<br>
    If you did not expect this email, please ignore it and contact your administrator.
  </div>
</div>
</body>
</html>"""
    return subject, html


# ─────────────────────────────────────────────────────────────────────────────
# Public send functions
# ─────────────────────────────────────────────────────────────────────────────

def _get_ca_attachment(brand: str) -> Optional[MIMEApplication]:
    """Return a MIME attachment for the CA cert, or None if not found."""
    from app.core.config import settings
    ca_pem = Path(settings.INSTALL_DIR) / "data" / "certs" / "ca.crt"
    ca_der = Path(settings.INSTALL_DIR) / "data" / "certs" / "ca.der"
    if ca_pem.exists():
        data = ca_pem.read_bytes()
        att = MIMEApplication(data, Name=f"{brand}_CA.crt")
        att["Content-Disposition"] = f'attachment; filename="{brand}_CA.crt"'
        return att
    if ca_der.exists():
        data = ca_der.read_bytes()
        att = MIMEApplication(data, Name=f"{brand}_CA.der")
        att["Content-Disposition"] = f'attachment; filename="{brand}_CA.der"'
        return att
    return None


def send_welcome_emails(
    to_email: str,
    full_name: str,
    username: str,
    panel_password: str,
    vpn_username: str,
    vpn_password: str,
    server_hostname: str,
    panel_url: str,
    brand: str = "GhostWire",
) -> tuple[bool, str]:
    """
    Send TWO separate emails:
      1. Connection package (CA cert attached + server details, NO passwords)
      2. Credentials (passwords only, no cert or config)
    Returns (success, message).
    """
    smtp = _smtp_settings()
    if not smtp:
        return False, "SMTP not configured — add SMTP_HOST and SMTP_PASS to /opt/ghostwire/.env"

    from_header = f"{smtp['brand']} <{smtp['from']}>"
    errors = []

    # ── Email 1: Connection package ───────────────────────────────────────────
    try:
        subj1, html1 = build_connection_package_email(
            full_name=full_name, username=username, vpn_username=vpn_username,
            server_hostname=server_hostname, panel_url=panel_url, brand=brand,
        )
        msg1 = MIMEMultipart("mixed")
        msg1["Subject"] = subj1
        msg1["From"]    = from_header
        msg1["To"]      = to_email
        alt1 = MIMEMultipart("alternative")
        alt1.attach(MIMEText(html1, "html"))
        msg1.attach(alt1)

        ca_att = _get_ca_attachment(brand)
        if ca_att:
            msg1.attach(ca_att)

        _do_send(smtp, to_email, msg1)
        log.info(f"Connection package email sent to {to_email}")
    except Exception as e:
        log.error(f"Connection package email failed to {to_email}: {e}")
        errors.append(f"connection package: {e}")

    # ── Email 2: Credentials ──────────────────────────────────────────────────
    try:
        subj2, html2 = build_credentials_email(
            full_name=full_name, username=username,
            panel_password=panel_password, vpn_password=vpn_password,
            panel_url=panel_url, brand=brand,
        )
        msg2 = MIMEMultipart("alternative")
        msg2["Subject"] = subj2
        msg2["From"]    = from_header
        msg2["To"]      = to_email
        msg2.attach(MIMEText(html2, "html"))
        _do_send(smtp, to_email, msg2)
        log.info(f"Credentials email sent to {to_email}")
    except Exception as e:
        log.error(f"Credentials email failed to {to_email}: {e}")
        errors.append(f"credentials: {e}")

    if errors:
        return False, "Email error(s): " + "; ".join(errors)
    return True, f"2 emails sent to {to_email} (connection package + credentials)"


def send_connection_package_email(
    to_email: str,
    full_name: str,
    username: str,
    vpn_username: str,
    server_hostname: str,
    panel_url: str,
    brand: str = "GhostWire",
) -> tuple[bool, str]:
    """
    Send the connection package email only (no passwords).
    Used when admin resets a password and wants to re-send the connection details.
    """
    smtp = _smtp_settings()
    if not smtp:
        return False, "SMTP not configured"

    from_header = f"{smtp['brand']} <{smtp['from']}>"
    try:
        subj, html = build_connection_package_email(
            full_name=full_name, username=username, vpn_username=vpn_username,
            server_hostname=server_hostname, panel_url=panel_url, brand=brand,
        )
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subj
        msg["From"]    = from_header
        msg["To"]      = to_email
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(html, "html"))
        msg.attach(alt)

        ca_att = _get_ca_attachment(brand)
        if ca_att:
            msg.attach(ca_att)

        _do_send(smtp, to_email, msg)
        log.info(f"Connection package re-sent to {to_email}")
        return True, f"Connection package sent to {to_email}"
    except Exception as e:
        log.error(f"Connection package re-send failed to {to_email}: {e}")
        return False, f"Email failed: {e}"


# ── Legacy alias (keeps otp_service etc. working) ─────────────────────────────

def send_welcome_email(
    to_email: str,
    full_name: str,
    username: str,
    panel_password: str,
    vpn_username: str,
    vpn_password: str,
    server_hostname: str,
    panel_url: str,
    brand: str = "GhostWire",
) -> tuple[bool, str]:
    """Backwards-compatible alias — now sends two separate emails."""
    return send_welcome_emails(
        to_email=to_email, full_name=full_name, username=username,
        panel_password=panel_password, vpn_username=vpn_username,
        vpn_password=vpn_password, server_hostname=server_hostname,
        panel_url=panel_url, brand=brand,
    )

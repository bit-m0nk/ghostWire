"""
GhostWire — IP Monitor, DDNS Updater, and Notification Service

Dynu API note:
  Dynu uses a dedicated "IP Update Password" (not your account password).
  Get it from: https://www.dynu.com/ControlPanel/APICredentials
  The password can be sent as plain text, MD5, or SHA256 hash.
  We use SHA256 for security.

  Endpoint: https://api.dynu.com/nic/update
  Params:   hostname=<your.dynu.hostname>&myip=<ip>&username=<user>&password=<sha256>
  Response: "good <ip>" on success, "nochg <ip>" if unchanged, "badauth" on failure.

No-IP API:
  Endpoint: https://dynupdate.no-ip.com/nic/update
  Auth:     HTTP Basic (email:password)
  Params:   hostname=<hostname>&myip=<ip>
"""
import asyncio
import hashlib
import logging
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv("/opt/ghostwire/.env")

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from app.core.config import settings

log = logging.getLogger("ghostwire.monitor")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/var/log/ghostwire/monitor.log"),
    ],
)

IP_CACHE_FILE = Path("/opt/ghostwire/data/last_known_ip.txt")
POLL_INTERVAL = 300  # 5 minutes


# ── IP detection ──────────────────────────────────────────────────────────────

async def get_public_ip() -> str:
    sources = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://api4.my-ip.io/ip",
        "https://ipecho.net/plain",
    ]
    async with httpx.AsyncClient(timeout=10) as c:
        for url in sources:
            try:
                r = await c.get(url)
                ip = r.text.strip()
                if ip and 7 <= len(ip) <= 45:
                    return ip
            except Exception:
                continue
    raise RuntimeError("All IP detection sources failed")


# ── Dynu DDNS ─────────────────────────────────────────────────────────────────

def _dynu_sha256(password: str) -> str:
    """SHA256-hash the IP Update Password as Dynu recommends."""
    return hashlib.sha256(password.encode()).hexdigest()


async def update_dynu(ip: str) -> bool:
    """
    Update Dynu DDNS using the IP Update Password (not account password).
    Docs: https://www.dynu.com/DynamicDNS/IP-Update-Protocol
    """
    if not settings.dynu_configured:
        return False
    try:
        pw_hash = _dynu_sha256(settings.DYNU_IP_UPDATE_PASS)
        url = (
            f"https://api.dynu.com/nic/update"
            f"?hostname={settings.DYNU_HOSTNAME}"
            f"&myip={ip}"
            f"&username={settings.DYNU_USERNAME}"
            f"&password={pw_hash}"
        )
        headers = {"User-Agent": f"GhostWire/1.0 {settings.DYNU_USERNAME}"}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(url, headers=headers)
        body = r.text.strip()
        success = body.startswith("good") or body.startswith("nochg")
        if success:
            log.info(f"Dynu updated: {body}")
        else:
            log.error(f"Dynu update failed: {body}")
        return success
    except Exception as e:
        log.error(f"Dynu exception: {e}")
        return False


# ── No-IP DDNS ────────────────────────────────────────────────────────────────

async def update_noip(ip: str) -> bool:
    if not settings.noip_configured:
        return False
    try:
        url = (
            f"https://dynupdate.no-ip.com/nic/update"
            f"?hostname={settings.NOIP_HOSTNAME}"
            f"&myip={ip}"
        )
        headers = {"User-Agent": f"GhostWire/1.0 {settings.NOIP_USERNAME}"}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                url,
                auth=(settings.NOIP_USERNAME, settings.NOIP_PASSWORD),
                headers=headers,
            )
        body = r.text.strip()
        success = body.startswith("good") or body.startswith("nochg")
        if success:
            log.info(f"No-IP updated: {body}")
        else:
            log.error(f"No-IP update failed: {body}")
        return success
    except Exception as e:
        log.error(f"No-IP exception: {e}")
        return False


async def update_all_ddns(ip: str) -> bool:
    """Update primary provider first; try failover if primary fails."""
    if settings.DDNS_PRIMARY == "noip":
        ok = await update_noip(ip)
        if not ok:
            log.warning("Primary (No-IP) failed — trying Dynu failover")
            ok = await update_dynu(ip)
    else:
        ok = await update_dynu(ip)
        if not ok:
            log.warning("Primary (Dynu) failed — trying No-IP failover")
            ok = await update_noip(ip)
    return ok


# ── Notifications ─────────────────────────────────────────────────────────────

async def send_telegram(message: str) -> None:
    if not settings.TG_BOT_TOKEN or not settings.TG_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{settings.TG_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=15) as c:
            await c.post(url, json={
                "chat_id":    settings.TG_CHAT_ID,
                "text":       message,
                "parse_mode": "Markdown",
            })
        log.info("Telegram notification sent")
    except Exception as e:
        log.error(f"Telegram failed: {e}")


def send_email(subject: str, body: str) -> None:
    if not settings.SMTP_HOST or not settings.NOTIFY_EMAIL:
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = settings.SMTP_USER
        msg["To"]      = settings.NOTIFY_EMAIL
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as s:
            s.ehlo()
            s.starttls()
            s.login(settings.SMTP_USER, settings.SMTP_PASS)
            s.sendmail(settings.SMTP_USER, settings.NOTIFY_EMAIL, msg.as_string())
        log.info("Email notification sent")
    except Exception as e:
        log.error(f"Email failed: {e}")


async def notify_ip_change(old_ip: str, new_ip: str) -> None:
    brand = settings.VPN_BRAND
    now   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if settings.ddns_enabled:
        tg = (
            f"*{brand} VPN — IP Updated*\n\n"
            f"Time: {now}\n"
            f"Old IP: `{old_ip}`\n"
            f"New IP: `{new_ip}`\n\n"
            f"DDNS updated automatically.\n"
            f"Connect to `{settings.DDNS_HOSTNAME}` as usual — no action needed."
        )
        email_body = (
            f"{brand} VPN — IP Change Notification\n"
            f"{'='*42}\n"
            f"Time   : {now}\n"
            f"Old IP : {old_ip}\n"
            f"New IP : {new_ip}\n\n"
            f"DDNS updated automatically.\n"
            f"Hostname: {settings.DDNS_HOSTNAME}\n"
            f"No action required.\n"
        )
    else:
        tg = (
            f"*{brand} VPN — IP Changed — Action Required*\n\n"
            f"Time: {now}\n"
            f"Old IP: `{old_ip}`\n"
            f"*New IP: `{new_ip}`*\n\n"
            f"Your server certificate has been regenerated.\n"
            f"⚠️ All VPN users must re-download their profiles.\n\n"
            f"Steps for each user:\n"
            f"1. Open the user portal: http://{new_ip}:{settings.PANEL_PORT}/portal\n"
            f"2. Download and re-import their VPN profile\n"
            f"3. Update server address to: `{new_ip}`\n\n"
            f"Admin panel:\n"
            f"→ http://{new_ip}:{settings.PANEL_PORT}"
        )
        email_body = (
            f"{brand} VPN — IP Change Notification\n"
            f"{'='*42}\n"
            f"Time   : {now}\n"
            f"Old IP : {old_ip}\n"
            f"NEW IP : {new_ip}   <-- UPDATE THIS\n\n"
            f"Your server certificate has been regenerated with the new IP.\n"
            f"ACTION REQUIRED: All VPN users must re-download their profiles.\n\n"
            f"Steps for each user:\n"
            f"  1. Visit the user portal: http://{new_ip}:{settings.PANEL_PORT}/portal\n"
            f"  2. Download and re-import their VPN profile (.mobileconfig / .sswan)\n"
            f"  3. Update the server address to: {new_ip}\n\n"
            f"Admin panel:\n"
            f"  http://{new_ip}:{settings.PANEL_PORT}\n"
        )

    await send_telegram(tg)
    send_email(f"{brand} VPN — New IP: {new_ip}", email_body)


# ── State helpers ─────────────────────────────────────────────────────────────

def load_last_ip() -> str:
    return IP_CACHE_FILE.read_text().strip() if IP_CACHE_FILE.exists() else ""


def save_last_ip(ip: str) -> None:
    IP_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    IP_CACHE_FILE.write_text(ip)


def update_env_ip(new_ip: str) -> None:
    env_path = Path("/opt/ghostwire/.env")
    if not env_path.exists():
        return
    lines = env_path.read_text().splitlines()
    env_path.write_text(
        "\n".join(
            f"PUBLIC_IP={new_ip}" if l.startswith("PUBLIC_IP=") else l
            for l in lines
        ) + "\n"
    )


# ── IP change handler ─────────────────────────────────────────────────────────

def _update_swanctl_server_id(new_ip: str) -> None:
    """Patch the SERVER_ID (local id) in ghostwire.conf to the new IP."""
    import re as _re
    conf_path = Path(settings.SWANCTL_CONF)
    if not conf_path.exists():
        log.warning(f"swanctl conf not found at {conf_path} — skipping id update")
        return
    text = conf_path.read_text()
    # Only replace `id = <value>` inside local { ... } blocks, not remote/child IDs
    new_text = _re.sub(
        r'(local\s*\{[^}]*?id\s*=\s*)(\S+)',
        lambda m: m.group(1) + new_ip,
        text,
        flags=_re.DOTALL,
    )
    if new_text != text:
        conf_path.write_text(new_text)
        log.info(f"swanctl conf: SERVER_ID updated to {new_ip}")


def _write_profile_update_flag() -> None:
    flag = Path(settings.INSTALL_DIR) / "data" / "profile_update_required.flag"
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text("1")
    log.info("Profile update flag written")


async def handle_ip_change(old_ip: str, new_ip: str) -> None:
    log.info(f"IP changed: {old_ip} → {new_ip}")

    if settings.ddns_enabled:
        ok = await update_all_ddns(new_ip)
        if not ok:
            log.error("All DDNS providers failed to update!")
    else:
        # No-DDNS mode: regenerate server cert with new IP as SAN
        try:
            from scripts.generate_ca import CertificateAuthority
            import subprocess
            ca = CertificateAuthority(
                brand=settings.VPN_BRAND,
                hostname=new_ip,
                public_ip=new_ip,
                certs_dir=settings.CERTS_DIR,
                output_dir=str(Path(settings.INSTALL_DIR) / "data" / "certs"),
            )
            ca.regenerate_server_cert(new_ip=new_ip)
            # Update swanctl config then hot-reload credentials and connections
            _update_swanctl_server_id(new_ip)
            subprocess.run(["swanctl", "--load-creds"],   capture_output=True)
            subprocess.run(["swanctl", "--load-conns"],   capture_output=True)
            # Flag that all user profiles need re-download (new cert embedded)
            _write_profile_update_flag()
            log.info("Server certificate regenerated for new IP")

            # Emit event so other subsystems can react
            try:
                from app.infrastructure.events.bus import event_bus, AppEvent
                event_bus.emit(AppEvent.SYSTEM_CERT_REGENERATED, {"new_ip": new_ip})
            except Exception as ev_err:
                log.debug(f"Event bus not available: {ev_err}")

        except Exception as e:
            log.error(f"Cert regeneration failed: {e}")

    update_env_ip(new_ip)
    save_last_ip(new_ip)
    await notify_ip_change(old_ip, new_ip)


# ── Main loop ─────────────────────────────────────────────────────────────────

async def monitor_loop() -> None:
    log.info(f"GhostWire IP monitor started (interval={POLL_INTERVAL}s, ddns={settings.ddns_enabled})")
    if settings.ddns_enabled:
        log.info(f"Primary DDNS: {settings.DDNS_PRIMARY} | Dynu: {settings.dynu_configured} | No-IP: {settings.noip_configured}")

    try:
        current_ip = await get_public_ip()
    except Exception as e:
        log.error(f"Could not detect initial IP: {e}")
        current_ip = settings.PUBLIC_IP

    save_last_ip(current_ip)
    log.info(f"Current public IP: {current_ip}")

    # Initial DDNS update and startup notification
    if settings.ddns_enabled:
        await update_all_ddns(current_ip)

    startup_msg = (
        f"*{settings.VPN_BRAND} VPN Started*\n"
        f"IP: `{current_ip}`\n"
        f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    await send_telegram(startup_msg)

    refresh_ticks = 0
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        refresh_ticks += 1
        try:
            new_ip  = await get_public_ip()
            last_ip = load_last_ip()

            if new_ip != last_ip and last_ip:
                await handle_ip_change(last_ip, new_ip)
            else:
                save_last_ip(new_ip)
                # Refresh DDNS every 30 min even without IP change
                # (free DDNS services expire if not refreshed)
                if settings.ddns_enabled and refresh_ticks % 6 == 0:
                    await update_all_ddns(new_ip)
                    log.debug(f"DDNS refreshed (periodic), IP={new_ip}")

        except Exception as e:
            log.error(f"Monitor loop error: {e}")


if __name__ == "__main__":
    asyncio.run(monitor_loop())

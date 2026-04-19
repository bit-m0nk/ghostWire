"""GhostWire — Encrypted Backup/Restore service (Phase 5)

Backup format: .gwbak file (AES-256-GCM encrypted zip)

Structure inside the zip:
  manifest.json         — metadata (version, timestamp, hostname)
  ghostwire.db          — full SQLite snapshot  (or pg_dump for Postgres)
  config/               — /opt/ghostwire/*.env  and strongSwan snippets
  plugins/              — serialized plugin manifests + configs (not binaries)
  themes.json           — all theme rows
  plugins.json          — all plugin DB rows

Encryption:
  PBKDF2-HMAC-SHA256 (480 000 iterations) → 32-byte AES key
  AES-256-GCM with a random 16-byte salt and 12-byte nonce
  File layout: magic(8) + salt(16) + nonce(12) + tag(16) + ciphertext

The passphrase is supplied by the admin at backup/restore time and is
never stored anywhere.
"""
import io
import json
import logging
import os
import shutil
import socket
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings

log = logging.getLogger("ghostwire.backup")

MAGIC = b"GWBAK001"          # 8 bytes — magic header
PBKDF2_ITERATIONS = 480_000
DB_PATH = Path(getattr(settings, "DB_PATH", "/opt/ghostwire/ghostwire.db"))
INSTALL_DIR = Path(getattr(settings, "INSTALL_DIR", "/opt/ghostwire"))


# ─────────────────────────────────────────────────────────────────────────────
# Crypto helpers
# ─────────────────────────────────────────────────────────────────────────────

def _derive_key(passphrase: str, salt: bytes) -> bytes:
    import hashlib
    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode(), salt, PBKDF2_ITERATIONS, dklen=32
    )


def _encrypt(data: bytes, passphrase: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt  = os.urandom(16)
    nonce = os.urandom(12)
    key   = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    ct_with_tag = aesgcm.encrypt(nonce, data, None)
    # AES-GCM from cryptography appends the 16-byte tag at the end
    ct  = ct_with_tag[:-16]
    tag = ct_with_tag[-16:]
    return MAGIC + salt + nonce + tag + ct


def _decrypt(data: bytes, passphrase: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if len(data) < 52:   # 8+16+12+16 minimum
        raise ValueError("File too short — not a valid .gwbak")
    if data[:8] != MAGIC:
        raise ValueError("Not a GhostWire backup file (bad magic)")
    salt  = data[8:24]
    nonce = data[24:36]
    tag   = data[36:52]
    ct    = data[52:]
    key   = _derive_key(passphrase, salt)
    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ct + tag, None)
    except Exception:
        raise ValueError("Decryption failed — wrong passphrase or corrupted file")


# ─────────────────────────────────────────────────────────────────────────────
# Create backup
# ─────────────────────────────────────────────────────────────────────────────

def create_backup(db: Session, passphrase: str) -> tuple[bytes, str]:
    """
    Build an encrypted .gwbak and return (encrypted_bytes, filename).
    """
    from app.domains.themes.models import Theme
    from app.domains.plugins.models import Plugin

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:

        # Manifest is written last (after all sections) so late-added fields
        # like security_note are captured. Build the dict now, write at end.
        manifest = {
            "ghostwire_version": "5.0.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "hostname": socket.gethostname(),
            "includes": ["database", "themes", "plugins_meta", "config_files"],
        }

        # 2. SQLite DB snapshot
        if DB_PATH.exists():
            zf.write(DB_PATH, "ghostwire.db")
        else:
            log.warning("DB file not found at %s — skipping DB snapshot", DB_PATH)

        # 3. Themes JSON export
        themes = db.query(Theme).all()
        themes_data = []
        for t in themes:
            try:
                variables = json.loads(t.variables or "{}")
            except Exception:
                variables = {}
            themes_data.append({
                "slug": t.slug, "name": t.name, "description": t.description,
                "variables": variables, "is_builtin": t.is_builtin, "is_active": t.is_active,
            })
        zf.writestr("themes.json", json.dumps(themes_data, indent=2))

        # 4. Plugins JSON export (manifest + config only, no binaries)
        plugins = db.query(Plugin).all()
        plugins_data = []
        for p in plugins:
            try:
                config = json.loads(p.config_json or "{}")
            except Exception:
                config = {}
            plugins_data.append({
                "slug": p.slug, "name": p.name, "version": p.version,
                "author": p.author, "description": p.description,
                "status": p.status, "config": config,
                "pip_deps": p.pip_deps,
            })
        zf.writestr("plugins.json", json.dumps(plugins_data, indent=2))

        # 5. Config files from install dir
        for env_file in INSTALL_DIR.glob("*.env"):
            try:
                zf.write(env_file, f"config/{env_file.name}")
            except Exception as e:
                log.warning("Could not include config file %s: %s", env_file, e)

        # 6. strongSwan swanctl config — EAP user secrets are STRIPPED before
        #    inclusion.  The secrets {} block contains plaintext VPN passwords
        #    for every user; we deliberately exclude it from the backup so that
        #    a stolen backup file cannot be used to harvest credentials.
        #    Certs (x509 / x509ca) are included because they are not secret.
        swanctl_conf = Path(settings.SWANCTL_CONF)
        if swanctl_conf.exists():
            try:
                raw = swanctl_conf.read_text()
                # Strip the entire secrets { ... } block and all ghostwire-user
                # marker lines, leaving connections/pools intact.
                import re as _re
                # Remove top-level secrets { ... } block (non-greedy, handles nesting
                # via a simple brace-counter approach after the opening keyword).
                def _strip_secrets_block(text: str) -> str:
                    out = []
                    depth = 0
                    in_secrets = False
                    for line in text.splitlines(keepends=True):
                        stripped = line.strip()
                        if not in_secrets and _re.match(r'^secrets\s*\{', stripped):
                            in_secrets = True
                            depth = 1
                            continue
                        if in_secrets:
                            depth += stripped.count("{") - stripped.count("}")
                            if depth <= 0:
                                in_secrets = False
                            continue
                        # Also drop any stray ghostwire-user marker lines
                        if "ghostwire-user:" in line:
                            continue
                        out.append(line)
                    return "".join(out)

                sanitised = _strip_secrets_block(raw)
                zf.writestr(f"swanctl/conf.d/{swanctl_conf.name}", sanitised)
                manifest["security_note"] = (
                    "swanctl secrets{} block was stripped from the backup. "
                    "VPN user credentials are NOT included. "
                    "After restoring, run 'Reset VPN Password' for each user."
                )
            except Exception as e:
                log.warning("Could not include swanctl conf: %s", e)

        swanctl_dir = Path(settings.CERTS_DIR)
        for cert_subdir in ("x509", "x509ca"):
            subdir_path = swanctl_dir / cert_subdir
            if subdir_path.exists():
                for cf in subdir_path.glob("*.crt"):
                    try:
                        zf.write(cf, f"swanctl/{cert_subdir}/{cf.name}")
                    except Exception as e:
                        log.warning("Could not include cert %s: %s", cf, e)
        # Intentionally skip swanctl/private/ — private keys are never backed up

        # Write manifest last so all fields (incl. security_note) are captured
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    plain_bytes = buf.getvalue()
    encrypted   = _encrypt(plain_bytes, passphrase)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"ghostwire-backup-{ts}.gwbak"
    log.info("Backup created: %s (%d bytes encrypted)", filename, len(encrypted))
    return encrypted, filename


# ─────────────────────────────────────────────────────────────────────────────
# Restore from backup
# ─────────────────────────────────────────────────────────────────────────────

def restore_backup(
    db: Session,
    encrypted_bytes: bytes,
    passphrase: str,
    restore_db: bool = True,
    restore_themes: bool = True,
    restore_plugins: bool = True,
    restore_config: bool = False,
) -> dict:
    """
    Decrypt and extract a .gwbak.
    Returns a summary dict of what was restored.
    Raises ValueError on bad passphrase or corrupt file.
    """
    from app.domains.themes.models import Theme
    from app.domains.plugins.models import Plugin

    plain_bytes = _decrypt(encrypted_bytes, passphrase)
    buf = io.BytesIO(plain_bytes)

    summary = {
        "manifest": None,
        "themes_restored": 0,
        "plugins_restored": 0,
        "db_restored": False,
        "config_restored": False,
        "warnings": [],
    }

    with zipfile.ZipFile(buf, "r") as zf:
        names = set(zf.namelist())

        # Read manifest
        if "manifest.json" in names:
            summary["manifest"] = json.loads(zf.read("manifest.json"))

        # Restore themes
        if restore_themes and "themes.json" in names:
            themes_data = json.loads(zf.read("themes.json"))
            for t in themes_data:
                if t.get("is_builtin"):
                    continue  # never overwrite built-ins from backup
                row = db.query(Theme).filter(Theme.slug == t["slug"]).first()
                if row:
                    row.name = t["name"]
                    row.description = t.get("description", "")
                    row.variables = json.dumps(t.get("variables", {}))
                else:
                    db.add(Theme(
                        slug=t["slug"], name=t["name"],
                        description=t.get("description", ""),
                        variables=json.dumps(t.get("variables", {})),
                        is_builtin=False, is_active=False,
                    ))
                summary["themes_restored"] += 1
            db.commit()

        # Restore plugin configs (not binaries)
        if restore_plugins and "plugins.json" in names:
            plugins_data = json.loads(zf.read("plugins.json"))
            for p in plugins_data:
                row = db.query(Plugin).filter(Plugin.slug == p["slug"]).first()
                if row:
                    row.config_json = json.dumps(p.get("config", {}))
                    summary["plugins_restored"] += 1
            db.commit()

        # Restore config files
        if restore_config:
            for name in names:
                if name.startswith("config/"):
                    fname = name[len("config/"):]
                    dest = INSTALL_DIR / fname
                    try:
                        dest.write_bytes(zf.read(name))
                        summary["config_restored"] = True
                    except Exception as e:
                        summary["warnings"].append(f"Config restore {fname}: {e}")

        # Restore SQLite DB (last — service restart needed after)
        if restore_db and "ghostwire.db" in names:
            try:
                db_backup_path = INSTALL_DIR / "ghostwire.db.bak"
                if DB_PATH.exists():
                    shutil.copy2(DB_PATH, db_backup_path)
                DB_PATH.write_bytes(zf.read("ghostwire.db"))
                summary["db_restored"] = True
                summary["warnings"].append(
                    "Database restored — restart the GhostWire service to reload."
                )
            except Exception as e:
                summary["warnings"].append(f"DB restore failed: {e}")

    log.info("Backup restored: %s", summary)
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# Peek — read manifest without decrypting full backup
# ─────────────────────────────────────────────────────────────────────────────

def peek_backup(encrypted_bytes: bytes, passphrase: str) -> dict:
    """Decrypt and return just the manifest — quick validation before restore."""
    plain_bytes = _decrypt(encrypted_bytes, passphrase)
    buf = io.BytesIO(plain_bytes)
    with zipfile.ZipFile(buf, "r") as zf:
        if "manifest.json" not in zf.namelist():
            return {}
        return json.loads(zf.read("manifest.json"))

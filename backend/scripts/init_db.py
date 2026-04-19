"""GhostWire — Database initialiser (Python 3.13 compatible, no passlib)"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _migrate_vpn_session_is_active(engine):
    """
    One-time migration: vpn_sessions.is_active was historically a String
    ("true"/"false").  It is now a Boolean column.  For SQLite we must
    recreate the column; for Postgres ALTER COLUMN … USING handles it.

    This is idempotent — safe to run on a fresh DB or an already-migrated one.
    """
    from sqlalchemy import text, inspect
    insp = inspect(engine)
    if "vpn_sessions" not in insp.get_table_names():
        return  # table doesn't exist yet — create_all will build it correctly

    cols = {c["name"]: c for c in insp.get_columns("vpn_sessions")}
    if "is_active" not in cols:
        return  # column doesn't exist — create_all will add it

    col_type = str(cols["is_active"]["type"]).upper()
    # If it's already a proper BOOLEAN / INTEGER (SQLite stores bool as INTEGER) we're done
    if "BOOL" in col_type or col_type in ("INTEGER", "INT"):
        return

    # It's VARCHAR/TEXT — needs migration
    db_url = str(engine.url)
    print("[DB] Migrating vpn_sessions.is_active from String → Boolean ...")

    with engine.begin() as conn:
        if db_url.startswith("postgresql"):
            conn.execute(text(
                "ALTER TABLE vpn_sessions "
                "ALTER COLUMN is_active TYPE BOOLEAN "
                "USING (is_active = 'true')"
            ))
        else:
            # SQLite: rename → recreate → copy → drop old
            conn.execute(text(
                "ALTER TABLE vpn_sessions RENAME COLUMN is_active TO is_active_old"
            ))
            conn.execute(text(
                "ALTER TABLE vpn_sessions ADD COLUMN is_active BOOLEAN DEFAULT 1"
            ))
            conn.execute(text(
                "UPDATE vpn_sessions SET is_active = (is_active_old = 'true')"
            ))
            # SQLite doesn't support DROP COLUMN before 3.35; leave the old column
            # harmless if the SQLite version is older — the ORM ignores unknown cols.
            try:
                conn.execute(text(
                    "ALTER TABLE vpn_sessions DROP COLUMN is_active_old"
                ))
            except Exception:
                pass  # pre-3.35 SQLite — old column stays but is ignored by ORM

    print("[DB] vpn_sessions.is_active migration complete")



def init(env_file: str, admin_user: str, admin_pass: str):
    from dotenv import load_dotenv
    load_dotenv(env_file)

    from app.infrastructure.db import engine, Base

    # ── Import ALL domain models so Base.metadata registers every table ────────
    # Previously this block used the wrong paths (app.models.*) which do not
    # exist — the project uses the domain-based layout (app.domains.*).
    # Importing only 3 models also meant 7 tables were silently never created.
    import app.domains.users.models        # noqa: F401 — User, UserAPIKey
    import app.domains.vpn.models          # noqa: F401 — VPNSession
    import app.domains.audit.models        # noqa: F401 — AuditLog
    import app.domains.customfields.models # noqa: F401 — CustomFieldSchema
    import app.domains.dns.models          # noqa: F401 — DnsEvent, BlocklistSource, UserDnsSettings, DnsOverride
    import app.domains.analytics.models    # noqa: F401 — DailySummary
    import app.domains.nodes.models        # noqa: F401 — ServerNode, NodeHealthLog
    import app.domains.bots.models         # noqa: F401 — BotConfig, BotMessage
    import app.domains.plugins.models      # noqa: F401 — Plugin
    import app.domains.themes.models       # noqa: F401 — Theme

    # Pull the actual model class needed for admin seeding
    from app.domains.users.models import User

    from sqlalchemy.orm import Session
    import bcrypt

    print("[DB] Checking schema migrations...")
    _migrate_vpn_session_is_active(engine)
    print("[DB] Creating tables...")
    Base.metadata.create_all(bind=engine)

    hashed = bcrypt.hashpw(admin_pass.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    with Session(engine) as db:
        existing = db.query(User).filter(User.username == admin_user).first()
        if not existing:
            admin = User(
                username=admin_user,
                hashed_password=hashed,
                email="admin@ghostwire.local",
                is_admin=True,
                is_active=True,
                full_name="Administrator",
                vpn_enabled=False,
            )
            db.add(admin)
            db.commit()
            print(f"[DB] Admin user '{admin_user}' created")
        else:
            # Update password hash in case of reinstall
            existing.hashed_password = hashed
            db.commit()
            print(f"[DB] Admin user '{admin_user}' already exists — password updated")

    print("[DB] Database ready")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--env-file",    required=True)
    p.add_argument("--admin-user",  required=True)
    p.add_argument("--admin-pass",  required=True)
    a = p.parse_args()
    init(a.env_file, a.admin_user, a.admin_pass)

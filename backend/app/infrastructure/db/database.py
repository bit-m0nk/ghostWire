"""GhostWire — SQLAlchemy database setup
Abstraction layer that supports SQLite (default, zero-config, runs on Pi)
and PostgreSQL (optional, for multi-server setups — Phase 4).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

# connect_args is SQLite-specific; Postgres doesn't need it
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session, always closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

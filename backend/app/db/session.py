"""SQLAlchemy engine and request-scoped session dependency."""

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = BACKEND_ROOT / "data" / "carbonguard.db"
load_dotenv(BACKEND_ROOT / ".env", override=False)


def get_database_url() -> str:
    """Return the configured URL or a predictable backend-local SQLite URL."""
    return os.getenv(
        "DATABASE_URL",
        f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}",
    )


DATABASE_URL = get_database_url()
_database_url = make_url(DATABASE_URL)

if _database_url.get_backend_name() == "sqlite" and _database_url.database not in {
    None,
    "",
    ":memory:",
}:
    Path(_database_url.database).expanduser().resolve().parent.mkdir(
        parents=True, exist_ok=True
    )

connect_args = (
    {"check_same_thread": False}
    if _database_url.get_backend_name() == "sqlite"
    else {}
)
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

if _database_url.get_backend_name() == "sqlite":

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(connection: Any, _record: Any) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

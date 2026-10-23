"""
Database setup and session management for HostCart using SQLModel and SQLite.
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator, Optional, Union

from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from fastapi import Depends

from src.core.config import get_settings


_engine: Optional[Engine] = None


def get_engine(
    db_path: Optional[Union[str, Path]] = None,
    echo: bool = False,
) -> Engine:
    """
    Get or create a SQLAlchemy/SQLModel Engine.
    If db_path is None, the path from configuration is used and the engine is cached.
    Supports SQLite and PostgreSQL engines.
    """
    global _engine

    if db_path is None and _engine is not None:
        return _engine

    settings = get_settings()

    if isinstance(db_path, Path):
        raw_str = str(db_path)
        for prefix in ("postgresql+psycopg:", "postgresql:", "postgres:"):
            if raw_str.startswith(prefix + "\\") or raw_str.startswith(prefix + "/"):
                raw_path = prefix + "//" + raw_str[len(prefix):].lstrip("\\/").replace("\\", "/")
                break
        else:
            raw_path = raw_str
    elif db_path is not None:
        raw_path = str(db_path)
    else:
        db_file = settings.database.db_file
        if any(db_file.startswith(p) for p in ("postgresql://", "postgresql+psycopg://", "postgres://")):
            raw_path = db_file
        else:
            raw_path = str(settings.database.get_resolved_path())

    is_postgres = any(
        raw_path.startswith(p)
        for p in ("postgresql://", "postgresql+psycopg://", "postgres://")
    )

    if is_postgres:
        if raw_path.startswith("postgres://"):
            db_url = "postgresql+psycopg://" + raw_path[len("postgres://"):]
        elif raw_path.startswith("postgresql://"):
            db_url = "postgresql+psycopg://" + raw_path[len("postgresql://"):]
        else:
            db_url = raw_path

        created_engine = create_engine(
            db_url,
            echo=echo,
            pool_pre_ping=True,
        )
    elif raw_path == ":memory:":
        db_url = "sqlite:///:memory:"
        created_engine = create_engine(
            db_url,
            echo=echo,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        file_path = Path(raw_path).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # SQLite URL on Windows requires forward slashes
        db_url = f"sqlite:///{file_path.as_posix()}"
        created_engine = create_engine(
            db_url,
            echo=echo,
            connect_args={"check_same_thread": False},
        )

    if db_path is None:
        _engine = created_engine

    return created_engine


def get_database_backend(engine: Optional[Engine] = None) -> str:
    """
    Return 'postgresql' if the dialect or URL scheme is PostgreSQL, else 'sqlite'.
    """
    target_engine = engine or get_engine()
    dialect_name = getattr(target_engine.dialect, "name", "").lower()
    if "postgres" in dialect_name:
        return "postgresql"
    url_scheme = str(getattr(target_engine, "url", "")).split("://")[0].lower()
    if "postgres" in url_scheme:
        return "postgresql"
    return "sqlite"


def reset_engine() -> None:
    """Reset and dispose the cached default engine (useful for test isolation)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


def init_db(engine: Optional[Engine] = None) -> None:
    """Create all SQLModel database tables."""
    # Ensure all models are imported so SQLModel.metadata knows about them
    import src.data.models  # noqa: F401

    target_engine = engine or get_engine()
    SQLModel.metadata.create_all(target_engine)


def get_session(
    engine: Optional[Engine] = Depends(lambda: None),
) -> Generator[Session, None, None]:
    """FastAPI dependency for database session generation."""
    target_engine = engine or get_engine()
    with Session(target_engine) as session:
        yield session

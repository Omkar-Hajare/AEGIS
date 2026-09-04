from collections.abc import Generator
from contextlib import contextmanager
import logging
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, settings as default_settings
from database.models import Base

logger = logging.getLogger(__name__)

_engine: sa.Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_database_url(settings: Settings | None = None) -> str:
    """Construct database connection URL from settings."""
    cfg = settings or default_settings
    if cfg.database_url:
        return cfg.database_url

    if cfg.database_password:
        auth = f"{cfg.database_user}:{cfg.database_password}"
    else:
        auth = f"{cfg.database_user}"

    return (
        f"postgresql+psycopg://{auth}@{cfg.database_host}:{cfg.database_port}/{cfg.database_name}"
    )


def get_engine(
    url: str | None = None,
    settings: Settings | None = None,
    echo: bool = False,
    **engine_kwargs: Any,
) -> sa.Engine:
    """Retrieve or create the singleton SQLAlchemy Engine."""
    global _engine
    if _engine is not None and url is None and settings is None:
        return _engine

    target_url = url or get_database_url(settings)

    # SQLite does not support pool_size/max_overflow; only apply pooling args for Postgres/general engines
    kwargs: dict[str, Any] = {"echo": echo}
    if target_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20

    kwargs.update(engine_kwargs)
    engine = sa.create_engine(target_url, **kwargs)

    if url is None and settings is None:
        _engine = engine

    return engine


def get_session_factory(engine: sa.Engine | None = None) -> sessionmaker[Session]:
    """Retrieve or create the session factory."""
    global _session_factory
    eng = engine or get_engine()
    if _session_factory is None or engine is not None:
        factory = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
        if engine is None:
            _session_factory = factory
        return factory
    return _session_factory


@contextmanager
def get_db_session(engine: sa.Engine | None = None) -> Generator[Session, None, None]:
    """Context manager for managed database session lifecycle."""
    factory = get_session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    with get_db_session() as session:
        yield session


def create_tables(engine: sa.Engine | None = None) -> None:
    """Create all defined database tables."""
    eng = engine or get_engine()
    Base.metadata.create_all(bind=eng)


def drop_tables(engine: sa.Engine | None = None) -> None:
    """Drop all defined database tables."""
    eng = engine or get_engine()
    Base.metadata.drop_all(bind=eng)


def reset_engine() -> None:
    """Reset the singleton engine and session factory (useful for tests)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None

# Database engine/session + Postgres URL rewriting (SQLModel/SQLAlchemy)

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlmodel import Session, create_engine

from app.core.config import get_settings

_engine = None


def _postgres_url(url: str) -> str:
    """Rewrite postgres://|postgresql+psycopg2:// variants to SQLAlchemy 2.x psycopg3 DSNs."""
    u = make_url(url)
    if not u.drivername.startswith("postgres"):
        return url
    # render_as_string with mask off — str(url) would LITERALLY inject '***'
    # as the password (SQLAlchemy masks on string render).
    return u.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


def get_engine():
    global _engine
    if _engine is None:
        url = _postgres_url(get_settings().database_url)
        _engine = create_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        )
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _fk_on(dbapi_conn, _record):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()

            @event.listens_for(_engine, "connect")
            def _wal(dbapi_conn, _record):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA busy_timeout=10000")
                cur.close()
    return _engine


def get_session():
    with Session(get_engine()) as session:
        yield session


def create_all() -> None:
    # app.models imports trigger table registration into SQLModel.metadata
    from sqlmodel import SQLModel

    import app.models  # noqa: F401

    SQLModel.metadata.create_all(get_engine())


def reset_database() -> None:
    """Drop + recreate all tables. Test-only helper."""
    from sqlmodel import SQLModel

    import app.models  # noqa: F401

    engine = get_engine()
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

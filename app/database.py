"""Simple SQLAlchemy engine, session dependency, and shared model base."""

import logging
from collections.abc import Generator

from sqlalchemy import Engine, URL, create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import Settings, settings

Base = declarative_base()
logger = logging.getLogger(__name__)

def resolve_database_url():
    return "mysql+pymysql://root:9560@localhost:3306/tiktokdb"

DATABASE_URL = resolve_database_url()
engine: Engine | None = (
    create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800)
    if DATABASE_URL is not None
    else None
)


def get_engine() -> Engine:
    if engine is None:
        raise RuntimeError("MYSQL_PASSWORD is not configured in the backend process environment")
    return engine


def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=get_engine(),
        expire_on_commit=False,
    )


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database_connection() -> bool:
    if engine is None:
        logger.error("Database is not configured: MYSQL_PASSWORD is missing from the backend process environment")
        return False
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            if not inspect(connection).has_table("search_jobs"):
                logger.warning(
                    "Database schema is not ready: table 'search_jobs' is missing; "
                    "run 'python -m alembic upgrade head' from the backend directory"
                )
                return False
        return True
    except SQLAlchemyError as exc:
        logger.error("Database readiness check failed: %s", exc)
        return False

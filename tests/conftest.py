"""Shared fixtures for tests that need a real Postgres+pgvector connection.

These tests require the local dev database (`docker compose up`) to be
running, migrated to head (`alembic upgrade head`). They're skipped
automatically if the database isn't reachable, so the rest of the suite
(pure-function / mocked-Gmail tests) stays runnable without Docker.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from volley.config import DATABASE_URL


def _db_available() -> bool:
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect():
            pass
        engine.dispose()
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_available(), reason="Postgres not reachable at DATABASE_URL — run `docker compose up`"
)


@pytest.fixture
def db_session():
    """A session whose changes are rolled back at the end of the test."""
    engine = create_engine(DATABASE_URL)
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()

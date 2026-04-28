"""
We patch SQLAlchemy to use Text for JSON columns when running in-memory tests.
"""

import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

# SQLite JSON fix — must run BEFORE any models are imported

from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON  # noqa: F401
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    if isinstance(dbapi_conn, sqlite3.Connection):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Patch PostgreSQL JSON type to use SQLite-compatible Text before model import
import sqlalchemy.types as sa_types
_original_JSON = sa_types.JSON

class _SQLiteCompatibleJSON(sa_types.TypeDecorator):
    """Store JSON as text in SQLite; behaves as JSON in PostgreSQL."""
    impl = sa_types.Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            import json
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            import json
            return json.loads(value)
        return value


# In-memory test database


TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    # Patch JSON columns to be Text-based for SQLite compatibility
    import sqlalchemy
    sqlalchemy.JSON = _SQLiteCompatibleJSON

    eng = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Import models after patching
    try:
        from app.db.base import Base  # adjust if your base is elsewhere
        Base.metadata.create_all(eng)
    except Exception as e:
        print(f"Warning: Could not create all tables: {e}")

    yield eng
    eng.dispose()


@pytest.fixture(scope="function")
def db_session(engine):
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

# Model factories

@pytest.fixture
def make_user():
    def _make(id=1, username="test_user", role="user", language="en"):
        user = MagicMock()
        user.id = id
        user.username = username
        user.role = role
        user.language = language
        return user
    return _make


@pytest.fixture
def make_message():
    def _make(id=1, user_id=1, role="user", content="I feel fine today.",
              risk_level="low", risk_score=1, created_at=None):
        msg = MagicMock()
        msg.id = id
        msg.user_id = user_id
        msg.role = role
        msg.content = content
        msg.risk_level = risk_level
        msg.risk_score = risk_score
        msg.created_at = created_at or datetime.utcnow()
        return msg
    return _make


@pytest.fixture
def make_checkin():
    def _make(id=1, user_id=1, checkin_date=None, mood_rating=4,
              sleep_quality=3, meals_eaten=2, drank_enough_water=True,
              took_medication=True, message_count=5):
        checkin = MagicMock()
        checkin.id = id
        checkin.user_id = user_id
        checkin.checkin_date = checkin_date or date.today()
        checkin.mood_rating = mood_rating
        checkin.sleep_quality = sleep_quality
        checkin.meals_eaten = meals_eaten
        checkin.drank_enough_water = drank_enough_water
        checkin.took_medication = took_medication
        checkin.message_count = message_count
        return checkin
    return _make

# FastAPI test client


@pytest.fixture(scope="session")
def client():
    from app.main import app
    return app

# Auth helpers

@pytest.fixture
def auth_headers():
    import jwt, os
    secret = os.getenv("SECRET_KEY", "test-secret-key-32-chars-minimum!!")
    token = jwt.encode(
        {"sub": "1", "username": "test_user", "role": "user"},
        secret, algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


# OpenAI mock — prevents any real API calls


@pytest.fixture(autouse=True)
def mock_openai():
    try:
        with patch("app.integrations.openai_client.client") as mock_client:
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "I'm doing well, thank you."
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            mock_audio = MagicMock()
            mock_audio.content = b"fake-audio-bytes"
            mock_client.audio.speech.create = AsyncMock(return_value=mock_audio)

            mock_transcription = MagicMock()
            mock_transcription.text = "I feel good today."
            mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_transcription)

            yield mock_client
    except Exception:
        yield MagicMock()
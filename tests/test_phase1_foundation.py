"""
Phase 1 Foundation Test Suite for HostCart.
Tests configuration management, security primitives, database layer, and SQLModel data models.
"""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from src.core.config import (
    PROJECT_ROOT,
    ConfigStore,
    DatabaseConfig,
    Settings,
    get_config_store,
    get_settings,
    reset_config_store,
)
from src.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from src.data.database import get_engine, get_session, init_db, reset_engine
from src.data.models import (
    MediaItem,
    MediaType,
    TrackingStatus,
    User,
    UserMediaEntry,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture(autouse=True)
def clean_config_and_db_state(monkeypatch, tmp_path):
    """Reset singletons and isolate from developer's local .env between tests."""
    reset_config_store()
    reset_engine()

    # Isolate from local .env if present
    monkeypatch.setattr("src.core.config.DEFAULT_ENV_PATH", tmp_path / ".empty_test_env")

    keys_to_clean = [
        "SECRET_KEY",
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "SERVER_HOST",
        "HOST",
        "SERVER_PORT",
        "PORT",
        "DATABASE_URL",
        "DB_FILE",
        "IGDB_CLIENT_ID",
        "IGDB_CLIENT_SECRET",
        "TMDB_API_KEY",
        "GOOGLE_BOOKS_API_KEY",
    ]
    old_env = {}
    for k in keys_to_clean:
        if k in os.environ:
            old_env[k] = os.environ.pop(k)

    yield

    reset_config_store()
    reset_engine()
    for k in keys_to_clean:
        if k in os.environ:
            os.environ.pop(k)
    for k, v in old_env.items():
        os.environ[k] = v


@pytest.fixture
def memory_db_session():
    """Create an isolated in-memory SQLite database session."""
    engine = get_engine(":memory:")
    init_db(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


# =====================================================================
# 1. Configuration Tests
# =====================================================================

def test_config_defaults_and_root_resolution():
    """Test default settings instantiation and path safety."""
    settings = get_settings()
    assert settings.server.port == 8000
    assert settings.server.host == "0.0.0.0"
    assert settings.security.algorithm == "HS256"
    assert settings.providers.igdb.client_id == ""
    assert settings.providers.tmdb.api_key == ""
    assert settings.providers.books.openlibrary_enabled is True
    assert PROJECT_ROOT.exists()


def test_database_config_path_resolution(tmp_path):
    """Test resolution of relative, absolute, sqlite prefix, and in-memory DB paths."""
    # Memory
    db_mem = DatabaseConfig(db_file=":memory:")
    assert db_mem.get_resolved_path() == Path(":memory:")

    # Absolute path
    abs_file = (tmp_path / "custom.db").resolve()
    db_abs = DatabaseConfig(db_file=str(abs_file))
    assert db_abs.get_resolved_path() == abs_file

    # Relative path with custom root
    db_rel = DatabaseConfig(db_file="data/test.db")
    resolved = db_rel.get_resolved_path(root=tmp_path)
    assert resolved == (tmp_path / "data" / "test.db").resolve()

    # With sqlite:/// prefix
    db_prefix = DatabaseConfig(db_file=f"sqlite:///{abs_file.as_posix()}")
    assert db_prefix.get_resolved_path() == abs_file


def test_config_store_load_json_and_save(tmp_path):
    """Test loading, modifying, and saving config to custom JSON path."""
    cfg_file = tmp_path / "config.json"
    initial_content = {
        "server": {"port": 9000, "host": "127.0.0.1"},
        "providers": {"igdb": {"client_id": "test_id", "client_secret": "test_sec"}},
    }
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(initial_content, f)

    store = ConfigStore(config_path=cfg_file, env_file=tmp_path / ".env.none")
    settings = store.get_settings()
    assert settings.server.port == 9000
    assert settings.server.host == "127.0.0.1"
    assert settings.providers.igdb.client_id == "test_id"

    # Update and save
    updated = store.update_config(
        {"server": {"port": 9500}, "providers": {"tmdb": {"api_key": "new_tmdb"}}},
        save=True,
    )
    assert updated.server.port == 9500
    assert updated.providers.tmdb.api_key == "new_tmdb"

    # Reload from disk
    reloaded_store = ConfigStore(config_path=cfg_file, env_file=tmp_path / ".env.none")
    assert reloaded_store.get_settings().server.port == 9500
    assert reloaded_store.get_settings().providers.tmdb.api_key == "new_tmdb"


def test_config_store_invalid_json_handling(tmp_path):
    """Test that malformed JSON raises a descriptive RuntimeError."""
    cfg_file = tmp_path / "invalid.json"
    with open(cfg_file, "w", encoding="utf-8") as f:
        f.write("{ invalid json // here")

    with pytest.raises(RuntimeError) as exc_info:
        ConfigStore(config_path=cfg_file)
    assert "Failed to parse config file" in str(exc_info.value)


def test_config_store_missing_file_falls_back_to_defaults(tmp_path):
    """Test that if config file doesn't exist, valid defaults are provided."""
    cfg_file = tmp_path / "missing.json"
    store = ConfigStore(config_path=cfg_file, env_file=tmp_path / ".env.none")
    settings = store.get_settings()
    assert settings.server.port == 8000
    assert settings.security.secret_key != ""


def test_config_store_env_var_and_dotenv_overrides(tmp_path):
    """Test overriding configuration settings via .env file and environment variables."""
    dotenv_file = tmp_path / ".env"
    with open(dotenv_file, "w", encoding="utf-8") as f:
        f.write("SECRET_KEY=dotenv_secret\n")
        f.write("SERVER_HOST=10.0.0.5\n")
        f.write("PORT=8080\n")
        f.write("IGDB_CLIENT_ID=igdb_from_env\n")
        f.write("ACCESS_TOKEN_EXPIRE_MINUTES=60\n")

    # System environment should take precedence over .env
    os.environ["SECRET_KEY"] = "system_env_secret"
    os.environ["TMDB_API_KEY"] = "tmdb_system_key"
    os.environ["GOOGLE_BOOKS_API_KEY"] = "books_system_key"
    os.environ["DATABASE_URL"] = "data/custom_url.db"

    store = ConfigStore(
        config_path=tmp_path / "missing.json",
        env_file=dotenv_file,
    )
    settings = store.get_settings()

    # Precedence: system env overrides dotenv
    assert settings.security.secret_key == "system_env_secret"
    # Dotenv values applied when not in system env
    assert settings.server.host == "10.0.0.5"
    assert settings.server.port == 8080
    assert settings.security.access_token_expire_minutes == 60
    assert settings.providers.igdb.client_id == "igdb_from_env"
    # System env only
    assert settings.providers.tmdb.api_key == "tmdb_system_key"
    assert settings.providers.books.google_books_api_key == "books_system_key"
    assert settings.database.db_file == "data/custom_url.db"


def test_config_store_invalid_port_and_minutes_env_vars(tmp_path):
    """Test that invalid integer strings in environment variables do not crash config load."""
    os.environ["SERVER_PORT"] = "not_an_int"
    os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "invalid_number"
    os.environ["HOST"] = "192.168.1.1"
    os.environ["DB_FILE"] = "data/from_db_file.db"
    os.environ["IGDB_CLIENT_SECRET"] = "secret_from_env"

    store = ConfigStore(config_path=tmp_path / "missing.json", env_file=None)
    settings = store.get_settings()
    assert settings.server.port == 8000  # Default preserved
    assert settings.security.access_token_expire_minutes == 1440  # Default preserved
    assert settings.server.host == "192.168.1.1"
    assert settings.database.db_file == "data/from_db_file.db"
    assert settings.providers.igdb.client_secret == "secret_from_env"

    # Also test PORT with invalid integer
    os.environ.pop("SERVER_PORT")
    os.environ["PORT"] = "invalid_port"
    store2 = ConfigStore(config_path=tmp_path / "missing.json", env_file=None)
    assert store2.get_settings().server.port == 8000

    # Test load_now=False lazy load
    store3 = ConfigStore(config_path=tmp_path / "missing.json", env_file=None, load_now=False)
    assert store3._settings is None
    loaded_settings = store3.get_settings()
    assert loaded_settings is not None


def test_global_config_store_singleton():
    """Test get_config_store singleton behavior and force reload."""
    s1 = get_config_store()
    s2 = get_config_store()
    assert s1 is s2

    s3 = get_config_store(force_reload=True)
    assert s3 is not None


# =====================================================================
# 2. Security Primitives Tests
# =====================================================================

def test_password_hashing_and_verification():
    """Test password hashing, verification, wrong password, and invalid input."""
    plain = "ArcadiaCurator#2026"
    hashed = hash_password(plain)

    assert hashed != plain
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    # Correct password
    assert verify_password(plain, hashed) is True

    # Incorrect password
    assert verify_password("WrongPassword123", hashed) is False

    # Empty inputs
    assert verify_password("", hashed) is False
    assert verify_password(plain, "") is False

    # Malformed hash string
    assert verify_password(plain, "not_a_bcrypt_hash") is False


def test_jwt_create_and_decode_valid():
    """Test creating and decoding a standard JWT token."""
    data = {"sub": "user_123", "role": "admin"}
    token = create_access_token(data)

    assert isinstance(token, str)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user_123"
    assert decoded["role"] == "admin"
    assert "exp" in decoded
    assert "iat" in decoded


def test_jwt_expiration():
    """Test that expired JWT tokens return None upon decoding."""
    data = {"sub": "user_expired"}
    # Token expired 10 seconds ago
    expired_token = create_access_token(
        data, expires_delta=timedelta(seconds=-10)
    )
    assert decode_access_token(expired_token) is None


def test_jwt_invalid_or_tampered_token():
    """Test that invalid, tampered, or mismatched secret tokens decode to None."""
    data = {"sub": "user_456"}
    token = create_access_token(data)

    # Empty / None
    assert decode_access_token("") is None

    # Corrupted token
    corrupted_token = token[:-5] + "XXXXX"
    assert decode_access_token(corrupted_token) is None

    # Completely bogus string
    assert decode_access_token("this.is.not.a.valid.jwt") is None

    # Decode with different secret key
    assert (
        decode_access_token(token, secret_key="completely_different_secret_key_32bytes!")
        is None
    )

    # Unexpected exception handling in decode
    import unittest.mock as mock
    with mock.patch("jwt.decode", side_effect=RuntimeError("unexpected")):
        assert decode_access_token(token) is None


# =====================================================================
# 3. Database Layer Tests
# =====================================================================

def test_engine_creation_and_caching(tmp_path):
    """Test get_engine with memory, file paths, and default singleton caching."""
    # In-memory
    mem_engine = get_engine(":memory:")
    assert mem_engine is not None

    # File based creates directory
    file_target = tmp_path / "subfolder" / "test.db"
    file_engine = get_engine(file_target)
    assert file_target.parent.exists()
    assert file_engine is not None

    # Default cached engine
    default_1 = get_engine(None)
    default_2 = get_engine(None)
    assert default_1 is default_2

    reset_engine()
    default_3 = get_engine(None)
    assert default_3 is not None
    mem_engine.dispose()
    file_engine.dispose()
    default_3.dispose()


def test_database_session_generator():
    """Test FastAPI get_session generator dependency."""
    engine = get_engine(":memory:")
    init_db(engine)

    gen = get_session(engine)
    session = next(gen)
    assert isinstance(session, Session)

    # Add a user to verify active session
    u = User(
        username="session_test",
        email="session@hostcart.local",
        hashed_password="pw",
    )
    session.add(u)
    session.commit()
    assert u.id is not None

    # Complete the generator
    with pytest.raises(StopIteration):
        next(gen)
    engine.dispose()


# =====================================================================
# 4. SQLModel Data Models CRUD Tests
# =====================================================================

def test_user_crud_and_unique_constraints(memory_db_session):
    """Test User model creation, querying, updating, and unique constraints."""
    session = memory_db_session

    user = User(
        username="arcadia_king",
        email="king@arcadia.local",
        hashed_password=hash_password("password123"),
        is_admin=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    assert user.id is not None
    assert user.username == "arcadia_king"
    assert user.is_admin is True
    assert isinstance(user.created_at, datetime)

    # Retrieve by username
    found = session.exec(select(User).where(User.username == "arcadia_king")).first()
    assert found is not None
    assert found.email == "king@arcadia.local"

    # Unique username violation
    duplicate_user = User(
        username="arcadia_king",
        email="other@arcadia.local",
        hashed_password="pw",
    )
    session.add(duplicate_user)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    # Unique email violation
    duplicate_email = User(
        username="unique_username",
        email="king@arcadia.local",
        hashed_password="pw",
    )
    session.add(duplicate_email)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_media_item_crud_all_media_types(memory_db_session):
    """Test MediaItem creation across GAME, MOVIE, TV_SHOW, and BOOK."""
    session = memory_db_session

    # 1. Game
    game = MediaItem(
        media_type=MediaType.GAME,
        title="Cyberpunk 2077",
        original_title="Cyberpunk 2077",
        release_year=2020,
        genres=["Action RPG", "Cyberpunk", "Open World"],
        creators=["CD Projekt Red"],
        external_id="igdb_1877",
        external_source="igdb",
        summary="An open-world, action-adventure story set in Night City.",
    )

    # 2. Movie
    movie = MediaItem(
        media_type=MediaType.MOVIE,
        title="Blade Runner 2049",
        release_year=2017,
        runtime_minutes=164,
        genres=["Sci-Fi", "Neo-Noir"],
        creators=["Denis Villeneuve"],
        external_id="tmdb_335984",
        external_source="tmdb",
        poster_url="https://image.tmdb.org/t/p/w500/poster.jpg",
        backdrop_url="https://image.tmdb.org/t/p/w1280/backdrop.jpg",
    )

    # 3. TV Show
    tv = MediaItem(
        media_type=MediaType.TV_SHOW,
        title="Arcane",
        release_year=2021,
        total_episodes=18,
        genres=["Animation", "Action", "Sci-Fi"],
        creators=["Christian Linke", "Alex Yee"],
        external_id="tmdb_94605",
        external_source="tmdb",
    )

    # 4. Book
    book = MediaItem(
        media_type=MediaType.BOOK,
        title="Neuromancer",
        release_year=1984,
        total_pages=271,
        genres=["Cyberpunk", "Sci-Fi"],
        creators=["William Gibson"],
        external_id="OL27479W",
        external_source="openlibrary",
    )

    session.add_all([game, movie, tv, book])
    session.commit()

    # Query items and verify JSON list persistence
    items = session.exec(select(MediaItem)).all()
    assert len(items) == 4

    retrieved_game = session.exec(
        select(MediaItem).where(MediaItem.media_type == MediaType.GAME)
    ).first()
    assert retrieved_game.title == "Cyberpunk 2077"
    assert "Open World" in retrieved_game.genres
    assert "CD Projekt Red" in retrieved_game.creators

    retrieved_movie = session.exec(
        select(MediaItem).where(MediaItem.media_type == MediaType.MOVIE)
    ).first()
    assert retrieved_movie.runtime_minutes == 164

    retrieved_tv = session.exec(
        select(MediaItem).where(MediaItem.media_type == MediaType.TV_SHOW)
    ).first()
    assert retrieved_tv.total_episodes == 18

    retrieved_book = session.exec(
        select(MediaItem).where(MediaItem.media_type == MediaType.BOOK)
    ).first()
    assert retrieved_book.total_pages == 271


def test_user_media_entry_crud_and_tracking_statuses(memory_db_session):
    """Test UserMediaEntry CRUD, tracking statuses, rating, playtime, and JSON tags."""
    session = memory_db_session

    user = User(
        username="collector",
        email="collector@hostcart.local",
        hashed_password="pw",
    )
    game = MediaItem(
        media_type=MediaType.GAME,
        title="Persona 5 Royal",
        release_year=2019,
        genres=["JRPG"],
    )
    session.add_all([user, game])
    session.commit()

    # Create entry with PLAN_TO
    entry = UserMediaEntry(
        user_id=user.id,
        media_item_id=game.id,
        status=TrackingStatus.PLAN_TO,
        rating=None,
        is_favorite=False,
        tags=["atlus", "turn-based"],
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)

    assert entry.id is not None
    assert entry.status == TrackingStatus.PLAN_TO
    assert entry.playtime_hours == 0.0
    assert entry.tags == ["atlus", "turn-based"]

    # Transition to IN_PROGRESS
    entry.status = TrackingStatus.IN_PROGRESS
    entry.playtime_hours = 35.5
    entry.started_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(entry)
    assert entry.status == TrackingStatus.IN_PROGRESS
    assert entry.playtime_hours == 35.5

    # Transition to COMPLETED
    entry.status = TrackingStatus.COMPLETED
    entry.playtime_hours = 120.0
    entry.rating = 10.0
    entry.is_favorite = True
    entry.notes = "Unbelievable soundtrack and style."
    entry.completed_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(entry)
    assert entry.status == TrackingStatus.COMPLETED
    assert entry.rating == 10.0
    assert entry.is_favorite is True

    # Test other TrackingStatus enum states
    for status in [
        TrackingStatus.ON_HOLD,
        TrackingStatus.DROPPED,
        TrackingStatus.WISHLIST,
    ]:
        entry.status = status
        session.commit()
        session.refresh(entry)
        assert entry.status == status


def test_relationships_and_cascade_deletion(memory_db_session):
    """Test relationship navigation and cascade delete when User or MediaItem is deleted."""
    session = memory_db_session

    user = User(
        username="cascade_user",
        email="cascade@hostcart.local",
        hashed_password="pw",
    )
    item = MediaItem(
        media_type=MediaType.BOOK,
        title="Dune",
        genres=["Sci-Fi"],
    )
    session.add_all([user, item])
    session.commit()

    entry = UserMediaEntry(
        user_id=user.id,
        media_item_id=item.id,
        status=TrackingStatus.IN_PROGRESS,
        current_page=150,
    )
    session.add(entry)
    session.commit()

    # Relationship navigation
    session.refresh(user)
    session.refresh(item)
    assert len(user.entries) == 1
    assert user.entries[0].media_item.title == "Dune"
    assert item.entries[0].user.username == "cascade_user"

    # Cascade delete when user is deleted
    session.delete(user)
    session.commit()

    remaining_entries = session.exec(select(UserMediaEntry)).all()
    assert len(remaining_entries) == 0

    # MediaItem still exists
    remaining_item = session.get(MediaItem, item.id)
    assert remaining_item is not None

"""
Comprehensive unit and integration tests for Sub-Phase 3.3:
Inter-Service Homelab Endpoints (/api/v1/homelab/*) and AI Media Assistant (/api/v1/ai/recommend).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from src.core.config import (
    ConfigStore,
    HomelabConfig,
    Settings,
    get_config_store,
    get_settings,
    reset_config_store,
)
from src.core.security import create_access_token, hash_password
from src.data.database import (
    get_database_backend,
    get_engine,
    get_session,
    init_db,
    reset_engine,
)
from src.data.models import MediaItem, MediaType, TrackingStatus, User, UserMediaEntry
from src.main import app

CLEAN_ENV_KEYS = [
    "DEPLOYMENT_MODE",
    "AUTH_MODE",
    "HOMELAB_SSO_SECRET",
    "HOMELAB_INTERNAL_TOKEN",
    "AI_BASE_URL",
    "AI_API_KEY",
    "OPENROUTER_API_KEY",
    "AI_MODEL",
    "DATABASE_URL",
    "DB_FILE",
    "SECRET_KEY",
]

TEST_SSO_SECRET = "test-homelab-sso-secret-32bytes-key-1234"
TEST_INTERNAL_TOKEN = "test-homelab-internal-token-32bytes-secret"


@pytest.fixture(autouse=True)
def clean_env_fixture(monkeypatch, tmp_path):
    """Ensure clean environment and reset configuration/engine before and after each test."""
    reset_config_store()
    reset_engine()

    monkeypatch.setattr("src.core.config.DEFAULT_ENV_PATH", tmp_path / ".empty_env")

    saved = {}
    for k in CLEAN_ENV_KEYS:
        if k in os.environ:
            saved[k] = os.environ.pop(k)

    yield

    reset_config_store()
    reset_engine()

    for k in CLEAN_ENV_KEYS:
        if k in os.environ:
            os.environ.pop(k)
    for k, v in saved.items():
        os.environ[k] = v


@pytest.fixture(name="db_session")
def db_session_fixture() -> Generator[Session, None, None]:
    """Provide an isolated in-memory SQLite database session."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(test_engine)
    with Session(test_engine) as session:
        yield session
    test_engine.dispose()


@pytest.fixture(name="client")
def client_fixture(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a TestClient with database session overridden."""
    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_test_user(db_session: Session, username: str = "alice", is_admin: bool = False) -> User:
    """Create a verified local User in the test database."""
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=hash_password("Password123!"),
        is_admin=is_admin,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def auth_headers_for(user: User) -> dict:
    """Generate Authorization Bearer headers for a local User."""
    token = create_access_token({"sub": str(user.id), "username": user.username})
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# 1. Homelab Health Endpoint Tests
# =====================================================================

def test_homelab_health_default_standalone(client):
    """Verify /api/v1/homelab/health in standalone mode."""
    res = client.get("/api/v1/homelab/health")
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "hostcart"
    assert data["status"] == "ok"
    assert data["deployment_mode"] == "standalone"
    assert data["auth_mode"] == "standalone"
    assert data["database_backend"] == "sqlite"
    assert data["version"] == "1.0.0"


def test_homelab_health_homelab_mode(client, monkeypatch):
    """Verify /api/v1/homelab/health reflects homelab mode environment settings."""
    os.environ["DEPLOYMENT_MODE"] = "homelab"
    os.environ["AUTH_MODE"] = "homelab"
    reset_config_store()

    res = client.get("/api/v1/homelab/health")
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "hostcart"
    assert data["status"] == "ok"
    assert data["deployment_mode"] == "homelab"
    assert data["auth_mode"] == "homelab"
    assert data["database_backend"] == "sqlite"


# =====================================================================
# 2. Homelab Summary Endpoint Tests
# =====================================================================

def test_homelab_summary_requires_authentication(client):
    """Verify /api/v1/homelab/summary returns 401 when unauthenticated."""
    res = client.get("/api/v1/homelab/summary")
    assert res.status_code == 401


def test_homelab_summary_empty_collection(client, db_session):
    """Verify /api/v1/homelab/summary for a user with no tracked items."""
    user = make_test_user(db_session, "empty_user")
    headers = auth_headers_for(user)

    res = client.get("/api/v1/homelab/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "hostcart"
    assert data["username"] == "empty_user"
    assert data["stats"]["total_items"] == 0
    assert data["stats"]["in_progress"] == 0
    assert data["stats"]["completed"] == 0
    assert data["stats"]["plan_to"] == 0
    assert data["stats"]["recent_activity"] == []


def test_homelab_summary_populated_collection(client, db_session):
    """Verify /api/v1/homelab/summary calculates correct stats and progress strings."""
    user = make_test_user(db_session, "gamer_bob")
    headers = auth_headers_for(user)

    # 1. Game (in_progress)
    game = MediaItem(title="Elden Ring", media_type=MediaType.GAME)
    db_session.add(game)
    db_session.commit()
    entry_game = UserMediaEntry(
        user_id=user.id,
        media_item_id=game.id,
        status=TrackingStatus.IN_PROGRESS,
        playtime_hours=45.0,
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=4),
    )
    db_session.add(entry_game)

    # 2. TV Show with total_episodes (in_progress)
    tv1 = MediaItem(title="Severance", media_type=MediaType.TV_SHOW, total_episodes=9)
    db_session.add(tv1)
    db_session.commit()
    entry_tv1 = UserMediaEntry(
        user_id=user.id,
        media_item_id=tv1.id,
        status=TrackingStatus.IN_PROGRESS,
        current_episode=5,
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=3),
    )
    db_session.add(entry_tv1)

    # 3. TV Show without total_episodes (in_progress)
    tv2 = MediaItem(title="One Piece", media_type=MediaType.TV_SHOW, total_episodes=None)
    db_session.add(tv2)
    db_session.commit()
    entry_tv2 = UserMediaEntry(
        user_id=user.id,
        media_item_id=tv2.id,
        status=TrackingStatus.IN_PROGRESS,
        current_episode=1100,
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=2),
    )
    db_session.add(entry_tv2)

    # 4. Book with total_pages (completed)
    book1 = MediaItem(title="Dune", media_type=MediaType.BOOK, total_pages=300)
    db_session.add(book1)
    db_session.commit()
    entry_book1 = UserMediaEntry(
        user_id=user.id,
        media_item_id=book1.id,
        status=TrackingStatus.COMPLETED,
        current_page=300,
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(entry_book1)

    # 5. Book without total_pages (in_progress)
    book2 = MediaItem(title="Novel", media_type=MediaType.BOOK, total_pages=None)
    db_session.add(book2)
    db_session.commit()
    entry_book2 = UserMediaEntry(
        user_id=user.id,
        media_item_id=book2.id,
        status=TrackingStatus.IN_PROGRESS,
        current_page=75,
        updated_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )
    db_session.add(entry_book2)

    # 6. Movie (plan_to)
    movie1 = MediaItem(title="Interstellar", media_type=MediaType.MOVIE)
    db_session.add(movie1)
    db_session.commit()
    entry_movie1 = UserMediaEntry(
        user_id=user.id,
        media_item_id=movie1.id,
        status=TrackingStatus.PLAN_TO,
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(entry_movie1)

    db_session.commit()

    res = client.get("/api/v1/homelab/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "hostcart"
    assert data["username"] == "gamer_bob"

    stats = data["stats"]
    assert stats["total_items"] == 6
    assert stats["in_progress"] == 4
    assert stats["completed"] == 1
    assert stats["plan_to"] == 1

    # Recent activity returns up to 5 most recently updated
    recent = stats["recent_activity"]
    assert len(recent) == 5

    # Check top entry is Interstellar (plan_to -> "Plan to")
    assert recent[0]["title"] == "Interstellar"
    assert recent[0]["media_type"] == "movie"
    assert recent[0]["status"] == "plan_to"
    assert recent[0]["progress"] == "Plan to"

    # Check Novel (p. 75)
    assert recent[1]["title"] == "Novel"
    assert recent[1]["progress"] == "p. 75"

    # Check Dune (p. 300/300)
    assert recent[2]["title"] == "Dune"
    assert recent[2]["progress"] == "p. 300/300"

    # Check One Piece (Ep 1100)
    assert recent[3]["title"] == "One Piece"
    assert recent[3]["progress"] == "Ep 1100"

    # Check Severance (Ep 5/9)
    assert recent[4]["title"] == "Severance"
    assert recent[4]["progress"] == "Ep 5/9"


def test_homelab_summary_movie_status_formatting(client, db_session):
    """Verify movie progress formatting for completed and in_progress states."""
    user = make_test_user(db_session, "cinephile")
    headers = auth_headers_for(user)

    m1 = MediaItem(title="Inception", media_type=MediaType.MOVIE)
    m2 = MediaItem(title="Avatar", media_type=MediaType.MOVIE)
    db_session.add_all([m1, m2])
    db_session.commit()

    db_session.add(UserMediaEntry(user_id=user.id, media_item_id=m1.id, status=TrackingStatus.COMPLETED))
    db_session.add(UserMediaEntry(user_id=user.id, media_item_id=m2.id, status=TrackingStatus.IN_PROGRESS))
    db_session.commit()

    res = client.get("/api/v1/homelab/summary", headers=headers)
    assert res.status_code == 200
    recent = res.json()["stats"]["recent_activity"]
    progress_map = {item["title"]: item["progress"] for item in recent}
    assert progress_map["Inception"] == "Completed"
    assert progress_map["Avatar"] == "In progress"


# =====================================================================
# 3. Homelab Tools Discovery Tests
# =====================================================================

def test_homelab_tools_discovery(client):
    """Verify /api/v1/homelab/tools returns valid function definitions."""
    res = client.get("/api/v1/homelab/tools")
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "hostcart"
    assert "tools" in data

    tool_names = [t["name"] for t in data["tools"]]
    assert "hostcart_get_user_collection" in tool_names
    assert "hostcart_update_progress" in tool_names

    # Check properties
    progress_tool = next(t for t in data["tools"] if t["name"] == "hostcart_update_progress")
    assert "required" in progress_tool["parameters"]
    assert "title" in progress_tool["parameters"]["required"]
    assert "action" in progress_tool["parameters"]["required"]


# =====================================================================
# 4. Homelab Tools Execute Tests
# =====================================================================

def test_homelab_tools_execute_requires_auth(client):
    """Verify /api/v1/homelab/tools/execute requires authentication."""
    res = client.post("/api/v1/homelab/tools/execute", json={"tool_name": "foo", "arguments": {}})
    assert res.status_code == 401


def test_homelab_tools_execute_unknown_tool(client, db_session):
    """Verify unknown tool returns ok=False error message."""
    user = make_test_user(db_session, "charlie")
    headers = auth_headers_for(user)

    res = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={"tool_name": "unknown_tool", "arguments": {}},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is False
    assert "Unknown tool 'unknown_tool'" in data["error"]


def test_homelab_tools_execute_get_collection(client, db_session):
    """Verify hostcart_get_user_collection tool with filtering and search."""
    user = make_test_user(db_session, "dana")
    headers = auth_headers_for(user)

    # Populate collection
    item_game = MediaItem(title="Cyberpunk 2077", media_type=MediaType.GAME)
    item_show = MediaItem(title="Cyberpunk: Edgerunners", media_type=MediaType.TV_SHOW, total_episodes=10)
    item_book = MediaItem(title="Neuromancer", media_type=MediaType.BOOK, total_pages=271)
    db_session.add_all([item_game, item_show, item_book])
    db_session.commit()

    db_session.add(UserMediaEntry(user_id=user.id, media_item_id=item_game.id, status=TrackingStatus.IN_PROGRESS, playtime_hours=60.0))
    db_session.add(UserMediaEntry(user_id=user.id, media_item_id=item_show.id, status=TrackingStatus.COMPLETED, current_episode=10))
    db_session.add(UserMediaEntry(user_id=user.id, media_item_id=item_book.id, status=TrackingStatus.PLAN_TO))
    db_session.commit()

    # Query all
    res = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={"tool_name": "hostcart_get_user_collection", "arguments": {}},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert len(data["result"]) == 3

    # Filter by media_type=game
    res = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={"tool_name": "hostcart_get_user_collection", "arguments": {"media_type": "game"}},
    )
    assert res.status_code == 200
    res_items = res.json()["result"]
    assert len(res_items) == 1
    assert res_items[0]["title"] == "Cyberpunk 2077"
    assert res_items[0]["progress"] == "60.0 hrs"

    # Filter by status=completed
    res = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={"tool_name": "hostcart_get_user_collection", "arguments": {"status": "completed"}},
    )
    assert res.status_code == 200
    res_items = res.json()["result"]
    assert len(res_items) == 1
    assert res_items[0]["title"] == "Cyberpunk: Edgerunners"

    # Search keyword
    res = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={"tool_name": "hostcart_get_user_collection", "arguments": {"search": "cyberpunk"}},
    )
    assert res.status_code == 200
    assert len(res.json()["result"]) == 2


def test_homelab_tools_execute_update_progress_add_to_watchlist(client, db_session):
    """Verify action=add_to_watchlist creates MediaItem and UserMediaEntry."""
    user = make_test_user(db_session, "eve")
    headers = auth_headers_for(user)

    # Add new movie to watchlist
    res = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {
                "title": "The Matrix",
                "media_type": "movie",
                "action": "add_to_watchlist",
            },
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "Added 'The Matrix' to watchlist for user 'eve'." in data["result"]

    # Verify in DB
    item = db_session.exec(select(MediaItem).where(MediaItem.title == "The Matrix")).first()
    assert item is not None
    assert item.media_type == MediaType.MOVIE
    entry = db_session.exec(select(UserMediaEntry).where(UserMediaEntry.media_item_id == item.id)).first()
    assert entry is not None
    assert entry.status == TrackingStatus.PLAN_TO

    # Add again when already present but marked completed -> resets to plan_to
    entry.status = TrackingStatus.COMPLETED
    db_session.add(entry)
    db_session.commit()

    res2 = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {
                "title": "The Matrix",
                "action": "add_to_watchlist",
            },
        },
    )
    assert res2.status_code == 200
    assert res2.json()["ok"] is True
    db_session.refresh(entry)
    assert entry.status == TrackingStatus.PLAN_TO


def test_homelab_tools_execute_update_progress_tv_show(client, db_session):
    """Verify increment_progress for TV Show (partial progress and auto-completion)."""
    user = make_test_user(db_session, "frank")
    headers = auth_headers_for(user)

    # Create TV Show with 10 episodes
    tv = MediaItem(title="Breaking Bad", media_type=MediaType.TV_SHOW, total_episodes=10)
    db_session.add(tv)
    db_session.commit()
    entry = UserMediaEntry(user_id=user.id, media_item_id=tv.id, status=TrackingStatus.IN_PROGRESS, current_episode=7)
    db_session.add(entry)
    db_session.commit()

    # Increment by 1
    res = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {
                "title": "Breaking Bad",
                "action": "increment_progress",
                "amount": 1,
            },
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "episode progress is now 8/10 (in_progress)" in data["result"]

    # Increment by 2 to reach total_episodes (10) -> auto completes
    res2 = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {
                "title": "Breaking Bad",
                "action": "increment_progress",
                "amount": 2,
            },
        },
    )
    assert res2.status_code == 200
    assert "episode progress is now 10/10 (completed)" in res2.json()["result"]
    db_session.refresh(entry)
    assert entry.status == TrackingStatus.COMPLETED


def test_homelab_tools_execute_update_progress_game_and_book(client, db_session):
    """Verify increment_progress for Game playtime and Book pages."""
    user = make_test_user(db_session, "grace")
    headers = auth_headers_for(user)

    game = MediaItem(title="Dark Souls", media_type=MediaType.GAME)
    book = MediaItem(title="The Hobbit", media_type=MediaType.BOOK, total_pages=310)
    db_session.add_all([game, book])
    db_session.commit()

    entry_game = UserMediaEntry(user_id=user.id, media_item_id=game.id, status=TrackingStatus.IN_PROGRESS, playtime_hours=12.5)
    entry_book = UserMediaEntry(user_id=user.id, media_item_id=book.id, status=TrackingStatus.IN_PROGRESS, current_page=150)
    db_session.add_all([entry_game, entry_book])
    db_session.commit()

    # Increment game playtime by 2.5
    res_game = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {
                "title": "Dark Souls",
                "action": "increment_progress",
                "amount": 2.5,
            },
        },
    )
    assert res_game.status_code == 200
    assert "playtime is now 15.0 hours (in_progress)" in res_game.json()["result"]

    # Increment book pages by 160 -> auto completes (310 >= 310)
    res_book = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {
                "title": "The Hobbit",
                "action": "increment_progress",
                "amount": 160,
            },
        },
    )
    assert res_book.status_code == 200
    assert "page progress is now 310/310 (completed)" in res_book.json()["result"]
    db_session.refresh(entry_book)
    assert entry_book.status == TrackingStatus.COMPLETED


def test_homelab_tools_execute_update_progress_movie_and_mark_completed(client, db_session):
    """Verify movie increment and mark_completed action."""
    user = make_test_user(db_session, "heidi")
    headers = auth_headers_for(user)

    movie = MediaItem(title="Pulp Fiction", media_type=MediaType.MOVIE)
    db_session.add(movie)
    db_session.commit()
    entry_movie = UserMediaEntry(user_id=user.id, media_item_id=movie.id, status=TrackingStatus.IN_PROGRESS)
    db_session.add(entry_movie)
    db_session.commit()

    # increment_progress on movie marks it completed
    res = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {
                "title": "Pulp Fiction",
                "action": "increment_progress",
            },
        },
    )
    assert res.status_code == 200
    assert "Marked 'Pulp Fiction' as completed for user 'heidi'." in res.json()["result"]
    db_session.refresh(entry_movie)
    assert entry_movie.status == TrackingStatus.COMPLETED

    # mark_completed action
    entry_movie.status = TrackingStatus.PLAN_TO
    db_session.add(entry_movie)
    db_session.commit()

    res2 = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {
                "title": "Pulp Fiction",
                "action": "mark_completed",
            },
        },
    )
    assert res2.status_code == 200
    assert "Marked 'Pulp Fiction' as completed for user 'heidi'." in res2.json()["result"]
    db_session.refresh(entry_movie)
    assert entry_movie.status == TrackingStatus.COMPLETED


def test_homelab_tools_execute_error_cases(client, db_session):
    """Verify error conditions in update_progress."""
    user = make_test_user(db_session, "ivan")
    headers = auth_headers_for(user)

    # Missing title
    res1 = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {"action": "increment_progress"},
        },
    )
    assert res1.status_code == 200
    assert res1.json()["ok"] is False
    assert "Missing or empty 'title'" in res1.json()["error"]

    # Item not found for increment
    res2 = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {"title": "NonExistentShow", "action": "increment_progress"},
        },
    )
    assert res2.status_code == 200
    assert res2.json()["ok"] is False
    assert "Item 'NonExistentShow' not found" in res2.json()["error"]

    # Item not found for mark_completed
    res3 = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {"title": "NonExistentShow", "action": "mark_completed"},
        },
    )
    assert res3.status_code == 200
    assert res3.json()["ok"] is False
    assert "Item 'NonExistentShow' not found" in res3.json()["error"]

    # Unknown action
    res4 = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {"title": "SomeTitle", "action": "fly_to_moon"},
        },
    )
    assert res4.status_code == 200
    assert res4.json()["ok"] is False
    assert "Unknown action 'fly_to_moon'" in res4.json()["error"]


def test_homelab_tools_strict_user_isolation(client, db_session):
    """Verify that User A executing tools never modifies or sees User B's entries."""
    user_a = make_test_user(db_session, "alice_tool")
    user_b = make_test_user(db_session, "bob_tool")

    item = MediaItem(title="Shared Title", media_type=MediaType.GAME)
    db_session.add(item)
    db_session.commit()

    entry_b = UserMediaEntry(user_id=user_b.id, media_item_id=item.id, status=TrackingStatus.IN_PROGRESS, playtime_hours=10.0)
    db_session.add(entry_b)
    db_session.commit()

    # User A tries to increment progress of "Shared Title" -> not in User A's collection!
    headers_a = auth_headers_for(user_a)
    res = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers_a,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {"title": "Shared Title", "action": "increment_progress", "amount": 5},
        },
    )
    assert res.status_code == 200
    assert res.json()["ok"] is False
    assert "Item 'Shared Title' not found in collection for user 'alice_tool'" in res.json()["error"]

    # Verify Bob's entry playtime remained 10.0
    db_session.refresh(entry_b)
    assert entry_b.playtime_hours == 10.0


def test_homelab_tools_inter_service_obo_execution(client, db_session):
    """Verify BonTalk voice assistant calling tool via X-Homelab-Token + X-Homelab-User."""
    os.environ["AUTH_MODE"] = "homelab"
    os.environ["HOMELAB_INTERNAL_TOKEN"] = TEST_INTERNAL_TOKEN
    reset_config_store()

    # Service calls on behalf of target user 'bon_listener'
    obo_headers = {
        "X-Homelab-Token": TEST_INTERNAL_TOKEN,
        "X-Homelab-User": "bon_listener",
    }

    # Add item to watchlist via service-to-service call
    res = client.post(
        "/api/v1/homelab/tools/execute",
        headers=obo_headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {
                "title": "Doctor Who",
                "media_type": "tv_show",
                "action": "add_to_watchlist",
            },
        },
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert "Added 'Doctor Who' to watchlist for user 'bon_listener'." in res.json()["result"]

    # Verify target user was JIT created and entry created
    user = db_session.exec(select(User).where(User.username == "bon_listener")).first()
    assert user is not None
    entry = db_session.exec(select(UserMediaEntry).where(UserMediaEntry.user_id == user.id)).first()
    assert entry is not None
    assert entry.status == TrackingStatus.PLAN_TO


# =====================================================================
# 5. AI Media Assistant Endpoint Tests (/api/v1/ai/recommend)
# =====================================================================

def test_ai_recommend_requires_auth(client):
    """Verify POST /api/v1/ai/recommend requires authentication."""
    res = client.post("/api/v1/ai/recommend", json={})
    assert res.status_code == 401


def test_ai_recommend_missing_api_key_returns_503(client, db_session):
    """Verify 503 is returned when neither AI_API_KEY nor OPENROUTER_API_KEY is configured."""
    user = make_test_user(db_session, "ai_user_no_key")
    headers = auth_headers_for(user)

    os.environ["AI_API_KEY"] = ""
    os.environ["OPENROUTER_API_KEY"] = ""
    reset_config_store()

    res = client.post("/api/v1/ai/recommend", headers=headers, json={})
    assert res.status_code == 503
    assert "AI Assistant is not configured" in res.json()["detail"]


def test_ai_recommend_success_and_headers_verification(client, db_session):
    """Verify successful AI recommendation with correct attribution headers and taste context."""
    user = make_test_user(db_session, "ai_cinephile")
    headers = auth_headers_for(user)

    os.environ["AI_API_KEY"] = "sk-test-ai-key-9999"
    os.environ["AI_BASE_URL"] = "http://ai-gateway:4000/v1"
    os.environ["AI_MODEL"] = "openai/gpt-4o-mini"
    reset_config_store()

    # Populate user collection with favorites and ratings
    game = MediaItem(title="Chrono Trigger", media_type=MediaType.GAME, genres=["RPG", "Adventure"])
    db_session.add(game)
    db_session.commit()
    entry = UserMediaEntry(
        user_id=user.id,
        media_item_id=game.id,
        status=TrackingStatus.COMPLETED,
        rating=10.0,
        is_favorite=True,
        playtime_hours=35.0,
    )
    db_session.add(entry)
    db_session.commit()

    fake_response = {
        "model": "openai/gpt-4o-mini",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Since you loved Chrono Trigger, check out Sea of Stars and Final Fantasy VI!",
                }
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response

    captured_request = {}

    async def mock_post(self, url, headers=None, json=None, **kwargs):
        captured_request["url"] = url
        captured_request["headers"] = headers
        captured_request["json"] = json
        return mock_resp

    with patch.object(httpx.AsyncClient, "post", new=mock_post):
        res = client.post(
            "/api/v1/ai/recommend",
            headers=headers,
            json={"media_type": "game", "prompt": "Looking for classic JRPGs"},
        )

    assert res.status_code == 200
    data = res.json()
    assert "Sea of Stars" in data["recommendation"]
    assert data["model"] == "openai/gpt-4o-mini"

    # Verify outgoing URL and attribution headers
    assert captured_request["url"] == "http://ai-gateway:4000/v1/chat/completions"
    assert captured_request["headers"]["Authorization"] == "Bearer sk-test-ai-key-9999"
    assert captured_request["headers"]["X-Homelab-Service"] == "hostcart"
    assert captured_request["headers"]["X-Homelab-User"] == "ai_cinephile"

    # Verify taste context and user prompt in payload
    user_msg = captured_request["json"]["messages"][1]["content"]
    assert "Chrono Trigger" in user_msg
    assert "Looking for classic JRPGs" in user_msg
    assert "Target media type: game" in user_msg


def test_ai_recommend_downstream_service_error(client, db_session):
    """Verify 502 Bad Gateway when downstream AI service returns 500 error."""
    user = make_test_user(db_session, "ai_error_user")
    headers = auth_headers_for(user)

    os.environ["AI_API_KEY"] = "sk-test-ai-key-9999"
    reset_config_store()

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    async def mock_post(self, url, **kwargs):
        return mock_resp

    with patch.object(httpx.AsyncClient, "post", new=mock_post):
        res = client.post("/api/v1/ai/recommend", headers=headers, json={})

    assert res.status_code == 502
    assert "Downstream AI service error (500)" in res.json()["detail"]


def test_ai_recommend_timeout_returns_504(client, db_session):
    """Verify 504 Gateway Timeout when downstream AI service times out."""
    user = make_test_user(db_session, "ai_timeout_user")
    headers = auth_headers_for(user)

    os.environ["AI_API_KEY"] = "sk-test-ai-key-9999"
    reset_config_store()

    async def mock_post(self, url, **kwargs):
        raise httpx.TimeoutException("Timeout")

    with patch.object(httpx.AsyncClient, "post", new=mock_post):
        res = client.post("/api/v1/ai/recommend", headers=headers, json={})

    assert res.status_code == 504
    assert "timed out" in res.json()["detail"]


def test_ai_recommend_network_error_returns_502(client, db_session):
    """Verify 502 Bad Gateway when network connection fails."""
    user = make_test_user(db_session, "ai_net_error_user")
    headers = auth_headers_for(user)

    os.environ["AI_API_KEY"] = "sk-test-ai-key-9999"
    reset_config_store()

    async def mock_post(self, url, **kwargs):
        raise httpx.ConnectError("Connection refused")

    with patch.object(httpx.AsyncClient, "post", new=mock_post):
        res = client.post("/api/v1/ai/recommend", headers=headers, json={})

    assert res.status_code == 502
    assert "Failed to communicate with AI service" in res.json()["detail"]


def test_ai_recommend_http_400_and_empty_choices(client, db_session):
    """Verify handling of downstream HTTP 400 error and empty choices list."""
    user = make_test_user(db_session, "ai_edge_user")
    headers = auth_headers_for(user)

    os.environ["AI_API_KEY"] = "sk-test-ai-key-9999"
    reset_config_store()

    # 1. Test status 400
    mock_resp_400 = MagicMock()
    mock_resp_400.status_code = 400
    mock_resp_400.text = "Bad Request from upstream model"

    async def mock_post_400(self, url, **kwargs):
        return mock_resp_400

    with patch.object(httpx.AsyncClient, "post", new=mock_post_400):
        res = client.post("/api/v1/ai/recommend", headers=headers, json={})
    assert res.status_code == 502
    assert "Downstream AI service error (400)" in res.json()["detail"]

    # 2. Test empty choices
    mock_resp_empty = MagicMock()
    mock_resp_empty.status_code = 200
    mock_resp_empty.json.return_value = {"choices": []}

    async def mock_post_empty(self, url, **kwargs):
        return mock_resp_empty

    with patch.object(httpx.AsyncClient, "post", new=mock_post_empty):
        res2 = client.post("/api/v1/ai/recommend", headers=headers, json={})
    assert res2.status_code == 200
    assert res2.json()["recommendation"] == ""


def test_ai_recommend_taste_context_episodes_and_pages(client, db_session):
    """Verify taste context builder includes episodes and pages."""
    user = make_test_user(db_session, "ai_multi_user")
    headers = auth_headers_for(user)

    os.environ["AI_API_KEY"] = "sk-test-ai-key-9999"
    reset_config_store()

    tv = MediaItem(title="Show With Ep", media_type=MediaType.TV_SHOW)
    book = MediaItem(title="Book With Pages", media_type=MediaType.BOOK)
    db_session.add_all([tv, book])
    db_session.commit()

    db_session.add(UserMediaEntry(user_id=user.id, media_item_id=tv.id, status=TrackingStatus.IN_PROGRESS, current_episode=15))
    db_session.add(UserMediaEntry(user_id=user.id, media_item_id=book.id, status=TrackingStatus.IN_PROGRESS, current_page=220))
    db_session.commit()

    captured_prompt = {}

    async def mock_post_capture(self, url, json=None, **kwargs):
        captured_prompt["content"] = json["messages"][1]["content"]
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"choices": [{"message": {"content": "Sample rec"}}]}
        return resp

    with patch.object(httpx.AsyncClient, "post", new=mock_post_capture):
        res = client.post("/api/v1/ai/recommend", headers=headers, json={})
    assert res.status_code == 200
    assert "Episode: 15" in captured_prompt["content"]
    assert "Page: 220" in captured_prompt["content"]


def test_homelab_tools_execute_more_edge_cases(client, db_session):
    """Verify invalid amount fallback, unmetered TV/book increment, and mark_completed with media_type."""
    user = make_test_user(db_session, "edge_user")
    headers = auth_headers_for(user)

    # TV show without total_episodes
    tv = MediaItem(title="Endless Series", media_type=MediaType.TV_SHOW, total_episodes=None)
    # Book without total_pages
    book = MediaItem(title="Endless Book", media_type=MediaType.BOOK, total_pages=None)
    db_session.add_all([tv, book])
    db_session.commit()

    db_session.add(UserMediaEntry(user_id=user.id, media_item_id=tv.id, status=TrackingStatus.IN_PROGRESS, current_episode=1))
    db_session.add(UserMediaEntry(user_id=user.id, media_item_id=book.id, status=TrackingStatus.IN_PROGRESS, current_page=10))
    db_session.commit()

    # Invalid amount string -> fallback to 1.0
    res1 = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {
                "title": "Endless Series",
                "action": "increment_progress",
                "amount": "not_a_valid_number",
            },
        },
    )
    assert res1.status_code == 200
    assert "episode progress is now 2 (in_progress)" in res1.json()["result"]

    # Book increment without total_pages
    res2 = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {
                "title": "Endless Book",
                "action": "increment_progress",
                "amount": 25,
            },
        },
    )
    assert res2.status_code == 200
    assert "page progress is now 35 (in_progress)" in res2.json()["result"]

    # mark_completed with media_type filter
    res3 = client.post(
        "/api/v1/homelab/tools/execute",
        headers=headers,
        json={
            "tool_name": "hostcart_update_progress",
            "arguments": {
                "title": "Endless Book",
                "media_type": "book",
                "action": "mark_completed",
            },
        },
    )
    assert res3.status_code == 200
    assert "Marked 'Endless Book' as completed" in res3.json()["result"]

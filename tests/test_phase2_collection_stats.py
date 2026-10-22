"""
Phase 2 Test Suite: Authentication, Multi-Media Collection CRUD, Quick Increment,
Strict User Isolation, and the Comprehensive Statistics Analytics Engine.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from src.api.v1.auth import get_current_user
from src.core.security import create_access_token
from src.data.database import get_session, init_db
from src.data.models import MediaType, TrackingStatus, User
from src.main import app


@pytest.fixture(name="db_session")
def db_session_fixture() -> Generator[Session, None, None]:
    """Provide an isolated in-memory SQLite database session for each test."""
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
    """Provide a TestClient with database session overridden by db_session and lifespan triggered."""
    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def register_user(
    client: TestClient,
    username: str = "testuser",
    email: str = "testuser@hostcart.local",
    password: str = "password123",
) -> dict:
    """Helper to register a user and return the response json."""
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert resp.status_code == 201
    return resp.json()


def auth_header(token: str) -> dict:
    """Helper to create authorization header."""
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. Health Probe Test
# ==============================================================================


def test_health_check(client: TestClient):
    """Test health check probe endpoint."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "app": "HostCart"}


# ==============================================================================
# 2. Authentication & Authorization Tests
# ==============================================================================


def test_user_registration_admin_and_regular(client: TestClient):
    """
    Test registration semantics:
    - First registered user is automatically made admin (is_admin=True)
    - Subsequent registered users are regular users (is_admin=False)
    - Duplicate username / email handling (case-insensitive)
    """
    # 1. First user -> Admin
    first_data = register_user(client, "alice", "alice@hostcart.local", "securepass123")
    assert first_data["user"]["username"] == "alice"
    assert first_data["user"]["is_admin"] is True
    assert "access_token" in first_data
    assert first_data["token_type"] == "bearer"

    # 2. Second user -> Regular user
    second_data = register_user(client, "bob", "bob@hostcart.local", "securepass123")
    assert second_data["user"]["username"] == "bob"
    assert second_data["user"]["is_admin"] is False

    # 3. Duplicate username (case-insensitive)
    dup_name_resp = client.post(
        "/api/v1/auth/register",
        json={"username": "ALICE", "email": "alice2@hostcart.local", "password": "password123"},
    )
    assert dup_name_resp.status_code == 400
    assert "Username already registered" in dup_name_resp.json()["detail"]

    # 4. Duplicate email (case-insensitive)
    dup_email_resp = client.post(
        "/api/v1/auth/register",
        json={"username": "alice_alt", "email": "ALICE@hostcart.local", "password": "password123"},
    )
    assert dup_email_resp.status_code == 400
    assert "Email already registered" in dup_email_resp.json()["detail"]


def test_user_login_json_and_form(client: TestClient):
    """Test login via both JSON payload and OAuth2 form urlencoded."""
    register_user(client, "carol", "carol@hostcart.local", "mypassword123")

    # 1. JSON Login
    resp_json = client.post(
        "/api/v1/auth/login",
        json={"username": "carol", "password": "mypassword123"},
    )
    assert resp_json.status_code == 200
    token_data = resp_json.json()
    assert "access_token" in token_data
    assert token_data["user"]["username"] == "carol"

    # 2. Form Login (OAuth2 Password Request Form format)
    resp_form = client.post(
        "/api/v1/auth/login",
        data={"username": "carol", "password": "mypassword123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp_form.status_code == 200
    assert "access_token" in resp_form.json()

    # 3. Invalid password -> 401
    resp_bad_pw = client.post(
        "/api/v1/auth/login",
        json={"username": "carol", "password": "wrongpassword"},
    )
    assert resp_bad_pw.status_code == 401
    assert "Invalid username or password" in resp_bad_pw.json()["detail"]

    # 4. Unknown username -> 401
    resp_unknown = client.post(
        "/api/v1/auth/login",
        json={"username": "nonexistent", "password": "mypassword123"},
    )
    assert resp_unknown.status_code == 401

    # 5. Missing / empty username or password -> 400
    resp_empty = client.post(
        "/api/v1/auth/login",
        json={"username": "", "password": ""},
    )
    assert resp_empty.status_code == 400

    # 6. Invalid body
    resp_invalid_body = client.post(
        "/api/v1/auth/login",
        content="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp_invalid_body.status_code == 400


def test_auth_guards_and_roles(client: TestClient, db_session: Session):
    """Test token validation, /me endpoint, and admin role guard."""
    admin_data = register_user(client, "admin_user", "admin@hostcart.local", "adminpass")
    admin_token = admin_data["access_token"]

    user_data = register_user(client, "regular_user", "reg@hostcart.local", "regpass")
    user_token = user_data["access_token"]

    # 1. GET /api/v1/auth/me with valid token
    me_resp = client.get("/api/v1/auth/me", headers=auth_header(admin_token))
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "admin_user"
    assert me_resp.json()["is_admin"] is True

    # 2. Missing token on protected endpoint -> 401
    no_auth_resp = client.get("/api/v1/auth/me")
    assert no_auth_resp.status_code == 401

    # 3. Malformed token -> 401
    bad_token_resp = client.get("/api/v1/auth/me", headers=auth_header("invalid.jwt.token"))
    assert bad_token_resp.status_code == 401

    # 4. Expired token -> 401
    expired_token = create_access_token(
        {"sub": str(admin_data["user"]["id"])},
        expires_delta=timedelta(seconds=-10),
    )
    expired_resp = client.get("/api/v1/auth/me", headers=auth_header(expired_token))
    assert expired_resp.status_code == 401

    # 5. Token for deleted / nonexistent user -> 401
    ghost_token = create_access_token({"sub": "999999"})
    ghost_resp = client.get("/api/v1/auth/me", headers=auth_header(ghost_token))
    assert ghost_resp.status_code == 401

    # 6. Invalid user ID format in token -> 401
    invalid_sub_token = create_access_token({"sub": "not_an_int"})
    inv_sub_resp = client.get("/api/v1/auth/me", headers=auth_header(invalid_sub_token))
    assert inv_sub_resp.status_code == 401

    # 7. Admin-only route access:
    # Admin accesses -> 200
    admin_access_resp = client.get("/api/v1/auth/admin-only", headers=auth_header(admin_token))
    assert admin_access_resp.status_code == 200

    # Regular user accesses -> 403 Forbidden
    reg_access_resp = client.get("/api/v1/auth/admin-only", headers=auth_header(user_token))
    assert reg_access_resp.status_code == 403
    assert "Admin privileges required" in reg_access_resp.json()["detail"]


# ==============================================================================
# 3. Collection CRUD Across All 4 Media Types
# ==============================================================================


def test_collection_crud_all_four_media_types(client: TestClient):
    """Test full CRUD operations for Game, Movie, TV Show, and Book items."""
    user = register_user(client, "curator1", "curator1@hostcart.local", "curatorpass")
    headers = auth_header(user["access_token"])

    # 1. Create Game Entry
    game_payload = {
        "media": {
            "media_type": "game",
            "title": "Hollow Knight",
            "release_year": 2017,
            "genres": ["Metroidvania", "Action"],
            "creators": ["Team Cherry"],
            "runtime_minutes": 1800,
        },
        "status": "in_progress",
        "rating": 9.5,
        "playtime_hours": 34.5,
        "tags": ["favorite", "indie"],
        "notes": "Exploring Hallownest",
    }
    game_resp = client.post("/api/v1/collection", json=game_payload, headers=headers)
    assert game_resp.status_code == 201
    game_data = game_resp.json()
    assert game_data["media"]["media_type"] == "game"
    assert game_data["media"]["title"] == "Hollow Knight"
    assert game_data["playtime_hours"] == 34.5
    assert game_data["started_at"] is not None
    game_id = game_data["id"]

    # 2. Create Movie Entry
    movie_payload = {
        "media": {
            "media_type": "movie",
            "title": "Interstellar",
            "release_year": 2014,
            "genres": ["Sci-Fi", "Drama"],
            "creators": ["Christopher Nolan"],
            "runtime_minutes": 169,
        },
        "status": "completed",
        "rating": 9.8,
        "rewatch_count": 2,
    }
    movie_resp = client.post("/api/v1/collection", json=movie_payload, headers=headers)
    assert movie_resp.status_code == 201
    movie_data = movie_resp.json()
    assert movie_data["media"]["media_type"] == "movie"
    assert movie_data["status"] == "completed"
    assert movie_data["completed_at"] is not None
    movie_id = movie_data["id"]

    # 3. Create TV Show Entry
    tv_payload = {
        "media": {
            "media_type": "tv_show",
            "title": "Arcane",
            "release_year": 2021,
            "total_episodes": 9,
            "runtime_minutes": 42,
            "genres": ["Animation", "Action", "Sci-Fi"],
        },
        "status": "in_progress",
        "current_episode": 6,
        "rating": 10.0,
    }
    tv_resp = client.post("/api/v1/collection", json=tv_payload, headers=headers)
    assert tv_resp.status_code == 201
    tv_data = tv_resp.json()
    assert tv_data["media"]["media_type"] == "tv_show"
    assert tv_data["current_episode"] == 6
    tv_id = tv_data["id"]

    # 4. Create Book Entry
    book_payload = {
        "media": {
            "media_type": "book",
            "title": "Project Hail Mary",
            "release_year": 2021,
            "total_pages": 496,
            "creators": ["Andy Weir"],
            "genres": ["Sci-Fi"],
        },
        "status": "plan_to",
        "current_page": 0,
    }
    book_resp = client.post("/api/v1/collection", json=book_payload, headers=headers)
    assert book_resp.status_code == 201
    book_data = book_resp.json()
    assert book_data["media"]["media_type"] == "book"
    assert book_data["current_page"] == 0
    book_id = book_data["id"]

    # 5. Read single entry
    get_game = client.get(f"/api/v1/collection/{game_id}", headers=headers)
    assert get_game.status_code == 200
    assert get_game.json()["id"] == game_id

    # 6. Update entry (including linked media item attributes)
    update_payload = {
        "rating": 10.0,
        "is_favorite": True,
        "playtime_hours": 45.0,
        "notes": "112% Completion achieved!",
        "media": {
            "media_type": "game",
            "title": "Hollow Knight",
            "poster_url": "https://cdn.example.com/hollow_knight.jpg",
        },
    }
    update_resp = client.put(f"/api/v1/collection/{game_id}", json=update_payload, headers=headers)
    assert update_resp.status_code == 200
    updated_game = update_resp.json()
    assert updated_game["rating"] == 10.0
    assert updated_game["is_favorite"] is True
    assert updated_game["playtime_hours"] == 45.0
    assert updated_game["media"]["poster_url"] == "https://cdn.example.com/hollow_knight.jpg"

    # 7. Update status to completed auto-sets completed_at
    put_complete = client.put(
        f"/api/v1/collection/{book_id}",
        json={"status": "completed", "current_page": 496},
        headers=headers,
    )
    assert put_complete.status_code == 200
    assert put_complete.json()["status"] == "completed"
    assert put_complete.json()["completed_at"] is not None

    # 8. Delete entry
    del_resp = client.delete(f"/api/v1/collection/{game_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json() == {"ok": True, "deleted_id": game_id}

    # Verify deleted entry returns 404
    assert client.get(f"/api/v1/collection/{game_id}", headers=headers).status_code == 404


# ==============================================================================
# 4. Strict User Isolation Tests
# ==============================================================================


def test_strict_user_isolation(client: TestClient):
    """
    Verify complete isolation between users:
    - User A cannot view User B's collection entries
    - User A cannot get, update, increment, or delete User B's entry (returns 404)
    - User A's statistics do not include User B's entries
    """
    user_a = register_user(client, "usera", "usera@hostcart.local", "password123")
    user_b = register_user(client, "userb", "userb@hostcart.local", "password123")
    headers_a = auth_header(user_a["access_token"])
    headers_b = auth_header(user_b["access_token"])

    # User B creates a private game entry
    b_entry_resp = client.post(
        "/api/v1/collection",
        json={
            "media": {
                "media_type": "game",
                "title": "Secret Game of User B",
            },
            "status": "in_progress",
            "playtime_hours": 100.0,
        },
        headers=headers_b,
    )
    assert b_entry_resp.status_code == 201
    b_entry_id = b_entry_resp.json()["id"]

    # User A creates a movie entry
    a_entry_resp = client.post(
        "/api/v1/collection",
        json={
            "media": {
                "media_type": "movie",
                "title": "Movie of User A",
            },
            "status": "completed",
        },
        headers=headers_a,
    )
    assert a_entry_resp.status_code == 201
    a_entry_id = a_entry_resp.json()["id"]

    # 1. User A lists entries -> should ONLY have 1 item (User A's movie)
    list_a = client.get("/api/v1/collection", headers=headers_a)
    assert list_a.status_code == 200
    items_a = list_a.json()
    assert len(items_a) == 1
    assert items_a[0]["id"] == a_entry_id
    assert items_a[0]["media"]["title"] == "Movie of User A"

    # 2. User A attempts to GET User B's entry -> 404
    get_b = client.get(f"/api/v1/collection/{b_entry_id}", headers=headers_a)
    assert get_b.status_code == 404

    # 3. User A attempts to PUT User B's entry -> 404
    put_b = client.put(
        f"/api/v1/collection/{b_entry_id}",
        json={"notes": "Hacked by User A"},
        headers=headers_a,
    )
    assert put_b.status_code == 404

    # 4. User A attempts to INCREMENT User B's entry -> 404
    inc_b = client.post(
        f"/api/v1/collection/{b_entry_id}/increment",
        json={"amount": 10.0},
        headers=headers_a,
    )
    assert inc_b.status_code == 404

    # 5. User A attempts to DELETE User B's entry -> 404
    del_b = client.delete(f"/api/v1/collection/{b_entry_id}", headers=headers_a)
    assert del_b.status_code == 404

    # Verify User B's entry is pristine and unaffected
    b_verify = client.get(f"/api/v1/collection/{b_entry_id}", headers=headers_b)
    assert b_verify.status_code == 200
    assert b_verify.json()["playtime_hours"] == 100.0


# ==============================================================================
# 5. MediaItem Reuse and Attaching Existing Media
# ==============================================================================


def test_media_item_reuse_and_attaching(client: TestClient):
    """
    Test MediaItem catalog deduplication:
    - Adding media with identical external_id + external_source reuses the same MediaItem
    - Adding media with identical title + media_type reuses the same MediaItem
    - Adding an item by explicit media_item_id attaches directly
    - Attempting to add an entry for a media item already in the user's collection returns 400
    - Referencing a nonexistent media_item_id returns 404
    """
    user1 = register_user(client, "user1", "user1@hostcart.local", "password123")
    user2 = register_user(client, "user2", "user2@hostcart.local", "password123")
    h1 = auth_header(user1["access_token"])
    h2 = auth_header(user2["access_token"])

    # 1. User 1 adds "The Matrix" via external_id
    resp1 = client.post(
        "/api/v1/collection",
        json={
            "media": {
                "media_type": "movie",
                "title": "The Matrix",
                "external_id": "tmdb-603",
                "external_source": "tmdb",
                "release_year": 1999,
            },
            "status": "completed",
        },
        headers=h1,
    )
    assert resp1.status_code == 201
    media_item_id = resp1.json()["media"]["id"]

    # 2. User 2 adds "The Matrix" via identical external_id -> reuses same MediaItem
    resp2 = client.post(
        "/api/v1/collection",
        json={
            "media": {
                "media_type": "movie",
                "title": "The Matrix",
                "external_id": "tmdb-603",
                "external_source": "tmdb",
            },
            "status": "plan_to",
        },
        headers=h2,
    )
    assert resp2.status_code == 201
    assert resp2.json()["media"]["id"] == media_item_id

    # 3. User 1 attempts duplicate addition -> 400
    dup_resp = client.post(
        "/api/v1/collection",
        json={"media_item_id": media_item_id, "status": "completed"},
        headers=h1,
    )
    assert dup_resp.status_code == 400
    assert "already in your collection" in dup_resp.json()["detail"]

    # 4. User 2 attaches another existing media by media_item_id
    # Create game with user 1 first
    game_r = client.post(
        "/api/v1/collection",
        json={
            "media": {
                "media_type": "game",
                "title": "Bloodborne",
            },
        },
        headers=h1,
    )
    game_media_id = game_r.json()["media"]["id"]

    # User 2 attaches via media_item_id
    u2_game_r = client.post(
        "/api/v1/collection",
        json={"media_item_id": game_media_id, "status": "in_progress"},
        headers=h2,
    )
    assert u2_game_r.status_code == 201
    assert u2_game_r.json()["media"]["id"] == game_media_id

    # 5. Non-existent media_item_id -> 404
    bad_attach = client.post(
        "/api/v1/collection",
        json={"media_item_id": 999999, "status": "plan_to"},
        headers=h1,
    )
    assert bad_attach.status_code == 404

    # 6. Title + media_type matching deduplication
    book1 = client.post(
        "/api/v1/collection",
        json={"media": {"media_type": "book", "title": "Foundation"}},
        headers=h1,
    )
    book2 = client.post(
        "/api/v1/collection",
        json={"media": {"media_type": "book", "title": "foundation"}},
        headers=h2,
    )
    assert book1.json()["media"]["id"] == book2.json()["media"]["id"]


# ==============================================================================
# 6. Filtering and Sorting Tests
# ==============================================================================


def test_collection_filtering_and_sorting(client: TestClient):
    """Test filtering by media_type, status, tag, search, is_favorite, min_rating, and sort_by."""
    user = register_user(client, "filter_user", "filter@hostcart.local", "password123")
    headers = auth_header(user["access_token"])

    items = [
        {
            "media": {"media_type": "game", "title": "Zelda: Breath of the Wild", "original_title": "BotW"},
            "status": "completed",
            "rating": 9.5,
            "is_favorite": True,
            "tags": ["switch", "goty"],
        },
        {
            "media": {"media_type": "game", "title": "Super Mario Odyssey"},
            "status": "in_progress",
            "rating": 8.0,
            "is_favorite": False,
            "tags": ["switch", "platformer"],
        },
        {
            "media": {"media_type": "movie", "title": "Spirited Away"},
            "status": "completed",
            "rating": 10.0,
            "is_favorite": True,
            "tags": ["anime", "classic"],
        },
        {
            "media": {"media_type": "tv_show", "title": "Chernobyl"},
            "status": "completed",
            "rating": 9.0,
            "is_favorite": False,
            "tags": ["hbo", "drama"],
        },
        {
            "media": {"media_type": "book", "title": "Hyperion"},
            "status": "plan_to",
            "rating": None,
            "is_favorite": False,
            "tags": ["sci-fi"],
        },
    ]

    for item in items:
        resp = client.post("/api/v1/collection", json=item, headers=headers)
        assert resp.status_code == 201

    # 1. Filter by media_type
    games_resp = client.get("/api/v1/collection?media_type=game", headers=headers)
    assert len(games_resp.json()) == 2

    # 2. Filter by status
    completed_resp = client.get("/api/v1/collection?status=completed", headers=headers)
    assert len(completed_resp.json()) == 3

    # 3. Filter by is_favorite
    favs_resp = client.get("/api/v1/collection?is_favorite=true", headers=headers)
    assert len(favs_resp.json()) == 2

    # 4. Filter by min_rating
    min_rating_resp = client.get("/api/v1/collection?min_rating=9.5", headers=headers)
    assert len(min_rating_resp.json()) == 2  # 9.5 and 10.0

    # 5. Filter by search (title)
    search_title = client.get("/api/v1/collection?search=mario", headers=headers)
    assert len(search_title.json()) == 1
    assert search_title.json()[0]["media"]["title"] == "Super Mario Odyssey"

    # 6. Filter by search (original_title)
    search_orig = client.get("/api/v1/collection?search=botw", headers=headers)
    assert len(search_orig.json()) == 1
    assert search_orig.json()[0]["media"]["title"] == "Zelda: Breath of the Wild"

    # 7. Filter by tag
    tag_switch = client.get("/api/v1/collection?tag=switch", headers=headers)
    assert len(tag_switch.json()) == 2

    tag_anime = client.get("/api/v1/collection?tag=anime", headers=headers)
    assert len(tag_anime.json()) == 1

    # 8. Sorting: title_asc & title_desc
    sort_title_asc = client.get("/api/v1/collection?sort_by=title_asc", headers=headers)
    titles_asc = [x["media"]["title"] for x in sort_title_asc.json()]
    assert titles_asc == sorted(titles_asc)

    sort_title_desc = client.get("/api/v1/collection?sort_by=title_desc", headers=headers)
    titles_desc = [x["media"]["title"] for x in sort_title_desc.json()]
    assert titles_desc == sorted(titles_asc, reverse=True)

    # 9. Sorting: rating_desc & rating_asc
    sort_rating_desc = client.get("/api/v1/collection?sort_by=rating_desc", headers=headers)
    ratings_desc = [x["rating"] for x in sort_rating_desc.json() if x["rating"] is not None]
    assert ratings_desc == [10.0, 9.5, 9.0, 8.0]

    sort_rating_asc = client.get("/api/v1/collection?sort_by=rating_asc", headers=headers)
    ratings_asc = [x["rating"] for x in sort_rating_asc.json() if x["rating"] is not None]
    assert ratings_asc == [8.0, 9.0, 9.5, 10.0]

    # 10. Sorting: created_at_asc & created_at_desc, updated_at_asc
    sort_c_asc = client.get("/api/v1/collection?sort_by=created_at_asc", headers=headers)
    assert len(sort_c_asc.json()) == 5

    sort_c_desc = client.get("/api/v1/collection?sort_by=created_at_desc", headers=headers)
    assert len(sort_c_desc.json()) == 5

    sort_u_asc = client.get("/api/v1/collection?sort_by=updated_at_asc", headers=headers)
    assert len(sort_u_asc.json()) == 5


# ==============================================================================
# 7. Quick Increment (+1) Progress & Auto-Completion Tests
# ==============================================================================


def test_quick_increment_all_types_and_auto_completion(client: TestClient):
    """
    Test +amount quick-increment logic:
    - Game: playtime_hours += amount
    - Movie: rewatch_count += amount
    - TV Show: current_episode += amount; auto-completes when total_episodes reached
    - Book: current_page += amount; auto-completes when total_pages reached
    - Automatically moves plan_to items to in_progress and sets started_at
    """
    user = register_user(client, "inc_user", "inc@hostcart.local", "password123")
    headers = auth_header(user["access_token"])

    # 1. Game increment & plan_to -> in_progress transition
    game_r = client.post(
        "/api/v1/collection",
        json={
            "media": {"media_type": "game", "title": "Cyberpunk 2077"},
            "status": "plan_to",
            "playtime_hours": 0.0,
        },
        headers=headers,
    )
    game_id = game_r.json()["id"]
    assert game_r.json()["status"] == "plan_to"
    assert game_r.json()["started_at"] is None

    inc_game = client.post(
        f"/api/v1/collection/{game_id}/increment",
        json={"amount": 2.5},
        headers=headers,
    )
    assert inc_game.status_code == 200
    assert inc_game.json()["playtime_hours"] == 2.5
    assert inc_game.json()["status"] == "in_progress"
    assert inc_game.json()["started_at"] is not None

    # 2. Movie increment (rewatch count)
    movie_r = client.post(
        "/api/v1/collection",
        json={
            "media": {"media_type": "movie", "title": "The Dark Knight"},
            "status": "completed",
            "rewatch_count": 1,
        },
        headers=headers,
    )
    movie_id = movie_r.json()["id"]

    inc_movie = client.post(
        f"/api/v1/collection/{movie_id}/increment",
        json={"amount": 1.0},
        headers=headers,
    )
    assert inc_movie.status_code == 200
    assert inc_movie.json()["rewatch_count"] == 2

    # 3. TV Show increment & auto-completion
    tv_r = client.post(
        "/api/v1/collection",
        json={
            "media": {
                "media_type": "tv_show",
                "title": "Sherlock",
                "total_episodes": 4,
            },
            "status": "in_progress",
            "current_episode": 3,
        },
        headers=headers,
    )
    tv_id = tv_r.json()["id"]

    inc_tv = client.post(
        f"/api/v1/collection/{tv_id}/increment",
        json={"amount": 1.0},
        headers=headers,
    )
    assert inc_tv.status_code == 200
    tv_after = inc_tv.json()
    assert tv_after["current_episode"] == 4
    assert tv_after["status"] == "completed"
    assert tv_after["completed_at"] is not None

    # 4. Book increment & auto-completion
    book_r = client.post(
        "/api/v1/collection",
        json={
            "media": {
                "media_type": "book",
                "title": "The Hobbit",
                "total_pages": 310,
            },
            "status": "in_progress",
            "current_page": 300,
        },
        headers=headers,
    )
    book_id = book_r.json()["id"]

    inc_book = client.post(
        f"/api/v1/collection/{book_id}/increment",
        json={"amount": 15.0},
        headers=headers,
    )
    assert inc_book.status_code == 200
    book_after = inc_book.json()
    assert book_after["current_page"] == 315
    assert book_after["status"] == "completed"
    assert book_after["completed_at"] is not None

    # 5. Incrementing nonexistent entry returns 404
    inc_404 = client.post("/api/v1/collection/99999/increment", json={"amount": 1.0}, headers=headers)
    assert inc_404.status_code == 404


# ==============================================================================
# 8. Collection Statistics Analytics Engine Tests
# ==============================================================================


def test_collection_stats_analytics_engine(client: TestClient):
    """
    Test the comprehensive collection stats calculation engine:
    - KPIs: total_items, game_hours, movie_hours, tv_hours, episodes_watched,
            pages_read, book_hours, total_time_hours, avg_rating, completion_rate,
            curator_xp, curator_level
    - Charts: status_counts, media_type_counts, time_by_media_type, rating_distribution,
              top_genres, top_formats, monthly_activity
    """
    user = register_user(client, "stats_user", "stats@hostcart.local", "statspass")
    headers = auth_header(user["access_token"])

    # 1. Game 1: 50.0 hours, completed, rating 10.0, genres ["Action", "RPG"]
    client.post(
        "/api/v1/collection",
        json={
            "media": {
                "media_type": "game",
                "title": "The Witcher 3",
                "genres": ["Action", "RPG"],
            },
            "status": "completed",
            "rating": 10.0,
            "playtime_hours": 50.0,
        },
        headers=headers,
    )

    # 2. Game 2: 20.0 hours, in_progress, rating 8.0, genres ["RPG"]
    client.post(
        "/api/v1/collection",
        json={
            "media": {
                "media_type": "game",
                "title": "Baldur's Gate 3",
                "genres": ["RPG"],
            },
            "status": "in_progress",
            "rating": 8.0,
            "playtime_hours": 20.0,
        },
        headers=headers,
    )

    # 3. Movie 1: runtime 120 mins, completed, rewatch_count 1, rating 9.0, genres ["Sci-Fi"]
    # Watches = rewatch_count(1) + completed(1) = 2 watches -> 2 * 120 / 60 = 4.0 hours
    client.post(
        "/api/v1/collection",
        json={
            "media": {
                "media_type": "movie",
                "title": "Blade Runner 2049",
                "runtime_minutes": 120,
                "genres": ["Sci-Fi"],
            },
            "status": "completed",
            "rating": 9.0,
            "rewatch_count": 1,
        },
        headers=headers,
    )

    # 4. TV Show 1: runtime 45 mins, current_episode 20, rating 7.0, genres ["Drama"]
    # tv_hours = 20 * 45 / 60 = 15.0 hours
    client.post(
        "/api/v1/collection",
        json={
            "media": {
                "media_type": "tv_show",
                "title": "Succession",
                "runtime_minutes": 45,
                "genres": ["Drama"],
            },
            "status": "in_progress",
            "current_episode": 20,
            "rating": 7.0,
        },
        headers=headers,
    )

    # 5. Book 1: 500 pages, completed, rating 6.0, genres ["Fantasy"]
    # book_hours = 500 / 50 = 10.0 hours
    client.post(
        "/api/v1/collection",
        json={
            "media": {
                "media_type": "book",
                "title": "The Way of Kings",
                "total_pages": 500,
                "genres": ["Fantasy"],
            },
            "status": "completed",
            "rating": 6.0,
            "current_page": 500,
        },
        headers=headers,
    )

    # Fetch stats
    stats_resp = client.get("/api/v1/collection/stats", headers=headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()

    # KPI Verifications:
    assert stats["total_items"] == 5
    assert stats["game_hours"] == 70.0  # 50.0 + 20.0
    assert stats["movie_hours"] == 4.0  # 2 watches * 120 / 60
    assert stats["tv_hours"] == 15.0    # 20 * 45 / 60
    assert stats["episodes_watched"] == 20
    assert stats["pages_read"] == 500
    assert stats["book_hours"] == 10.0  # 500 / 50
    assert stats["total_time_hours"] == 99.0  # 70 + 4 + 15 + 10
    # Average rating: (10 + 8 + 9 + 7 + 6) / 5 = 40 / 5 = 8.0
    assert stats["avg_rating"] == 8.0
    # Completion rate: 3 completed / 5 items * 100 = 60.0%
    assert stats["completion_rate"] == 60.0
    # Curator XP calculation:
    # (5 items * 10) + (3 completed * 25) + int(70 * 2) + (20 * 5) + int(500 * 0.1)
    # = 50 + 75 + 140 + 100 + 50 = 415 XP
    assert stats["curator_xp"] == 415
    # Level: 415 // 100 + 1 = 5
    assert stats["curator_level"] == 5

    # Chart Verifications:
    # Status counts
    assert stats["status_counts"]["completed"] == 3
    assert stats["status_counts"]["in_progress"] == 2
    assert stats["status_counts"]["plan_to"] == 0

    # Media type counts
    assert stats["media_type_counts"]["game"] == 2
    assert stats["media_type_counts"]["movie"] == 1
    assert stats["media_type_counts"]["tv_show"] == 1
    assert stats["media_type_counts"]["book"] == 1

    # Time by media type
    assert stats["time_by_media_type"] == {
        "game": 70.0,
        "movie": 4.0,
        "tv_show": 15.0,
        "book": 10.0,
    }

    # Rating distribution buckets
    # 10.0 -> "10★", 9.0 -> "9★", 8.0 -> "8★", 7.0 -> "7★", 6.0 -> "≤6★"
    rating_dict = {b["label"]: b["count"] for b in stats["rating_distribution"]}
    assert rating_dict["10★"] == 1
    assert rating_dict["9★"] == 1
    assert rating_dict["8★"] == 1
    assert rating_dict["7★"] == 1
    assert rating_dict["≤6★"] == 1

    # Top Genres: RPG appears twice, others appear once
    genre_dict = {g["name"]: g["count"] for g in stats["top_genres"]}
    assert genre_dict["RPG"] == 2
    assert genre_dict["Action"] == 1
    assert genre_dict["Sci-Fi"] == 1
    assert genre_dict["Drama"] == 1
    assert genre_dict["Fantasy"] == 1

    # Top Formats: breakdown by media type
    format_dict = {f["name"]: f["count"] for f in stats["top_formats"]}
    assert format_dict["game"] == 2
    assert format_dict["movie"] == 1
    assert format_dict["tv_show"] == 1
    assert format_dict["book"] == 1

    # Monthly Activity: 6 monthly points
    monthly_activity = stats["monthly_activity"]
    assert len(monthly_activity) == 6
    # Total activity across months should sum to 5 items
    total_monthly = sum(m["total"] for m in monthly_activity)
    assert total_monthly == 5


def test_stats_empty_collection(client: TestClient):
    """Test stats endpoint on a fresh user with no items in collection."""
    user = register_user(client, "empty_user", "empty@hostcart.local", "password123")
    headers = auth_header(user["access_token"])

    stats_resp = client.get("/api/v1/collection/stats", headers=headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()

    assert stats["total_items"] == 0
    assert stats["game_hours"] == 0.0
    assert stats["movie_hours"] == 0.0
    assert stats["tv_hours"] == 0.0
    assert stats["book_hours"] == 0.0
    assert stats["total_time_hours"] == 0.0
    assert stats["avg_rating"] == 0.0
    assert stats["completion_rate"] == 0.0
    assert stats["curator_xp"] == 0
    assert stats["curator_level"] == 1
    assert stats["top_genres"] == []
    assert len(stats["monthly_activity"]) == 6


def test_schema_validations_and_edge_cases(client: TestClient, db_session: Session):
    """Test schema validators, edge case updates, and activity date handling."""
    from src.api.v1.schemas import CollectionEntryCreate
    from src.data.models import UserMediaEntry, MediaItem, MediaType, TrackingStatus

    # 1. Validation error when neither media nor media_item_id is provided
    with pytest.raises(ValueError, match="Either 'media' or 'media_item_id' must be provided"):
        CollectionEntryCreate(status=TrackingStatus.PLAN_TO)

    user = register_user(client, "edge_user", "edge@hostcart.local", "password123")
    headers = auth_header(user["access_token"])

    # 2. Create entry initially in plan_to
    cr_resp = client.post(
        "/api/v1/collection",
        json={"media": {"media_type": "game", "title": "Stardew Valley"}, "status": "plan_to"},
        headers=headers,
    )
    assert cr_resp.status_code == 201
    entry_id = cr_resp.json()["id"]
    assert cr_resp.json()["started_at"] is None

    # Update status to in_progress -> sets started_at
    up_resp = client.put(
        f"/api/v1/collection/{entry_id}",
        json={
            "status": "in_progress",
            "current_episode": 2,
            "current_page": 50,
            "rewatch_count": 1,
            "tags": ["relaxing", "farming"],
            "notes": "Year 2 spring",
        },
        headers=headers,
    )
    assert up_resp.status_code == 200
    assert up_resp.json()["started_at"] is not None
    assert up_resp.json()["current_episode"] == 2
    assert up_resp.json()["current_page"] == 50
    assert up_resp.json()["rewatch_count"] == 1
    assert up_resp.json()["tags"] == ["relaxing", "farming"]

    # 3. Old entry created > 1 year ago (outside 6-month monthly_activity window)
    old_item = MediaItem(media_type=MediaType.MOVIE, title="Old Movie")
    db_session.add(old_item)
    db_session.commit()
    db_session.refresh(old_item)

    old_date = datetime.now(timezone.utc) - timedelta(days=400)
    old_entry = UserMediaEntry(
        user_id=user["user"]["id"],
        media_item_id=old_item.id,
        status=TrackingStatus.COMPLETED,
        completed_at=old_date,
        created_at=old_date,
        updated_at=old_date,
    )
    db_session.add(old_entry)
    db_session.commit()

    stats_resp = client.get("/api/v1/collection/stats", headers=headers)
    assert stats_resp.status_code == 200


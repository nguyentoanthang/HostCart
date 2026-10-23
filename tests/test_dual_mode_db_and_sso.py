"""
Unit and integration tests for Sub-Phase 3.1:
Dual-Mode Configuration & PostgreSQL Engine Upgrade.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from typing import Generator, Optional
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from src.core.config import (
    ConfigStore,
    DatabaseConfig,
    HomelabConfig,
    Settings,
    get_config_store,
    get_settings,
    reset_config_store,
)
from src.core.security import create_access_token
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
    "SERVER_HOST",
    "SERVER_PORT",
]


@pytest.fixture(autouse=True)
def clean_dual_mode_env(monkeypatch, tmp_path):
    """Ensure clean environment and reset singletons between each test."""
    reset_config_store()
    reset_engine()

    monkeypatch.setattr("src.core.config.DEFAULT_ENV_PATH", tmp_path / ".empty_env")

    saved_env = {}
    for k in CLEAN_ENV_KEYS:
        if k in os.environ:
            saved_env[k] = os.environ.pop(k)

    yield

    reset_config_store()
    reset_engine()

    for k in CLEAN_ENV_KEYS:
        if k in os.environ:
            os.environ.pop(k)
    for k, v in saved_env.items():
        os.environ[k] = v


# =====================================================================
# 1. Configuration Tests: HomelabConfig Defaults & Overrides
# =====================================================================

def test_homelab_config_defaults():
    """Verify default HomelabConfig settings comply with standalone specifications."""
    default_cfg = HomelabConfig()
    assert default_cfg.deployment_mode == "standalone"
    assert default_cfg.auth_mode == "standalone"
    assert default_cfg.homelab_sso_secret == ""
    assert default_cfg.homelab_internal_token == ""
    assert default_cfg.ai_base_url == "https://openrouter.ai/api/v1"
    assert default_cfg.ai_api_key == ""
    assert default_cfg.ai_model == "openai/gpt-4o-mini"

    # Also verify on Settings
    settings = Settings()
    assert hasattr(settings, "homelab")
    assert settings.homelab.deployment_mode == "standalone"
    assert settings.homelab.auth_mode == "standalone"


def test_homelab_config_env_overrides(tmp_path):
    """Verify environment variables properly override HomelabConfig settings."""
    os.environ["DEPLOYMENT_MODE"] = "homelab"
    os.environ["AUTH_MODE"] = "homelab"
    os.environ["HOMELAB_SSO_SECRET"] = "secret-sso-key-32bytes-long-min"
    os.environ["HOMELAB_INTERNAL_TOKEN"] = "internal-service-token-32bytes"
    os.environ["AI_BASE_URL"] = "http://ai-gateway:4000/v1"
    os.environ["AI_API_KEY"] = "sk-direct-ai-key-12345"
    os.environ["AI_MODEL"] = "anthropic/claude-3-5-sonnet"

    store = ConfigStore(config_path=tmp_path / "empty.json", env_file=None)
    settings = store.get_settings()

    assert settings.homelab.deployment_mode == "homelab"
    assert settings.homelab.auth_mode == "homelab"
    assert settings.homelab.homelab_sso_secret == "secret-sso-key-32bytes-long-min"
    assert settings.homelab.homelab_internal_token == "internal-service-token-32bytes"
    assert settings.homelab.ai_base_url == "http://ai-gateway:4000/v1"
    assert settings.homelab.ai_api_key == "sk-direct-ai-key-12345"
    assert settings.homelab.ai_model == "anthropic/claude-3-5-sonnet"


def test_homelab_ai_key_openrouter_fallback(tmp_path):
    """Verify OPENROUTER_API_KEY serves as fallback when AI_API_KEY is not set."""
    os.environ["OPENROUTER_API_KEY"] = "sk-openrouter-key-999"
    if "AI_API_KEY" in os.environ:
        os.environ.pop("AI_API_KEY")

    store = ConfigStore(config_path=tmp_path / "empty.json", env_file=None)
    settings = store.get_settings()
    assert settings.homelab.ai_api_key == "sk-openrouter-key-999"

    # When both are present, AI_API_KEY takes precedence
    os.environ["AI_API_KEY"] = "sk-ai-primary-key"
    store2 = ConfigStore(config_path=tmp_path / "empty.json", env_file=None)
    settings2 = store2.get_settings()
    assert settings2.homelab.ai_api_key == "sk-ai-primary-key"


# =====================================================================
# 2. DatabaseConfig Path & URL Resolution Tests
# =====================================================================

def test_database_config_resolved_path_sqlite_and_postgres(tmp_path):
    """Test get_resolved_path with SQLite paths, :memory:, and PostgreSQL URLs."""
    # Memory
    mem_cfg = DatabaseConfig(db_file=":memory:")
    assert mem_cfg.get_resolved_path() == Path(":memory:")

    # Local file path
    rel_cfg = DatabaseConfig(db_file="data/hostcart.db")
    resolved = rel_cfg.get_resolved_path(root=tmp_path)
    assert resolved == (tmp_path / "data" / "hostcart.db").resolve()

    # Absolute path
    abs_path = (tmp_path / "local.db").resolve()
    abs_cfg = DatabaseConfig(db_file=str(abs_path))
    assert abs_cfg.get_resolved_path() == abs_path

    # PostgreSQL URLs (must safely return Path without breaking on Windows)
    pg_urls = [
        "postgres://homelab:secret@postgres:5432/hostcart_db",
        "postgresql://homelab:secret@postgres:5432/hostcart_db",
        "postgresql+psycopg://homelab:secret@postgres:5432/hostcart_db",
    ]
    for url in pg_urls:
        cfg = DatabaseConfig(db_file=url)
        res = cfg.get_resolved_path()
        assert isinstance(res, Path)
        assert res == Path(url)


# =====================================================================
# 3. Database Engine & Backend Detection Tests
# =====================================================================

def test_get_database_backend_sqlite():
    """Verify get_database_backend returns 'sqlite' for default and in-memory engines."""
    mem_engine = get_engine(":memory:")
    assert get_database_backend(mem_engine) == "sqlite"

    # Calling without argument inspects active default engine
    assert get_database_backend() == "sqlite"
    mem_engine.dispose()


def test_get_engine_postgresql_url_normalization():
    """Verify postgres:// and postgresql:// are normalized to postgresql+psycopg://."""
    urls = [
        ("postgres://user:pass@localhost:5432/testdb", "postgresql+psycopg://user:***@localhost:5432/testdb"),
        ("postgresql://user:pass@localhost:5432/testdb", "postgresql+psycopg://user:***@localhost:5432/testdb"),
        ("postgresql+psycopg://user:pass@localhost:5432/testdb", "postgresql+psycopg://user:***@localhost:5432/testdb"),
    ]

    for input_url, expected_str in urls:
        eng = get_engine(input_url)
        try:
            assert str(eng.url) == expected_str
            assert eng.dialect.name == "postgresql"
            assert get_database_backend(eng) == "postgresql"
        finally:
            eng.dispose()


def test_get_engine_path_object_with_postgres_url():
    """Verify get_engine safely handles Path objects containing postgres URLs on Windows."""
    pg_path = Path("postgresql://user:pass@localhost:5432/testdb")
    eng = get_engine(pg_path)
    try:
        assert eng.dialect.name == "postgresql"
        assert "postgresql+psycopg" in str(eng.url)
        assert get_database_backend(eng) == "postgresql"
    finally:
        eng.dispose()


def test_get_engine_cached_default_from_database_url_env(tmp_path):
    """Verify DATABASE_URL env sets default engine to PostgreSQL and caches it."""
    os.environ["DATABASE_URL"] = "postgresql://homelab:secret@postgres:5432/hostcart_db"

    reset_config_store()
    reset_engine()

    eng1 = get_engine()
    try:
        assert eng1.dialect.name == "postgresql"
        assert get_database_backend() == "postgresql"
        assert get_database_backend(eng1) == "postgresql"

        # Verify caching
        eng2 = get_engine()
        assert eng1 is eng2
    finally:
        reset_engine()


def test_get_database_backend_mock_dialect():
    """Verify get_database_backend detects dialect name and url scheme edge cases."""
    mock_pg_engine = MagicMock()
    mock_pg_engine.dialect.name = "postgresql"
    mock_pg_engine.url = "postgresql+psycopg://dummy"
    assert get_database_backend(mock_pg_engine) == "postgresql"

    mock_fallback_engine = MagicMock()
    mock_fallback_engine.dialect.name = "custom"
    mock_fallback_engine.url = "postgres://dummy"
    assert get_database_backend(mock_fallback_engine) == "postgresql"

    mock_sqlite_engine = MagicMock()
    mock_sqlite_engine.dialect.name = "sqlite"
    mock_sqlite_engine.url = "sqlite:///:memory:"
    assert get_database_backend(mock_sqlite_engine) == "sqlite"


# =====================================================================
# 4. Backward Compatibility: SQLite Operations Unaltered
# =====================================================================

def test_sqlite_crud_backward_compatibility():
    """Ensure in-memory SQLite tables, sessions, and CRUD operations remain 100% functional."""
    engine = get_engine(":memory:")
    init_db(engine)

    with Session(engine) as session:
        user = User(
            username="dualmode_tester",
            email="tester@homelab.local",
            hashed_password="test_hash_123",
            is_admin=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        assert user.id is not None

        # Query back
        stmt = select(User).where(User.username == "dualmode_tester")
        found = session.exec(stmt).first()
        assert found is not None
        assert found.email == "tester@homelab.local"
        assert found.is_admin is True

    engine.dispose()


# =====================================================================
# 5. Sub-Phase 3.2: Homelab SSO Authentication, OBO & JIT Provisioning
# =====================================================================

TEST_SSO_SECRET = "test-homelab-sso-secret-32bytes-key-1234"
TEST_INTERNAL_TOKEN = "test-homelab-internal-token-32bytes-secret"


@pytest.fixture(name="db_session")
def db_session_fixture() -> Generator[Session, None, None]:
    """Provide an isolated in-memory SQLite database session for endpoint tests."""
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
    """Provide a TestClient with database session overridden by db_session."""
    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_sso_jwt(
    username: str,
    secret: str = TEST_SSO_SECRET,
    is_admin: bool = False,
    allowed_apps: Optional[list] = None,
    email: Optional[str] = None,
    expires_in_hours: int = 24,
) -> str:
    """Helper to generate a valid or custom Homelab SSO JWT for testing."""
    if allowed_apps is None:
        allowed_apps = ["hostcart"]
    now = datetime.now(timezone.utc)
    payload = {
        "iss": "homelab-dashboard",
        "sub": f"user-{username}",
        "username": username,
        "email": email or f"{username.lower()}@homelab.local",
        "display_name": username.title(),
        "is_admin": is_admin,
        "allowed_apps": allowed_apps,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=expires_in_hours)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_homelab_sso_cookie_auto_creates_user_and_accesses_endpoints(client, db_session):
    """
    Verify that a valid homelab_sso cookie auto-provisions a new User in HostCart
    and grants access to /api/v1/auth/me and /api/v1/collection.
    """
    os.environ["AUTH_MODE"] = "homelab"
    os.environ["HOMELAB_SSO_SECRET"] = TEST_SSO_SECRET
    reset_config_store()

    sso_token = make_sso_jwt("alice_sso", allowed_apps=["hostcart"])

    # 1. Access /api/v1/auth/me with homelab_sso cookie
    me_resp = client.get("/api/v1/auth/me", headers={"Cookie": f"homelab_sso={sso_token}"})
    assert me_resp.status_code == 200, me_resp.text
    user_data = me_resp.json()
    assert user_data["username"] == "alice_sso"
    assert user_data["email"] == "alice_sso@homelab.local"
    assert user_data["is_admin"] is False
    assert user_data["id"] is not None

    # 2. Check local DB User was JIT-provisioned
    user_row = db_session.exec(select(User).where(User.username == "alice_sso")).first()
    assert user_row is not None
    assert user_row.hashed_password == "<sso-managed>"
    assert user_row.is_admin is False

    # 3. Access /api/v1/collection with homelab_sso cookie
    col_resp = client.get("/api/v1/collection", headers={"Cookie": f"homelab_sso={sso_token}"})
    assert col_resp.status_code == 200, col_resp.text
    assert col_resp.json() == []


def test_homelab_sso_admin_grants_admin_privileges(client, db_session):
    """
    Verify that is_admin=True in the SSO JWT grants admin privileges in HostCart
    (/api/v1/auth/admin-only), bypassing the allowed_apps list.
    """
    os.environ["AUTH_MODE"] = "homelab"
    os.environ["HOMELAB_SSO_SECRET"] = TEST_SSO_SECRET
    reset_config_store()

    # Admin user: allowed_apps does not have "hostcart", but is_admin=True grants access
    admin_token = make_sso_jwt("super_boss", is_admin=True, allowed_apps=["dashboard"])
    admin_resp = client.get("/api/v1/auth/admin-only", headers={"Cookie": f"homelab_sso={admin_token}"})
    assert admin_resp.status_code == 200, admin_resp.text
    assert admin_resp.json()["username"] == "super_boss"
    assert admin_resp.json()["is_admin"] is True

    # Regular non-admin user
    reg_token = make_sso_jwt("regular_joe", is_admin=False, allowed_apps=["hostcart"])
    reg_resp = client.get("/api/v1/auth/admin-only", headers={"Cookie": f"homelab_sso={reg_token}"})
    assert reg_resp.status_code == 403
    assert "Admin privileges required" in reg_resp.json()["detail"]


def test_homelab_sso_user_without_hostcart_app_forbidden(client):
    """
    Verify that a user without 'hostcart' in allowed_apps and is_admin=False receives 403 Forbidden.
    """
    os.environ["AUTH_MODE"] = "homelab"
    os.environ["HOMELAB_SSO_SECRET"] = TEST_SSO_SECRET
    reset_config_store()

    token = make_sso_jwt("bontalk_only_user", is_admin=False, allowed_apps=["bontalk", "dashboard"])

    # GET /auth/me -> 403
    resp_me = client.get("/api/v1/auth/me", headers={"Cookie": f"homelab_sso={token}"})
    assert resp_me.status_code == 403
    assert "HostCart access not permitted for this user" in resp_me.json()["detail"]

    # GET /collection -> 403
    resp_col = client.get("/api/v1/collection", headers={"Cookie": f"homelab_sso={token}"})
    assert resp_col.status_code == 403

    # GET /auth/sso-session -> 403
    resp_sso = client.get("/api/v1/auth/sso-session", headers={"Cookie": f"homelab_sso={token}"})
    assert resp_sso.status_code == 403


def test_service_to_service_obo_auth_and_collection_isolation(client, db_session):
    """
    Verify that service-to-service X-Homelab-Token + X-Homelab-User authenticates
    on behalf of that specific user and strictly isolates each user's collection.
    """
    os.environ["AUTH_MODE"] = "homelab"
    os.environ["HOMELAB_INTERNAL_TOKEN"] = TEST_INTERNAL_TOKEN
    reset_config_store()

    headers_user1 = {
        "X-Homelab-Token": TEST_INTERNAL_TOKEN,
        "X-Homelab-User": "obo_agent_1",
    }
    headers_user2 = {
        "X-Homelab-Token": TEST_INTERNAL_TOKEN,
        "X-Homelab-User": "obo_agent_2",
    }

    # 1. User 1 authenticates and JIT user is created
    resp1 = client.get("/api/v1/auth/me", headers=headers_user1)
    assert resp1.status_code == 200, resp1.text
    user1_id = resp1.json()["id"]
    assert resp1.json()["username"] == "obo_agent_1"

    # Add a MediaItem and UserMediaEntry for user 1 directly in DB
    media = MediaItem(media_type=MediaType.GAME, title="Cyberpunk 2077")
    db_session.add(media)
    db_session.commit()
    db_session.refresh(media)

    entry = UserMediaEntry(
        user_id=user1_id,
        media_item_id=media.id,
        status=TrackingStatus.IN_PROGRESS,
        playtime_hours=35.0,
    )
    db_session.add(entry)
    db_session.commit()

    # 2. Query user 1's collection via OBO headers
    col1 = client.get("/api/v1/collection", headers=headers_user1)
    assert col1.status_code == 200, col1.text
    items1 = col1.json()
    assert len(items1) == 1
    assert items1[0]["media"]["title"] == "Cyberpunk 2077"

    # 3. Query user 2's collection via OBO headers
    col2 = client.get("/api/v1/collection", headers=headers_user2)
    assert col2.status_code == 200, col2.text
    items2 = col2.json()
    assert len(items2) == 0  # Strictly isolated from user 1!

    # Verify user 2 was also JIT-created
    resp2 = client.get("/api/v1/auth/me", headers=headers_user2)
    assert resp2.status_code == 200
    assert resp2.json()["username"] == "obo_agent_2"
    assert resp2.json()["id"] != user1_id


def test_service_to_service_invalid_internal_token_returns_401(client):
    """Verify that service-to-service with invalid or missing internal token returns 401."""
    os.environ["AUTH_MODE"] = "homelab"
    os.environ["HOMELAB_INTERNAL_TOKEN"] = TEST_INTERNAL_TOKEN
    reset_config_store()

    # Bad token
    headers_bad = {
        "X-Homelab-Token": "completely-invalid-internal-secret",
        "X-Homelab-User": "some_user",
    }
    resp = client.get("/api/v1/auth/me", headers=headers_bad)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid internal service token"

    # Empty internal token configured in system
    os.environ["HOMELAB_INTERNAL_TOKEN"] = ""
    reset_config_store()
    resp_empty = client.get("/api/v1/auth/me", headers=headers_bad)
    assert resp_empty.status_code == 401
    assert resp_empty.json()["detail"] == "Invalid internal service token"


def test_service_to_service_missing_user_header_returns_401(client):
    """Verify that service-to-service with missing or blank X-Homelab-User returns 401."""
    os.environ["AUTH_MODE"] = "homelab"
    os.environ["HOMELAB_INTERNAL_TOKEN"] = TEST_INTERNAL_TOKEN
    reset_config_store()

    # Missing header
    headers_no_user = {"X-Homelab-Token": TEST_INTERNAL_TOKEN}
    resp = client.get("/api/v1/auth/me", headers=headers_no_user)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing X-Homelab-User header"

    # Blank header
    headers_blank = {"X-Homelab-Token": TEST_INTERNAL_TOKEN, "X-Homelab-User": "   "}
    resp_blank = client.get("/api/v1/auth/me", headers=headers_blank)
    assert resp_blank.status_code == 401
    assert resp_blank.json()["detail"] == "Missing X-Homelab-User header"


def test_service_to_service_is_admin_header(client, db_session):
    """Verify that X-Homelab-Is-Admin header accurately sets and syncs is_admin status."""
    os.environ["AUTH_MODE"] = "homelab"
    os.environ["HOMELAB_INTERNAL_TOKEN"] = TEST_INTERNAL_TOKEN
    reset_config_store()

    # 1. Provision user as admin
    headers_admin = {
        "X-Homelab-Token": TEST_INTERNAL_TOKEN,
        "X-Homelab-User": "obo_super_admin",
        "X-Homelab-Is-Admin": "true",
    }
    resp = client.get("/api/v1/auth/admin-only", headers=headers_admin)
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_admin"] is True

    # 2. Later call with X-Homelab-Is-Admin: false syncs user to non-admin
    headers_demoted = {
        "X-Homelab-Token": TEST_INTERNAL_TOKEN,
        "X-Homelab-User": "obo_super_admin",
        "X-Homelab-Is-Admin": "false",
    }
    resp_demoted = client.get("/api/v1/auth/admin-only", headers=headers_demoted)
    assert resp_demoted.status_code == 403
    assert "Admin privileges required" in resp_demoted.json()["detail"]

    # Check database state
    user_db = db_session.exec(select(User).where(User.username == "obo_super_admin")).first()
    assert user_db is not None
    assert user_db.is_admin is False


def test_public_register_blocked_in_homelab_mode_but_works_in_standalone(client):
    """
    Verify public /register is blocked (403) when AUTH_MODE=homelab,
    but functions normally when AUTH_MODE=standalone.
    """
    reg_payload = {
        "username": "fresh_user",
        "email": "fresh_user@example.com",
        "password": "strongpassword123",
    }

    # 1. In homelab mode -> 403
    os.environ["AUTH_MODE"] = "homelab"
    reset_config_store()
    resp_blocked = client.post("/api/v1/auth/register", json=reg_payload)
    assert resp_blocked.status_code == 403
    assert "Registration is managed centrally by Homelab Dashboard" in resp_blocked.json()["detail"]

    # 2. In standalone mode -> 201 Created
    os.environ["AUTH_MODE"] = "standalone"
    reset_config_store()
    resp_allowed = client.post("/api/v1/auth/register", json=reg_payload)
    assert resp_allowed.status_code == 201, resp_allowed.text
    body = resp_allowed.json()
    assert "access_token" in body
    assert body["user"]["username"] == "fresh_user"


def test_sso_session_endpoint_exchange(client):
    """
    Verify GET /api/v1/auth/sso-session returns TokenResponse when a valid
    homelab_sso cookie is present, and the returned local token can be used.
    """
    os.environ["AUTH_MODE"] = "homelab"
    os.environ["HOMELAB_SSO_SECRET"] = TEST_SSO_SECRET
    reset_config_store()

    sso_token = make_sso_jwt("frontend_auto_user")

    # 1. Exchange SSO cookie for local TokenResponse
    exchange_resp = client.get("/api/v1/auth/sso-session", headers={"Cookie": f"homelab_sso={sso_token}"})
    assert exchange_resp.status_code == 200, exchange_resp.text
    session_data = exchange_resp.json()
    assert "access_token" in session_data
    assert session_data["token_type"] == "bearer"
    assert session_data["user"]["username"] == "frontend_auto_user"

    local_token = session_data["access_token"]

    # 2. Use the local access token via Path C fallback
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {local_token}"})
    assert me_resp.status_code == 200, me_resp.text
    assert me_resp.json()["username"] == "frontend_auto_user"

    # 3. Call sso-session without active SSO session -> 401
    no_session_resp = client.get("/api/v1/auth/sso-session")
    assert no_session_resp.status_code == 401
    assert "No active Homelab SSO session found" in no_session_resp.json()["detail"]

    # 4. In standalone mode -> 401
    os.environ["AUTH_MODE"] = "standalone"
    reset_config_store()
    standalone_resp = client.get("/api/v1/auth/sso-session", headers={"Cookie": f"homelab_sso={sso_token}"})
    assert standalone_resp.status_code == 401
    assert "No active Homelab SSO session found" in standalone_resp.json()["detail"]


def test_sso_headers_bearer_and_error_handling(client):
    """
    Verify SSO token resolution via X-Homelab-SSO-Token header, Bearer header,
    and appropriate error responses for expired or tampered tokens.
    """
    os.environ["AUTH_MODE"] = "homelab"
    os.environ["HOMELAB_SSO_SECRET"] = TEST_SSO_SECRET
    reset_config_store()

    # 1. Via X-Homelab-SSO-Token header
    token_hdr = make_sso_jwt("header_agent")
    resp_hdr = client.get("/api/v1/auth/me", headers={"X-Homelab-SSO-Token": token_hdr})
    assert resp_hdr.status_code == 200
    assert resp_hdr.json()["username"] == "header_agent"

    # 2. Via Authorization: Bearer <sso_jwt>
    token_bearer = make_sso_jwt("bearer_agent")
    resp_bearer = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_bearer}"})
    assert resp_bearer.status_code == 200
    assert resp_bearer.json()["username"] == "bearer_agent"

    # 3. Expired SSO token in cookie -> 401
    expired_token = make_sso_jwt("expired_agent", expires_in_hours=-5)
    resp_exp = client.get("/api/v1/auth/me", headers={"Cookie": f"homelab_sso={expired_token}"})
    assert resp_exp.status_code == 401
    assert "Invalid or expired SSO token" in resp_exp.json()["detail"]

    # 4. Tampered / wrong secret SSO token in cookie -> 401
    tampered_token = make_sso_jwt("tampered_agent", secret="wrong-secret-key-32bytes-padding!")
    resp_tamp = client.get("/api/v1/auth/me", headers={"Cookie": f"homelab_sso={tampered_token}"})
    assert resp_tamp.status_code == 401
    assert "Invalid or expired SSO token" in resp_tamp.json()["detail"]

    # 5. Invalid SSO token payload (missing username)
    now = datetime.now(timezone.utc)
    bad_payload = {
        "iss": "homelab-dashboard",
        "allowed_apps": ["hostcart"],
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    bad_payload_token = jwt.encode(bad_payload, TEST_SSO_SECRET, algorithm="HS256")
    resp_bad = client.get("/api/v1/auth/me", headers={"Cookie": f"homelab_sso={bad_payload_token}"})
    assert resp_bad.status_code == 401
    assert "Invalid SSO token payload" in resp_bad.json()["detail"]


def test_standalone_mode_unaffected_by_homelab_headers(client, db_session):
    """
    Ensure zero regressions in standalone mode: X-Homelab-* headers and homelab_sso
    cookies are ignored, and normal standalone Bearer auth functions unaltered.
    """
    os.environ["AUTH_MODE"] = "standalone"
    reset_config_store()

    # 1. Calling with X-Homelab-Token in standalone mode does not bypass auth
    headers = {
        "X-Homelab-Token": TEST_INTERNAL_TOKEN,
        "X-Homelab-User": "attacker",
    }
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authentication credentials were not provided"

    # 2. Calling with homelab_sso cookie in standalone mode does not bypass auth
    sso_token = make_sso_jwt("attacker")
    resp_cookie = client.get("/api/v1/auth/me", headers={"Cookie": f"homelab_sso={sso_token}"})
    assert resp_cookie.status_code == 401
    assert resp_cookie.json()["detail"] == "Authentication credentials were not provided"

    # 3. Standard user registration and Bearer login works as expected
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": "standalone_user", "email": "sa@example.com", "password": "password123"},
    )
    assert reg.status_code == 201
    token = reg.json()["access_token"]

    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "standalone_user"


def test_sso_session_alternative_headers_and_email_sync(client, db_session):
    """
    Verify sso-session with X-Homelab-SSO-Token header, Bearer header, local token,
    and verify email synchronization on existing SSO user.
    """
    os.environ["AUTH_MODE"] = "homelab"
    os.environ["HOMELAB_SSO_SECRET"] = TEST_SSO_SECRET
    reset_config_store()

    # 1. Calling /sso-session with X-Homelab-SSO-Token header
    token1 = make_sso_jwt("header_sso_user", email="initial@homelab.local")
    resp_hdr = client.get("/api/v1/auth/sso-session", headers={"X-Homelab-SSO-Token": token1})
    assert resp_hdr.status_code == 200
    assert resp_hdr.json()["user"]["username"] == "header_sso_user"
    assert resp_hdr.json()["user"]["email"] == "initial@homelab.local"

    # Verify user exists in DB with initial email
    user_db = db_session.exec(select(User).where(User.username == "header_sso_user")).first()
    assert user_db is not None
    assert user_db.email == "initial@homelab.local"

    # 2. Calling with updated email in SSO JWT syncs email on existing user
    token2 = make_sso_jwt("header_sso_user", email="updated@homelab.local")
    resp_sync = client.get("/api/v1/auth/sso-session", headers={"X-Homelab-SSO-Token": token2})
    assert resp_sync.status_code == 200
    assert resp_sync.json()["user"]["email"] == "updated@homelab.local"

    db_session.refresh(user_db)
    assert user_db.email == "updated@homelab.local"

    # 3. Calling /sso-session with Authorization: Bearer <sso_jwt>
    resp_bearer = client.get("/api/v1/auth/sso-session", headers={"Authorization": f"Bearer {token2}"})
    assert resp_bearer.status_code == 200
    assert resp_bearer.json()["user"]["username"] == "header_sso_user"

    # 4. Calling /sso-session with active local token
    local_tok = resp_bearer.json()["access_token"]
    resp_local = client.get("/api/v1/auth/sso-session", headers={"Authorization": f"Bearer {local_tok}"})
    assert resp_local.status_code == 200
    assert resp_local.json()["user"]["username"] == "header_sso_user"


def test_homelab_auth_edge_cases(client, db_session):
    """
    Test edge cases in homelab mode: missing SSO secret when cookie provided,
    invalid user ID in local token fallback, user deleted after local token created.
    """
    os.environ["AUTH_MODE"] = "homelab"
    os.environ["HOMELAB_SSO_SECRET"] = ""
    reset_config_store()

    # When HOMELAB_SSO_SECRET is empty and cookie is passed -> 401
    sso_token = make_sso_jwt("some_user")
    resp_nosecret = client.get("/api/v1/auth/me", headers={"Cookie": f"homelab_sso={sso_token}"})
    assert resp_nosecret.status_code == 401

    # Local token with non-existent user in homelab mode -> 401
    ghost_token = create_access_token({"sub": "999999", "username": "ghost"})
    resp_ghost = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ghost_token}"})
    assert resp_ghost.status_code == 401
    assert "User not found" in resp_ghost.json()["detail"]

    # Local token with non-int user ID in homelab mode -> 401
    bad_id_token = create_access_token({"sub": "not-an-int", "username": "bad"})
    resp_bad_id = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bad_id_token}"})
    assert resp_bad_id.status_code == 401
    assert "Invalid user ID" in resp_bad_id.json()["detail"]



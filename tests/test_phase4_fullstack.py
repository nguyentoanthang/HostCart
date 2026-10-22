"""
Phase 4 Full-Stack Integration Test Suite.
Tests the compiled React SPA mounting in FastAPI, client-side route fallback,
static asset serving, API route preservation, and end-to-end fullstack workflows.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from src.data.database import get_session, init_db
from src.main import app, create_app


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
    """Provide a TestClient with database session overridden by db_session."""
    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_frontend_dist_artifacts_exist():
    """Verify that the frontend build artifacts (index.html, assets) exist on disk."""
    project_root = Path(__file__).resolve().parents[1]
    frontend_dist = project_root / "frontend" / "dist"
    index_file = frontend_dist / "index.html"
    assets_dir = frontend_dist / "assets"

    assert frontend_dist.is_dir(), f"Frontend dist folder {frontend_dist} must exist"
    assert index_file.is_file(), f"Frontend {index_file} must exist"
    assert assets_dir.is_dir(), f"Frontend assets folder {assets_dir} must exist"

    content = index_file.read_text(encoding="utf-8")
    assert '<div id="root">' in content
    assert "HostCart" in content


def test_spa_index_served_at_root(client: TestClient):
    """Test that GET / serves frontend/dist/index.html with HTML content-type."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<div id="root">' in response.text
    assert "HostCart" in response.text


def test_spa_fallback_for_client_routes(client: TestClient):
    """Test that arbitrary client-side SPA routes (e.g., /stats, /games) return index.html."""
    for route in ["/stats", "/games", "/movies", "/settings", "/curator/dashboard"]:
        response = client.get(route)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert '<div id="root">' in response.text


def test_api_health_endpoint_preserved(client: TestClient):
    """Test that the core API health probe /api/health is preserved and not intercepted."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok", "app": "HostCart"}


def test_api_404_not_masked_by_spa(client: TestClient):
    """Test that non-existent API routes return 404 JSON and are NOT masked by index.html."""
    response = client.get("/api/v1/nonexistent_endpoint")
    assert response.status_code == 404
    assert "text/html" not in response.headers.get("content-type", "")


def test_api_docs_and_openapi_not_masked(client: TestClient):
    """Test that OpenAPI documentation routes are accessible and not masked by SPA."""
    docs_resp = client.get("/docs")
    assert docs_resp.status_code == 200
    assert "text/html" in docs_resp.headers["content-type"]

    openapi_resp = client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    openapi_data = openapi_resp.json()
    assert "openapi" in openapi_data
    assert openapi_data["info"]["title"] == "HostCart Multi-Media Rebuild"


def test_static_assets_serving(client: TestClient):
    """Test that static CSS and JS files in dist/assets are served properly."""
    project_root = Path(__file__).resolve().parents[1]
    assets_dir = project_root / "frontend" / "dist" / "assets"

    asset_files = list(assets_dir.glob("*.*"))
    assert len(asset_files) > 0, "There should be compiled asset files"

    test_asset = asset_files[0]
    asset_url = f"/assets/{test_asset.name}"

    response = client.get(asset_url)
    assert response.status_code == 200
    assert len(response.content) > 0


def test_direct_file_serving_from_dist(client: TestClient):
    """Test that direct file requests (e.g., /index.html) serve the file directly."""
    response = client.get("/index.html")
    assert response.status_code == 200
    assert '<div id="root">' in response.text


def test_app_creation_without_dist_directory():
    """Test that create_app initializes cleanly even when frontend/dist does not exist."""
    with patch("pathlib.Path.is_dir", return_value=False):
        fallback_app = create_app()
        assert fallback_app is not None
        assert fallback_app.title == "HostCart Multi-Media Rebuild"


def test_fullstack_api_workflow(client: TestClient):
    """Test end-to-end user registration, item creation, stats, and export via FastAPI."""
    # 1. Register user
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": "phase4curator",
            "email": "phase4@example.com",
            "password": "Password123!",
        },
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Add Game item
    create_resp = client.post(
        "/api/v1/collection",
        headers=headers,
        json={
            "media": {
                "media_type": "game",
                "title": "Cyberpunk 2077",
                "release_year": 2020,
                "genres": ["Action", "RPG"],
                "creators": ["CD Projekt Red"],
            },
            "status": "in_progress",
            "rating": 9.5,
            "playtime_hours": 25.0,
        },
    )
    assert create_resp.status_code == 201
    entry_id = create_resp.json()["id"]

    # 3. Increment progress (+5 hrs)
    inc_resp = client.post(
        f"/api/v1/collection/{entry_id}/increment",
        headers=headers,
        json={"amount": 5.0},
    )
    assert inc_resp.status_code == 200
    assert inc_resp.json()["playtime_hours"] == 30.0

    # 4. Fetch Collection Stats
    stats_resp = client.get("/api/v1/collection/stats", headers=headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_items"] == 1
    assert stats["game_hours"] == 30.0
    assert stats["status_counts"]["in_progress"] == 1

    # 5. Export collection
    export_resp = client.get("/api/v1/import-export/export?format=json", headers=headers)
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert len(export_data) == 1
    assert export_data[0]["media"]["title"] == "Cyberpunk 2077"

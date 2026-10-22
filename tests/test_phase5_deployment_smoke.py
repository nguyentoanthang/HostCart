"""
Phase 5 Deployment & End-to-End Regression Smoke Test Suite.
Validates:
1. Dockerfile, docker-compose.yml, .env.example, README.md specification.
2. Complete Live Smoke Workflow:
   - HTTP 200 on SPA root '/', '/api/health', and '/docs'
   - User registration and JWT login
   - Creation of items across all 4 media types (game, movie, tv_show, book)
   - Quick progress increments (+1) on game, tv_show, and book
   - Analytics verification on '/api/v1/collection/stats'
   - Full collection JSON & CSV exports
"""

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.core.config import reset_config_store
from src.data.database import get_session, init_db, reset_engine
from src.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------------------
# 1. Packaging & Deployment File Specifications
# ------------------------------------------------------------------------------

def test_dockerfile_structure_and_multistage_spec():
    """Verify Dockerfile contains proper multi-stage build, ports, volumes, and entrypoint."""
    dockerfile_path = PROJECT_ROOT / "Dockerfile"
    assert dockerfile_path.is_file(), "Dockerfile must exist at project root"

    content = dockerfile_path.read_text(encoding="utf-8")
    # Stage 1: Frontend builder
    assert "FROM node:22-alpine AS frontend-builder" in content
    assert "WORKDIR /build/frontend" in content
    assert "COPY frontend/package*.json ./" in content
    assert "RUN npm install" in content
    assert "RUN npm run build" in content

    # Stage 2: Python runtime
    assert "FROM python:3.12-slim" in content
    assert "WORKDIR /app" in content
    assert "ENV PYTHONUNBUFFERED=1" in content
    assert "COPY requirements.txt ." in content
    assert "RUN pip install --no-cache-dir -r requirements.txt" in content
    assert "COPY --from=frontend-builder /build/frontend/dist ./frontend/dist" in content
    assert "EXPOSE 8000" in content
    assert 'VOLUME ["/app/data", "/app/config"]' in content
    assert 'CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]' in content


def test_docker_compose_specification():
    """Verify docker-compose.yml defines hostcart service with required mappings."""
    compose_path = PROJECT_ROOT / "docker-compose.yml"
    assert compose_path.is_file(), "docker-compose.yml must exist at project root"

    content = compose_path.read_text(encoding="utf-8")
    assert "services:" in content
    assert "hostcart:" in content
    assert "container_name: hostcart" in content
    assert "restart: unless-stopped" in content
    assert '"8000:8000"' in content
    assert "./data:/app/data" in content
    assert "./config:/app/config" in content
    assert "HOST=0.0.0.0" in content
    assert "PORT=8000" in content


def test_env_example_template():
    """Verify .env.example contains all required configuration variables."""
    env_example_path = PROJECT_ROOT / ".env.example"
    assert env_example_path.is_file(), ".env.example must exist at project root"

    content = env_example_path.read_text(encoding="utf-8")
    assert "SECRET_KEY=" in content
    assert "SERVER_HOST=" in content
    assert "SERVER_PORT=" in content
    assert "IGDB_CLIENT_ID=" in content
    assert "IGDB_CLIENT_SECRET=" in content
    assert "TMDB_API_KEY=" in content
    assert "GOOGLE_BOOKS_API_KEY=" in content


def test_readme_documentation_completeness():
    """Verify README.md contains professional documentation covering all pillars."""
    readme_path = PROJECT_ROOT / "README.md"
    assert readme_path.is_file(), "README.md must exist at project root"

    content = readme_path.read_text(encoding="utf-8")
    assert "HostCart" in content
    assert "Arcadia" in content
    assert "Video Games" in content
    assert "Movies" in content
    assert "TV Shows" in content
    assert "Books" in content
    assert "docker compose up -d" in content
    assert "pytest" in content
    assert "90%" in content or "95." in content


# ------------------------------------------------------------------------------
# 2. Comprehensive Live Smoke Test
# ------------------------------------------------------------------------------

@pytest.fixture
def smoke_client(tmp_path):
    """Provide an isolated FastAPI TestClient with fresh SQLite database."""
    test_db_file = tmp_path / "smoke_hostcart.db"
    test_config_file = tmp_path / "smoke_config.json"

    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_file.as_posix()}"
    os.environ["SECRET_KEY"] = "super-secret-smoke-test-key-minimum-32-bytes!!"

    reset_config_store()
    reset_engine()
    init_db()

    app = create_app()
    with TestClient(app) as client:
        yield client

    reset_engine()
    reset_config_store()
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("SECRET_KEY", None)


def test_end_to_end_deployment_smoke_flow(smoke_client: TestClient):
    """
    Execute full end-to-end smoke verification:
    1. Root SPA, Health check, and OpenAPI Docs
    2. User registration and authentication
    3. Multi-media additions across all 4 media types
    4. Progress incrementations (+1)
    5. Statistics analytics engine
    6. Collection JSON and CSV export
    """
    # 1. Probes & Static UI
    # Health endpoint
    res_health = smoke_client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "ok", "app": "HostCart"}

    # OpenAPI docs
    res_docs = smoke_client.get("/docs")
    assert res_docs.status_code == 200

    # SPA Root
    res_root = smoke_client.get("/")
    assert res_root.status_code == 200
    assert "text/html" in res_root.headers.get("content-type", "")

    # 2. Authentication: Register and Login
    reg_payload = {
        "username": "arcadia_collector",
        "email": "arcadia@hostcart.local",
        "password": "SecurePassword123!",
    }
    res_reg = smoke_client.post("/api/v1/auth/register", json=reg_payload)
    assert res_reg.status_code == 201
    reg_data = res_reg.json()
    assert reg_data["user"]["username"] == "arcadia_collector"
    assert "access_token" in reg_data

    login_payload = {
        "username": "arcadia_collector",
        "password": "SecurePassword123!",
    }
    res_login = smoke_client.post("/api/v1/auth/login", json=login_payload)
    assert res_login.status_code == 200
    token_data = res_login.json()
    assert "access_token" in token_data
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify current user endpoint
    res_me = smoke_client.get("/api/v1/auth/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "arcadia@hostcart.local"

    # 3. Add Media Entries Across All 4 Media Types
    # A. Video Game
    game_payload = {
        "media": {
            "title": "Elden Ring",
            "media_type": "game",
            "release_year": 2022,
            "genres": ["Action RPG", "Open World"],
            "poster_url": "https://example.com/eldenring.jpg",
            "summary": "An open world action RPG set in the Lands Between.",
        },
        "status": "in_progress",
        "rating": 9.5,
        "notes": "Exploring the Lands Between",
        "tags": ["favorite", "goty"],
        "playtime_hours": 15.0,
    }
    res_game = smoke_client.post("/api/v1/collection", json=game_payload, headers=headers)
    assert res_game.status_code == 201
    game_id = res_game.json()["id"]

    # B. Movie
    movie_payload = {
        "media": {
            "title": "Blade Runner 2049",
            "media_type": "movie",
            "release_year": 2017,
            "genres": ["Sci-Fi", "Neo-Noir"],
            "poster_url": "https://example.com/br2049.jpg",
            "summary": "Young Blade Runner K unearths a long-buried secret.",
            "runtime_minutes": 164,
            "creators": ["Denis Villeneuve"],
        },
        "status": "completed",
        "rating": 9.0,
        "notes": "Masterpiece cinematography",
        "tags": ["cyberpunk"],
        "rewatch_count": 2,
    }
    res_movie = smoke_client.post("/api/v1/collection", json=movie_payload, headers=headers)
    assert res_movie.status_code == 201
    movie_id = res_movie.json()["id"]

    # C. TV Show
    tv_payload = {
        "media": {
            "title": "Severance",
            "media_type": "tv_show",
            "release_year": 2022,
            "genres": ["Sci-Fi", "Thriller"],
            "poster_url": "https://example.com/severance.jpg",
            "summary": "Mark leads a team of office workers whose memories have been surgically divided.",
            "total_episodes": 19,
        },
        "status": "in_progress",
        "rating": 9.0,
        "notes": "Mind bending mystery",
        "tags": ["must-watch"],
        "current_episode": 9,
    }
    res_tv = smoke_client.post("/api/v1/collection", json=tv_payload, headers=headers)
    assert res_tv.status_code == 201
    tv_id = res_tv.json()["id"]

    # D. Book
    book_payload = {
        "media": {
            "title": "Neuromancer",
            "media_type": "book",
            "release_year": 1984,
            "genres": ["Cyberpunk", "Sci-Fi"],
            "poster_url": "https://example.com/neuromancer.jpg",
            "summary": "The sky above the port was the color of television, tuned to a dead channel.",
            "total_pages": 271,
            "creators": ["William Gibson"],
        },
        "status": "in_progress",
        "rating": 8.5,
        "notes": "Sprawl trilogy book 1",
        "tags": ["classic", "cyberpunk"],
        "current_page": 150,
    }
    res_book = smoke_client.post("/api/v1/collection", json=book_payload, headers=headers)
    assert res_book.status_code == 201
    book_id = res_book.json()["id"]

    # 4. Progress Increments (+1)
    # Increment game playtime (+1.0 hr)
    res_inc_game = smoke_client.post(
        f"/api/v1/collection/{game_id}/increment",
        json={"amount": 1.0},
        headers=headers,
    )
    assert res_inc_game.status_code == 200
    assert res_inc_game.json()["playtime_hours"] == 16.0

    # Increment TV show episode (+1 ep)
    res_inc_tv = smoke_client.post(
        f"/api/v1/collection/{tv_id}/increment",
        json={"amount": 1.0},
        headers=headers,
    )
    assert res_inc_tv.status_code == 200
    assert res_inc_tv.json()["current_episode"] == 10

    # Increment Book pages read (+10 pgs)
    res_inc_book = smoke_client.post(
        f"/api/v1/collection/{book_id}/increment",
        json={"amount": 10.0},
        headers=headers,
    )
    assert res_inc_book.status_code == 200
    assert res_inc_book.json()["current_page"] == 160

    # 5. Statistics Analytics Engine Verification
    res_stats = smoke_client.get("/api/v1/collection/stats", headers=headers)
    assert res_stats.status_code == 200
    stats = res_stats.json()

    assert stats["total_items"] == 4
    assert stats["game_hours"] == 16.0
    assert stats["movie_hours"] > 0
    assert stats["tv_hours"] > 0
    assert stats["episodes_watched"] == 10
    assert stats["pages_read"] == 160
    assert stats["book_hours"] > 0
    assert stats["total_time_hours"] > 0
    assert stats["curator_xp"] > 0
    assert stats["media_type_counts"]["game"] == 1
    assert stats["media_type_counts"]["movie"] == 1
    assert stats["media_type_counts"]["tv_show"] == 1
    assert stats["media_type_counts"]["book"] == 1

    # 6. JSON & CSV Export Verification
    # JSON Export
    res_export_json = smoke_client.get("/api/v1/import-export/export?format=json", headers=headers)
    assert res_export_json.status_code == 200
    exported_items = res_export_json.json()
    assert isinstance(exported_items, list)
    assert len(exported_items) == 4
    exported_titles = {item["title"] for item in exported_items}
    assert "Elden Ring" in exported_titles
    assert "Blade Runner 2049" in exported_titles
    assert "Severance" in exported_titles
    assert "Neuromancer" in exported_titles

    # CSV Export
    res_export_csv = smoke_client.get("/api/v1/import-export/export?format=csv", headers=headers)
    assert res_export_csv.status_code == 200
    csv_text = res_export_csv.text
    assert "media_type,title,status" in csv_text
    assert "Elden Ring" in csv_text
    assert "Blade Runner 2049" in csv_text
    assert "Severance" in csv_text
    assert "Neuromancer" in csv_text

"""
HostCart Live Smoke Test Script.
Spins up a live Uvicorn ASGI server on an ephemeral port, executes full HTTP
regression against the live network socket, and validates end-to-end functionality.
"""

import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def find_free_port() -> int:
    """Locate an available ephemeral TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_live_smoke():
    port = find_free_port()
    temp_dir = tempfile.mkdtemp(prefix="hostcart_smoke_")
    db_path = Path(temp_dir) / "live_smoke.db"

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["SECRET_KEY"] = "live-network-smoke-secret-key-at-least-32-chars-long"

    from src.core.config import reset_config_store
    from src.data.database import init_db, reset_engine
    from src.main import create_app

    reset_config_store()
    reset_engine()
    init_db()

    app = create_app()

    server_config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="error",
    )
    server = uvicorn.Server(config=server_config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for server to bind and accept connections
    base_url = f"http://127.0.0.1:{port}"
    client = httpx.Client(base_url=base_url, timeout=10.0)

    max_retries = 20
    ready = False
    for _ in range(max_retries):
        try:
            r = client.get("/api/health")
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(0.2)

    if not ready:
        server.should_exit = True
        raise RuntimeError(f"Live server at {base_url} failed to start within timeout.")

    print(f"[*] Live HostCart ASGI server running at {base_url}")

    try:
        # Step 1: Health probe
        r_health = client.get("/api/health")
        assert r_health.status_code == 200, f"Health check failed: {r_health.text}"
        assert r_health.json() == {"status": "ok", "app": "HostCart"}
        print("  [PASS] /api/health returned 200 OK")

        # Step 2: Docs probe
        r_docs = client.get("/docs")
        assert r_docs.status_code == 200, f"Docs endpoint failed: {r_docs.status_code}"
        print("  [PASS] /docs returned 200 OK (Swagger UI)")

        # Step 3: SPA HTML root
        r_root = client.get("/")
        assert r_root.status_code == 200, f"SPA root failed: {r_root.status_code}"
        assert "text/html" in r_root.headers.get("content-type", "")
        print("  [PASS] / returned 200 OK (SPA index HTML)")

        # Step 4: Register user
        reg_payload = {
            "username": "live_tester",
            "email": "tester@hostcart.local",
            "password": "Password123!",
        }
        r_reg = client.post("/api/v1/auth/register", json=reg_payload)
        assert r_reg.status_code == 201, f"Registration failed: {r_reg.text}"
        reg_data = r_reg.json()
        assert reg_data["user"]["username"] == "live_tester"
        print("  [PASS] /api/v1/auth/register succeeded (User registered)")

        # Step 5: Login and obtain token
        login_payload = {
            "username": "live_tester",
            "password": "Password123!",
        }
        r_login = client.post("/api/v1/auth/login", json=login_payload)
        assert r_login.status_code == 200, f"Login failed: {r_login.text}"
        token = r_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("  [PASS] /api/v1/auth/login succeeded (JWT Token acquired)")

        # Step 6: Add items across all 4 media types
        # Game
        r_game = client.post(
            "/api/v1/collection",
            json={
                "media": {
                    "title": "Hollow Knight",
                    "media_type": "game",
                    "release_year": 2017,
                    "genres": ["Metroidvania", "Indie"],
                    "summary": "Forge your own path in Hollow Knight!",
                },
                "status": "in_progress",
                "rating": 9.8,
                "playtime_hours": 24.5,
                "tags": ["favorite", "indie"],
            },
            headers=headers,
        )
        assert r_game.status_code == 201, f"Game creation failed: {r_game.text}"
        game_id = r_game.json()["id"]

        # Movie
        r_movie = client.post(
            "/api/v1/collection",
            json={
                "media": {
                    "title": "Interstellar",
                    "media_type": "movie",
                    "release_year": 2014,
                    "genres": ["Sci-Fi", "Adventure"],
                    "runtime_minutes": 169,
                    "creators": ["Christopher Nolan"],
                },
                "status": "completed",
                "rating": 9.5,
                "rewatch_count": 3,
            },
            headers=headers,
        )
        assert r_movie.status_code == 201, f"Movie creation failed: {r_movie.text}"

        # TV Show
        r_tv = client.post(
            "/api/v1/collection",
            json={
                "media": {
                    "title": "Succession",
                    "media_type": "tv_show",
                    "release_year": 2018,
                    "genres": ["Drama"],
                    "total_episodes": 39,
                },
                "status": "in_progress",
                "rating": 9.7,
                "current_episode": 20,
            },
            headers=headers,
        )
        assert r_tv.status_code == 201, f"TV show creation failed: {r_tv.text}"
        tv_id = r_tv.json()["id"]

        # Book
        r_book = client.post(
            "/api/v1/collection",
            json={
                "media": {
                    "title": "Dune",
                    "media_type": "book",
                    "release_year": 1965,
                    "genres": ["Sci-Fi", "Classic"],
                    "total_pages": 412,
                    "creators": ["Frank Herbert"],
                },
                "status": "in_progress",
                "rating": 9.0,
                "current_page": 200,
            },
            headers=headers,
        )
        assert r_book.status_code == 201, f"Book creation failed: {r_book.text}"
        book_id = r_book.json()["id"]
        print("  [PASS] /api/v1/collection: All 4 media types added successfully (Game, Movie, TV, Book)")

        # Step 7: Increment progress via /api/v1/collection/{id}/increment
        # Game +1.5 hrs
        r_inc_game = client.post(
            f"/api/v1/collection/{game_id}/increment",
            json={"amount": 1.5},
            headers=headers,
        )
        assert r_inc_game.status_code == 200
        assert r_inc_game.json()["playtime_hours"] == 26.0

        # TV +1 ep
        r_inc_tv = client.post(
            f"/api/v1/collection/{tv_id}/increment",
            json={"amount": 1.0},
            headers=headers,
        )
        assert r_inc_tv.status_code == 200
        assert r_inc_tv.json()["current_episode"] == 21

        # Book +25 pgs
        r_inc_book = client.post(
            f"/api/v1/collection/{book_id}/increment",
            json={"amount": 25.0},
            headers=headers,
        )
        assert r_inc_book.status_code == 200
        assert r_inc_book.json()["current_page"] == 225
        print("  [PASS] /api/v1/collection/{id}/increment: Quick progress increments (+1) verified")

        # Step 8: Statistics analytics engine
        r_stats = client.get("/api/v1/collection/stats", headers=headers)
        assert r_stats.status_code == 200
        stats = r_stats.json()
        assert stats["total_items"] == 4
        assert stats["game_hours"] == 26.0
        assert stats["movie_hours"] > 0
        assert stats["tv_hours"] > 0
        assert stats["episodes_watched"] == 21
        assert stats["pages_read"] == 225
        assert stats["book_hours"] > 0
        assert stats["curator_xp"] > 0
        assert stats["media_type_counts"]["game"] == 1
        assert stats["media_type_counts"]["movie"] == 1
        assert stats["media_type_counts"]["tv_show"] == 1
        assert stats["media_type_counts"]["book"] == 1
        print("  [PASS] /api/v1/collection/stats: Analytics calculations verified with accurate non-zero KPIs")

        # Step 9: Export JSON and CSV
        r_export_json = client.get("/api/v1/import-export/export?format=json", headers=headers)
        assert r_export_json.status_code == 200
        json_export = r_export_json.json()
        assert len(json_export) == 4
        assert {i["title"] for i in json_export} == {"Hollow Knight", "Interstellar", "Succession", "Dune"}

        r_export_csv = client.get("/api/v1/import-export/export?format=csv", headers=headers)
        assert r_export_csv.status_code == 200
        csv_text = r_export_csv.text
        assert "media_type,title,status" in csv_text
        assert "Hollow Knight" in csv_text
        assert "Interstellar" in csv_text
        assert "Succession" in csv_text
        assert "Dune" in csv_text
        print("  [PASS] /api/v1/import-export/export: JSON & CSV exports verified cleanly")

        print("\nSUCCESS: ALL LIVE SMOKE TESTS PASSED 100% AGAINST LIVE NETWORK SOCKET!")

    finally:
        client.close()
        server.should_exit = True
        server_thread.join(timeout=3)
        reset_engine()
        reset_config_store()
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("SECRET_KEY", None)
        try:
            if db_path.exists():
                db_path.unlink()
            Path(temp_dir).rmdir()
        except Exception:
            pass


if __name__ == "__main__":
    run_live_smoke()

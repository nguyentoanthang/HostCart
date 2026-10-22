"""
Phase 3 Test Suite: External Metadata Providers (IGDB, TMDB, OpenLibrary, Google Books),
Collection Import & Export (JSON/CSV with deduplication and file upload), and Runtime Settings API.
"""

from __future__ import annotations

import io
import json
from typing import Any, Dict, Generator
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from src.core.config import Settings, get_config_store, reset_config_store
from src.core.import_export import (
    export_collection_csv,
    export_collection_json,
    import_collection_csv,
    import_collection_json,
)
from src.core.providers import (
    _get_twitch_oauth_token,
    clear_token_cache,
    search_external_media,
)
from src.data.database import get_session, init_db
from src.data.models import MediaItem, MediaType, TrackingStatus, User, UserMediaEntry
from src.main import app


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset token caches and config store singletons before each test."""
    clear_token_cache()
    yield
    clear_token_cache()


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


def register_user(
    client: TestClient,
    username: str = "testuser",
    email: str = "testuser@hostcart.local",
    password: str = "password123",
) -> Dict[str, Any]:
    """Helper to register a user and return the response json."""
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert resp.status_code == 201
    return resp.json()


# ============================================================================
# 1. External Metadata Providers Unit & Integration Tests
# ============================================================================


@pytest.mark.anyio
async def test_igdb_provider_missing_credentials_returns_empty():
    """When IGDB credentials are empty, search_external_media returns empty list without error."""
    config = Settings()
    config.providers.igdb.client_id = ""
    config.providers.igdb.client_secret = ""

    results = await search_external_media("Zelda", MediaType.GAME, config=config)
    assert results == []


@pytest.mark.anyio
async def test_igdb_provider_parsing_and_token_caching():
    """IGDB search properly exchanges Twitch OAuth token, parses games, and caches token."""
    config = Settings()
    config.providers.igdb.client_id = "test-client-id"
    config.providers.igdb.client_secret = "test-client-secret"

    mock_token_resp = httpx.Response(
        status_code=200,
        json={"access_token": "bearer-twitch-xyz", "expires_in": 3600},
        request=httpx.Request("POST", "https://id.twitch.tv/oauth2/token"),
    )

    mock_games_data = [
        {
            "id": 1942,
            "name": "The Witcher 3: Wild Hunt",
            "summary": "Geralt searches for Ciri in an open world.",
            "first_release_date": 1431993600,  # 2015-05-19
            "cover": {"id": 101, "image_id": "co1wyy"},
            "genres": [{"id": 12, "name": "Role-playing (RPG)"}, {"id": 25, "name": "Adventure"}],
            "involved_companies": [
                {"developer": True, "company": {"id": 1, "name": "CD Projekt RED"}},
                {"developer": False, "company": {"id": 2, "name": "Bandai Namco"}},
            ],
            "platforms": [{"id": 6, "name": "PC (Microsoft Windows)"}],
        }
    ]
    mock_games_resp = httpx.Response(
        status_code=200,
        json=mock_games_data,
        request=httpx.Request("POST", "https://api.igdb.com/v4/games"),
    )

    call_count = {"token": 0, "games": 0}

    async def mock_post(url, *args, **kwargs):
        if "id.twitch.tv" in str(url):
            call_count["token"] += 1
            return mock_token_resp
        elif "api.igdb.com" in str(url):
            call_count["games"] += 1
            return mock_games_resp
        return httpx.Response(404, request=httpx.Request("POST", str(url)))

    with patch.object(httpx.AsyncClient, "post", side_effect=mock_post):
        results = await search_external_media("Witcher 3", MediaType.GAME, config=config)

        assert len(results) == 1
        item = results[0]
        assert item.media_type == MediaType.GAME
        assert item.title == "The Witcher 3: Wild Hunt"
        assert item.release_year == 2015
        assert item.poster_url == "https://images.igdb.com/igdb/image/upload/t_cover_big/co1wyy.jpg"
        assert item.genres == ["Role-playing (RPG)", "Adventure"]
        assert item.creators == ["CD Projekt RED"]
        assert item.external_id == "1942"
        assert item.external_source == "igdb"
        assert call_count["token"] == 1
        assert call_count["games"] == 1

        # Second call should reuse cached token
        results2 = await search_external_media("Witcher 3", MediaType.GAME, config=config)
        assert len(results2) == 1
        assert call_count["token"] == 1  # No second token fetch!
        assert call_count["games"] == 2


@pytest.mark.anyio
async def test_igdb_oauth_token_failure_handled_gracefully():
    """If Twitch OAuth fails (e.g. 401 or network error), return empty list without crash."""
    config = Settings()
    config.providers.igdb.client_id = "bad-id"
    config.providers.igdb.client_secret = "bad-secret"

    mock_fail_resp = httpx.Response(
        status_code=401,
        json={"message": "invalid client"},
        request=httpx.Request("POST", "https://id.twitch.tv/oauth2/token"),
    )

    with patch.object(httpx.AsyncClient, "post", return_value=mock_fail_resp):
        results = await search_external_media("Cyberpunk", MediaType.GAME, config=config)
        assert results == []

    # Network exception handling
    with patch.object(
        httpx.AsyncClient, "post", side_effect=httpx.ConnectTimeout("Twitch connection timed out")
    ):
        results = await search_external_media("Cyberpunk", MediaType.GAME, config=config)
        assert results == []


@pytest.mark.anyio
async def test_tmdb_provider_missing_api_key_returns_empty():
    """When TMDB API key is empty, return empty list gracefully."""
    config = Settings()
    config.providers.tmdb.api_key = ""

    results_movie = await search_external_media("Inception", MediaType.MOVIE, config=config)
    results_tv = await search_external_media("Breaking Bad", MediaType.TV_SHOW, config=config)
    assert results_movie == []
    assert results_tv == []


@pytest.mark.anyio
async def test_tmdb_movies_and_tv_shows_parsing():
    """TMDB movie and TV searches are parsed with backdrop, poster, year, and genre IDs."""
    config = Settings()
    config.providers.tmdb.api_key = "test-tmdb-key"

    movie_data = {
        "results": [
            {
                "id": 550,
                "title": "Fight Club",
                "original_title": "Fight Club",
                "release_date": "1999-10-15",
                "overview": "A ticking-time-bomb insomniac...",
                "poster_path": "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",
                "backdrop_path": "/fCayJrkfRaCRCTh8GqN30f8ioGo.jpg",
                "genre_ids": [18, 53],  # Drama, Thriller
            }
        ]
    }

    tv_data = {
        "results": [
            {
                "id": 1399,
                "name": "Game of Thrones",
                "original_name": "Game of Thrones",
                "first_air_date": "2011-04-17",
                "overview": "Seven noble families fight for control...",
                "poster_path": "/1XS1oqL89opfnbLl8WnZY1O1uJx.jpg",
                "backdrop_path": "/2OMB0ynKlyIenMJWI2Dy9IWT4c.jpg",
                "genre_ids": [10759, 18],  # Action & Adventure, Drama
            }
        ]
    }

    async def mock_get(url, *args, **kwargs):
        if "search/movie" in str(url):
            return httpx.Response(200, json=movie_data, request=httpx.Request("GET", str(url)))
        elif "search/tv" in str(url):
            return httpx.Response(200, json=tv_data, request=httpx.Request("GET", str(url)))
        return httpx.Response(404, request=httpx.Request("GET", str(url)))

    with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
        movies = await search_external_media("Fight Club", MediaType.MOVIE, config=config)
        assert len(movies) == 1
        m = movies[0]
        assert m.media_type == MediaType.MOVIE
        assert m.title == "Fight Club"
        assert m.release_year == 1999
        assert "pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg" in m.poster_url
        assert "fCayJrkfRaCRCTh8GqN30f8ioGo.jpg" in m.backdrop_url
        assert m.genres == ["Drama", "Thriller"]
        assert m.external_id == "550"
        assert m.external_source == "tmdb"

        shows = await search_external_media("Game of Thrones", MediaType.TV_SHOW, config=config)
        assert len(shows) == 1
        s = shows[0]
        assert s.media_type == MediaType.TV_SHOW
        assert s.title == "Game of Thrones"
        assert s.release_year == 2011
        assert s.genres == ["Action & Adventure", "Drama"]
        assert s.external_id == "1399"
        assert s.external_source == "tmdb"


@pytest.mark.anyio
async def test_tmdb_network_error_handled_gracefully():
    """TMDB search handles network failure without throwing unhandled exceptions."""
    config = Settings()
    config.providers.tmdb.api_key = "test-key"

    with patch.object(httpx.AsyncClient, "get", side_effect=httpx.ReadTimeout("Timeout")):
        results = await search_external_media("Inception", MediaType.MOVIE, config=config)
        assert results == []


@pytest.mark.anyio
async def test_openlibrary_book_search_parsing():
    """OpenLibrary book search (keyless) parses title, authors, cover, page count, and ISBN."""
    config = Settings()

    ol_data = {
        "docs": [
            {
                "title": "Dune",
                "author_name": ["Frank Herbert"],
                "first_publish_year": 1965,
                "cover_i": 8258661,
                "number_of_pages_median": 412,
                "isbn": ["9780441172719"],
                "key": "/works/OL893415W",
                "subject": ["Science Fiction", "Space Opera"],
            }
        ]
    }

    mock_resp = httpx.Response(
        200, json=ol_data, request=httpx.Request("GET", "https://openlibrary.org/search.json")
    )

    with patch.object(httpx.AsyncClient, "get", return_value=mock_resp):
        results = await search_external_media("Dune", MediaType.BOOK, config=config)

        assert len(results) == 1
        book = results[0]
        assert book.media_type == MediaType.BOOK
        assert book.title == "Dune"
        assert book.creators == ["Frank Herbert"]
        assert book.release_year == 1965
        assert book.poster_url == "https://covers.openlibrary.org/b/id/8258661-L.jpg"
        assert book.total_pages == 412
        assert book.external_id == "OL893415W"
        assert book.external_source == "openlibrary"
        assert book.genres == ["Science Fiction", "Space Opera"]


@pytest.mark.anyio
async def test_books_google_books_fallback_when_openlibrary_empty():
    """When OpenLibrary yields 0 results, search seamlessly falls back to Google Books."""
    config = Settings()
    config.providers.books.google_books_api_key = "mock-google-key"

    ol_empty_resp = httpx.Response(
        200,
        json={"docs": []},
        request=httpx.Request("GET", "https://openlibrary.org/search.json"),
    )

    gb_data = {
        "items": [
            {
                "id": "gb_vol_999",
                "volumeInfo": {
                    "title": "Neuromancer",
                    "authors": ["William Gibson"],
                    "publishedDate": "1984-07-01",
                    "pageCount": 271,
                    "description": "The sky above the port was the color of television...",
                    "categories": ["Cyberpunk", "Fiction"],
                    "imageLinks": {"thumbnail": "http://books.google.com/thumb.jpg"},
                },
            }
        ]
    }
    gb_resp = httpx.Response(
        200,
        json=gb_data,
        request=httpx.Request("GET", "https://www.googleapis.com/books/v1/volumes"),
    )

    async def mock_get(url, *args, **kwargs):
        if "openlibrary.org" in str(url):
            return ol_empty_resp
        elif "googleapis.com" in str(url):
            return gb_resp
        return httpx.Response(404, request=httpx.Request("GET", str(url)))

    with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
        results = await search_external_media("Neuromancer", MediaType.BOOK, config=config)

        assert len(results) == 1
        book = results[0]
        assert book.title == "Neuromancer"
        assert book.creators == ["William Gibson"]
        assert book.release_year == 1984
        assert book.total_pages == 271
        assert book.external_id == "gb_vol_999"
        assert book.external_source == "google_books"
        assert book.poster_url == "https://books.google.com/thumb.jpg"


@pytest.mark.anyio
async def test_search_external_media_empty_query_returns_empty():
    """An empty or whitespace-only query immediately returns empty list without network calls."""
    res = await search_external_media("   ", MediaType.GAME)
    assert res == []


# ============================================================================
# 2. Search API Endpoint Integration Tests
# ============================================================================


def test_api_search_endpoint_requires_auth(client: TestClient):
    """GET /api/v1/search requires valid Bearer token."""
    resp = client.get("/api/v1/search?q=Zelda&media_type=game")
    assert resp.status_code == 401


def test_api_search_endpoint_success(client: TestClient):
    """GET /api/v1/search returns parsed search results for authenticated users."""
    user = register_user(client, "searcher", "searcher@hostcart.local")
    token = user["access_token"]

    mock_results = [
        {
            "media_type": "game",
            "title": "Elden Ring",
            "release_year": 2022,
            "poster_url": "https://images.igdb.com/cover.jpg",
            "summary": "Rise, Tarnished.",
            "genres": ["Action", "RPG"],
            "creators": ["FromSoftware"],
            "external_id": "119133",
            "external_source": "igdb",
        }
    ]

    with patch(
        "src.api.v1.search.search_external_media",
        new=AsyncMock(return_value=mock_results),
    ):
        resp = client.get(
            "/api/v1/search?q=Elden+Ring&media_type=game",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["title"] == "Elden Ring"
        assert items[0]["creators"] == ["FromSoftware"]


def test_api_search_query_validation(client: TestClient):
    """Query parameter 'q' must have min_length=1."""
    user = register_user(client, "validuser", "valid@hostcart.local")
    token = user["access_token"]

    resp = client.get(
        "/api/v1/search?q=&media_type=game",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ============================================================================
# 3. Collection Export Tests (JSON & CSV)
# ============================================================================


def _seed_sample_collection(session: Session, user_id: int):
    """Helper to populate sample media items and user entries."""
    game = MediaItem(
        media_type=MediaType.GAME,
        title="Chrono Trigger",
        release_year=1995,
        genres=["JRPG", "Adventure"],
        creators=["Square"],
        external_id="1010",
        external_source="igdb",
    )
    movie = MediaItem(
        media_type=MediaType.MOVIE,
        title="Spirited Away",
        release_year=2001,
        genres=["Animation", "Fantasy"],
        creators=["Studio Ghibli"],
        runtime_minutes=125,
        external_id="2020",
        external_source="tmdb",
    )
    book = MediaItem(
        media_type=MediaType.BOOK,
        title="Foundation",
        release_year=1951,
        genres=["Science Fiction"],
        creators=["Isaac Asimov"],
        total_pages=255,
        external_id="3030",
        external_source="openlibrary",
    )
    session.add_all([game, movie, book])
    session.flush()

    e1 = UserMediaEntry(
        user_id=user_id,
        media_item_id=game.id,
        status=TrackingStatus.COMPLETED,
        rating=10.0,
        is_favorite=True,
        playtime_hours=35.5,
        notes="Masterpiece time travel RPG",
        tags=["retro", "favorite"],
    )
    e2 = UserMediaEntry(
        user_id=user_id,
        media_item_id=movie.id,
        status=TrackingStatus.COMPLETED,
        rating=9.5,
        is_favorite=True,
        rewatch_count=3,
        notes="Beautiful animation",
        tags=["ghibli"],
    )
    e3 = UserMediaEntry(
        user_id=user_id,
        media_item_id=book.id,
        status=TrackingStatus.IN_PROGRESS,
        rating=8.5,
        current_page=120,
        notes="Psychohistory concept is great",
    )
    session.add_all([e1, e2, e3])
    session.commit()


def test_export_collection_json_structure(db_session: Session):
    """export_collection_json returns comprehensive list of dicts with media and entry fields."""
    user = User(username="export_json_user", email="json@hostcart.local", hashed_password="pw")
    db_session.add(user)
    db_session.commit()

    _seed_sample_collection(db_session, user.id)

    data = export_collection_json(db_session, user.id)
    assert len(data) == 3

    # Check Chrono Trigger entry
    game_item = next(d for d in data if d["title"] == "Chrono Trigger")
    assert game_item["media_type"] == "game"
    assert game_item["status"] == "completed"
    assert game_item["rating"] == 10.0
    assert game_item["is_favorite"] is True
    assert game_item["playtime_hours"] == 35.5
    assert "JRPG" in game_item["genres"]
    assert "Square" in game_item["creators"]
    assert game_item["media"]["title"] == "Chrono Trigger"


def test_export_collection_csv_headers_and_content(db_session: Session):
    """export_collection_csv returns valid CSV text with exact required headers."""
    user = User(username="export_csv_user", email="csv@hostcart.local", hashed_password="pw")
    db_session.add(user)
    db_session.commit()

    _seed_sample_collection(db_session, user.id)

    csv_text = export_collection_csv(db_session, user.id)
    lines = csv_text.strip().split("\n")
    header_line = lines[0]

    expected_headers = [
        "media_type",
        "title",
        "status",
        "rating",
        "is_favorite",
        "playtime_hours",
        "current_episode",
        "current_page",
        "rewatch_count",
        "release_year",
        "total_episodes",
        "total_pages",
        "runtime_minutes",
        "genres",
        "creators",
        "external_id",
        "external_source",
        "notes",
        "tags",
    ]
    for h in expected_headers:
        assert h in header_line

    assert len(lines) == 4  # 1 header + 3 rows
    assert "Chrono Trigger" in csv_text
    assert "Spirited Away" in csv_text
    assert "Foundation" in csv_text


def test_export_collection_filtered_by_media_type(db_session: Session):
    """export_collection_json and csv filter correctly by media_type."""
    user = User(username="filtered_user", email="filter@hostcart.local", hashed_password="pw")
    db_session.add(user)
    db_session.commit()

    _seed_sample_collection(db_session, user.id)

    # Filter GAME only
    games_json = export_collection_json(db_session, user.id, media_type=MediaType.GAME)
    assert len(games_json) == 1
    assert games_json[0]["title"] == "Chrono Trigger"

    # Filter BOOK only
    books_csv = export_collection_csv(db_session, user.id, media_type=MediaType.BOOK)
    lines = books_csv.strip().split("\n")
    assert len(lines) == 2  # header + 1 book row
    assert "Foundation" in lines[1]
    assert "Chrono Trigger" not in books_csv


def test_api_export_endpoint(client: TestClient, db_session: Session):
    """GET /api/v1/import-export/export works for JSON and CSV with download headers."""
    user_data = register_user(client, "exporter", "exporter@hostcart.local")
    token = user_data["access_token"]
    user_id = user_data["user"]["id"]

    _seed_sample_collection(db_session, user_id)

    # JSON export
    resp_json = client.get(
        "/api/v1/import-export/export?format=json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_json.status_code == 200
    assert resp_json.headers["content-type"] == "application/json"
    assert 'attachment; filename="hostcart_export.json"' in resp_json.headers["content-disposition"]
    data = resp_json.json()
    assert len(data) == 3

    # CSV export
    resp_csv = client.get(
        "/api/v1/import-export/export?format=csv",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert 'attachment; filename="hostcart_export.csv"' in resp_csv.headers["content-disposition"]
    assert "Chrono Trigger" in resp_csv.text


# ============================================================================
# 4. Collection Import Tests (JSON & CSV & Duplicate Handling)
# ============================================================================


def test_import_collection_json_and_duplicate_skipping(db_session: Session):
    """import_collection_json creates items and entries, and handles duplicates."""
    user = User(username="importer1", email="importer1@hostcart.local", hashed_password="pw")
    db_session.add(user)
    db_session.commit()

    import_data = [
        {
            "media_type": "game",
            "title": "Super Mario World",
            "release_year": 1990,
            "genres": ["Platformer"],
            "creators": ["Nintendo"],
            "status": "completed",
            "rating": 9.8,
            "is_favorite": True,
            "playtime_hours": 20.0,
            "external_id": "1001",
            "external_source": "igdb",
        },
        {
            "media_type": "movie",
            "title": "Interstellar",
            "release_year": 2014,
            "genres": ["Sci-Fi", "Drama"],
            "creators": ["Christopher Nolan"],
            "status": "completed",
            "rating": 9.5,
            "runtime_minutes": 169,
            "external_id": "157336",
            "external_source": "tmdb",
        },
    ]

    res = import_collection_json(db_session, user.id, import_data, skip_duplicates=True)
    assert res == {"total": 2, "imported": 2, "skipped": 0}

    # Verify items exist in database
    entries = db_session.exec(
        select(UserMediaEntry).where(UserMediaEntry.user_id == user.id)
    ).all()
    assert len(entries) == 2

    # Re-importing same items with skip_duplicates=True
    res_dup = import_collection_json(db_session, user.id, import_data, skip_duplicates=True)
    assert res_dup == {"total": 2, "imported": 0, "skipped": 2}

    # Re-importing with skip_duplicates=False updates existing entries
    import_data[0]["rating"] = 10.0
    res_update = import_collection_json(db_session, user.id, import_data, skip_duplicates=False)
    assert res_update == {"total": 2, "imported": 2, "skipped": 0}

    updated_entry = db_session.exec(
        select(UserMediaEntry).where(
            UserMediaEntry.user_id == user.id,
            UserMediaEntry.media_item_id == entries[0].media_item_id,
        )
    ).first()
    assert updated_entry.rating == 10.0


def test_import_collection_csv_text(db_session: Session):
    """import_collection_csv parses CSV text and links entries correctly."""
    user = User(username="importer_csv", email="importer_csv@hostcart.local", hashed_password="pw")
    db_session.add(user)
    db_session.commit()

    csv_content = """media_type,title,status,rating,is_favorite,playtime_hours,current_episode,current_page,rewatch_count,release_year,total_episodes,total_pages,runtime_minutes,genres,creators,external_id,external_source,notes,tags
book,The Hobbit,completed,9.0,true,0.0,0,310,0,1937,,310,,Fantasy,J.R.R. Tolkien,tolk_hobbit,openlibrary,Read in childhood,classic;tolkien
tv_show,Breaking Bad,completed,10.0,true,0.0,62,0,1,2008,62,,47,Crime;Drama,Vince Gilligan,1396,tmdb,Peak television,top-rated
"""

    res = import_collection_csv(db_session, user.id, csv_content)
    assert res == {"total": 2, "imported": 2, "skipped": 0}

    entries = db_session.exec(
        select(UserMediaEntry).where(UserMediaEntry.user_id == user.id)
    ).all()
    assert len(entries) == 2

    hobbit_entry = next(e for e in entries if e.media_item.title == "The Hobbit")
    assert hobbit_entry.media_item.media_type == MediaType.BOOK
    assert hobbit_entry.rating == 9.0
    assert hobbit_entry.is_favorite is True
    assert hobbit_entry.media_item.total_pages == 310
    assert hobbit_entry.tags == ["classic", "tolkien"]


def test_api_import_endpoint_json_body(client: TestClient, db_session: Session):
    """POST /api/v1/import-export/import accepts raw JSON list."""
    user_data = register_user(client, "api_json_importer", "api_json@hostcart.local")
    token = user_data["access_token"]

    payload = [
        {
            "media_type": "game",
            "title": "Metroid Prime",
            "release_year": 2002,
            "status": "completed",
            "rating": 9.5,
        }
    ]

    resp = client.post(
        "/api/v1/import-export/import",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"total": 1, "imported": 1, "skipped": 0}


def test_api_import_endpoint_csv_body(client: TestClient, db_session: Session):
    """POST /api/v1/import-export/import accepts raw CSV body with text/csv header."""
    user_data = register_user(client, "api_csv_importer", "api_csv@hostcart.local")
    token = user_data["access_token"]

    csv_data = "media_type,title,status,rating\ngame,Half-Life 2,completed,10.0\n"

    resp = client.post(
        "/api/v1/import-export/import",
        content=csv_data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "text/csv"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"total": 1, "imported": 1, "skipped": 0}


def test_api_import_endpoint_multipart_file_upload(client: TestClient, db_session: Session):
    """POST /api/v1/import-export/import accepts multipart file upload for both .json and .csv."""
    user_data = register_user(client, "api_upload_importer", "api_upload@hostcart.local")
    token = user_data["access_token"]

    # 1. Upload .json file
    json_bytes = json.dumps(
        [{"media_type": "movie", "title": "The Matrix", "status": "completed", "rating": 9.8}]
    ).encode("utf-8")
    files_json = {"file": ("matrix.json", io.BytesIO(json_bytes), "application/json")}

    resp_json = client.post(
        "/api/v1/import-export/import",
        files=files_json,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_json.status_code == 200
    assert resp_json.json() == {"total": 1, "imported": 1, "skipped": 0}

    # 2. Upload .csv file
    csv_bytes = b"media_type,title,status\nbook,1984,completed\n"
    files_csv = {"file": ("orwell.csv", io.BytesIO(csv_bytes), "text/csv")}

    resp_csv = client.post(
        "/api/v1/import-export/import",
        files=files_csv,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_csv.status_code == 200
    assert resp_csv.json() == {"total": 1, "imported": 1, "skipped": 0}


def test_api_import_error_handling(client: TestClient):
    """Bad JSON body or invalid multipart uploads return 400 Bad Request."""
    user_data = register_user(client, "error_importer", "error_imp@hostcart.local")
    token = user_data["access_token"]

    # Bad multipart without file
    resp_no_file = client.post(
        "/api/v1/import-export/import",
        data={"some_field": "val"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_no_file.status_code == 400

    # Bad JSON string
    resp_bad_json = client.post(
        "/api/v1/import-export/import",
        content="not valid json",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    assert resp_bad_json.status_code == 400


# ============================================================================
# 5. Settings API Tests (RBAC, Masking & Persistence)
# ============================================================================


def test_settings_api_rbac_guards(client: TestClient):
    """Only administrators can access GET / PUT /api/v1/settings."""
    # First user is admin
    admin = register_user(client, "admin_user", "admin@hostcart.local")
    admin_token = admin["access_token"]

    # Second user is regular user
    regular = register_user(client, "regular_user", "reg@hostcart.local")
    reg_token = regular["access_token"]

    # Unauthenticated
    assert client.get("/api/v1/settings").status_code == 401
    assert client.put("/api/v1/settings", json={}).status_code == 401

    # Regular user: 403 Forbidden
    assert (
        client.get(
            "/api/v1/settings", headers={"Authorization": f"Bearer {reg_token}"}
        ).status_code
        == 403
    )
    assert (
        client.put(
            "/api/v1/settings", json={}, headers={"Authorization": f"Bearer {reg_token}"}
        ).status_code
        == 403
    )

    # Admin: 200 OK
    assert (
        client.get(
            "/api/v1/settings", headers={"Authorization": f"Bearer {admin_token}"}
        ).status_code
        == 200
    )


def test_settings_api_masking_and_updating(client: TestClient, tmp_path):
    """GET masks sensitive keys; PUT updates config and preserves masked values."""
    # Isolated config file for this test
    test_config_path = tmp_path / "config.json"
    store = get_config_store(config_path=test_config_path, force_reload=True)
    store.update_config(
        {
            "security": {"secret_key": "super-secret-key-12345-minimum-32-bytes-long!"},
            "providers": {
                "igdb": {"client_id": "twitch_id", "client_secret": "twitch_secret"},
                "tmdb": {"api_key": "tmdb_secret_key"},
                "books": {"google_books_api_key": "google_secret_key"},
            },
        },
        save=True,
    )

    admin = register_user(client, "admin_settings", "adm_set@hostcart.local")
    admin_token = admin["access_token"]

    # 1. GET settings: verify sensitive fields are masked
    get_resp = client.get(
        "/api/v1/settings", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert get_resp.status_code == 200
    data = get_resp.json()

    assert data["security"]["secret_key"] == "********"
    assert data["providers"]["igdb"]["client_secret"] == "********"
    assert data["providers"]["tmdb"]["api_key"] == "********"
    assert data["providers"]["books"]["google_books_api_key"] == "********"
    # Client ID is not secret so it remains readable
    assert data["providers"]["igdb"]["client_id"] == "twitch_id"

    # 2. PUT settings: update provider keys and pass "********" placeholder for unchanged keys
    update_payload = {
        "igdb_client_id": "new_twitch_client_id",
        "igdb_client_secret": "********",  # should NOT overwrite with asterisks!
        "tmdb_api_key": "new_tmdb_key_999",  # updated secret
    }

    put_resp = client.put(
        "/api/v1/settings",
        json=update_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert put_resp.status_code == 200
    put_data = put_resp.json()
    assert put_data["providers"]["igdb"]["client_id"] == "new_twitch_client_id"
    assert put_data["providers"]["igdb"]["client_secret"] == "********"
    assert put_data["providers"]["tmdb"]["api_key"] == "********"

    # Verify underlying store retained original twitch_secret and updated tmdb_key
    raw_settings = store.get_settings()
    assert raw_settings.providers.igdb.client_id == "new_twitch_client_id"
    assert raw_settings.providers.igdb.client_secret == "twitch_secret"
    assert raw_settings.providers.tmdb.api_key == "new_tmdb_key_999"
    assert raw_settings.security.secret_key == "super-secret-key-12345-minimum-32-bytes-long!"



def test_settings_api_update_all_flat_and_nested_fields(client: TestClient, tmp_path):
    """PUT /api/v1/settings updates all mapped configuration keys and nested objects."""
    test_config_path = tmp_path / "config_all.json"
    store = get_config_store(config_path=test_config_path, force_reload=True)

    admin = register_user(client, "admin_all", "all@hostcart.local")
    admin_token = admin["access_token"]

    payload = {
        "google_books_api_key": "new-gbooks-key",
        "openlibrary_enabled": False,
        "secret_key": "new-secret-key-67890-at-least-32-chars-long",
        "server_host": "127.0.0.1",
        "server_port": 9000,
        "features": {"ratings": {"scale": 5}},
    }

    resp = client.put(
        "/api/v1/settings",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["server"]["host"] == "127.0.0.1"
    assert res_data["server"]["port"] == 9000
    assert res_data["providers"]["books"]["openlibrary_enabled"] is False
    assert res_data["providers"]["books"]["google_books_api_key"] == "********"
    assert res_data["security"]["secret_key"] == "********"

    # Verify underlying store values
    settings = store.get_settings()
    assert settings.server.host == "127.0.0.1"
    assert settings.server.port == 9000
    assert settings.providers.books.google_books_api_key == "new-gbooks-key"
    assert settings.providers.books.openlibrary_enabled is False
    assert settings.security.secret_key == "new-secret-key-67890-at-least-32-chars-long"


def test_import_collection_edge_cases(db_session: Session):
    """Test importing with edge case field formats (empty titles, strings, booleans, invalid types)."""
    user = User(username="edge_user", email="edge@hostcart.local", hashed_password="pw")
    db_session.add(user)
    db_session.commit()

    # 1. Empty title or missing title
    res_empty_title = import_collection_json(
        db_session, user.id, [{"media_type": "game", "title": ""}]
    )
    assert res_empty_title["skipped"] == 1
    assert res_empty_title["imported"] == 0

    # 2. Invalid media_type
    res_invalid_type = import_collection_json(
        db_session, user.id, [{"media_type": "unknown_type", "title": "Some Game"}]
    )
    assert res_invalid_type["skipped"] == 1
    assert res_invalid_type["imported"] == 0

    # 3. String fields for genres, creators, tags (semicolon vs comma)
    item = {
        "media_type": "game",
        "title": "Celeste",
        "genres": "Platformer, Indie",
        "creators": "Maddy Makes Games; Extremely OK Games",
        "tags": "challenging, precise",
        "status": "in_progress",
        "is_favorite": "yes",
        "playtime_hours": "14.5",
        "current_episode": "",
        "current_page": None,
        "rewatch_count": 0,
        "rating": "9.5",
        "release_year": "2018",
    }
    res_parsed = import_collection_json(db_session, user.id, [item])
    assert res_parsed["imported"] == 1

    entry = db_session.exec(
        select(UserMediaEntry).where(UserMediaEntry.user_id == user.id)
    ).first()
    assert entry.rating == 9.5
    assert entry.playtime_hours == 14.5
    assert entry.is_favorite is True
    assert entry.tags == ["challenging", "precise"]
    assert "Indie" in entry.media_item.genres
    assert "Maddy Makes Games" in entry.media_item.creators

    # 4. CSV import with completely empty text
    empty_csv_res = import_collection_csv(db_session, user.id, "")
    assert empty_csv_res == {"total": 0, "imported": 0, "skipped": 0}


def test_api_import_json_object_with_items_wrapper(client: TestClient):
    """POST /api/v1/import-export/import accepts an object wrapped in an 'items' key."""
    user_data = register_user(client, "items_wrapper", "items@hostcart.local")
    token = user_data["access_token"]

    body = {
        "items": [
            {"media_type": "game", "title": "Portal 2", "status": "completed", "rating": 10.0}
        ]
    }
    resp = client.post(
        "/api/v1/import-export/import",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"total": 1, "imported": 1, "skipped": 0}


def test_api_import_invalid_json_file_upload(client: TestClient):
    """Uploading a malformed .json file returns HTTP 400 Bad Request."""
    user_data = register_user(client, "bad_json_user", "bad_json@hostcart.local")
    token = user_data["access_token"]

    files = {"file": ("bad.json", io.BytesIO(b"{not: valid, json"), "application/json")}
    resp = client.post(
        "/api/v1/import-export/import",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "Invalid JSON file format" in resp.json()["detail"]


@pytest.mark.anyio
async def test_providers_server_error_and_edge_cases():
    """All providers gracefully handle HTTP 500 status codes and missing fields."""
    config = Settings()
    config.providers.igdb.client_id = "test-id"
    config.providers.igdb.client_secret = "test-secret"
    config.providers.tmdb.api_key = "test-tmdb"
    config.providers.books.google_books_api_key = "test-gb"

    # IGDB HTTP 500
    with patch(
        "src.core.providers._get_twitch_oauth_token",
        new=AsyncMock(return_value="mock-token"),
    ):
        with patch.object(
            httpx.AsyncClient,
            "post",
            return_value=httpx.Response(500, request=httpx.Request("POST", "https://api.igdb.com/v4/games")),
        ):
            res_igdb = await search_external_media("Zelda", MediaType.GAME, config=config)
            assert res_igdb == []

    # TMDB HTTP 500
    with patch.object(
        httpx.AsyncClient,
        "get",
        return_value=httpx.Response(500, request=httpx.Request("GET", "https://api.themoviedb.org/3/search/movie")),
    ):
        res_tmdb = await search_external_media("Inception", MediaType.MOVIE, config=config)
        assert res_tmdb == []

    # OpenLibrary HTTP 500 + Google Books HTTP 500
    with patch.object(
        httpx.AsyncClient,
        "get",
        return_value=httpx.Response(500, request=httpx.Request("GET", "https://openlibrary.org/search.json")),
    ):
        res_books = await search_external_media("Dune", MediaType.BOOK, config=config)
        assert res_books == []

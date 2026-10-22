"""
External Media Metadata Providers for HostCart.
Provides live metadata lookup for:
- Video Games via IGDB (Twitch OAuth2 + IGDB v4)
- Movies & TV Shows via TMDB (The Movie Database)
- Books via OpenLibrary (keyless) and Google Books (fallback)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from src.api.v1.schemas import MediaItemCreate
from src.core.config import Settings, get_settings
from src.data.models import MediaType

logger = logging.getLogger(__name__)

# Standard TMDB Genre ID to Name Mapping
TMDB_GENRES: Dict[int, str] = {
    # Movies & Shared
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    14: "Fantasy",
    36: "History",
    27: "Horror",
    10402: "Music",
    9648: "Mystery",
    10749: "Romance",
    878: "Science Fiction",
    10770: "TV Movie",
    53: "Thriller",
    10752: "War",
    37: "Western",
    # TV Specific
    10759: "Action & Adventure",
    10762: "Kids",
    10763: "News",
    10764: "Reality",
    10765: "Sci-Fi & Fantasy",
    10766: "Soap",
    10767: "Talk",
    10768: "War & Politics",
}

# In-memory Twitch OAuth token cache
_twitch_token_cache: Dict[str, Any] = {
    "token": None,
    "expires_at": 0.0,
    "client_id": "",
}


def clear_token_cache() -> None:
    """Clear in-memory OAuth token cache (useful for tests)."""
    global _twitch_token_cache
    _twitch_token_cache = {
        "token": None,
        "expires_at": 0.0,
        "client_id": "",
    }


async def _get_twitch_oauth_token(
    client: httpx.AsyncClient, client_id: str, client_secret: str
) -> Optional[str]:
    """Exchange Twitch client_id and client_secret for a bearer access token."""
    global _twitch_token_cache

    now = time.time()
    if (
        _twitch_token_cache["token"]
        and _twitch_token_cache["client_id"] == client_id
        and now < _twitch_token_cache["expires_at"] - 60
    ):
        return _twitch_token_cache["token"]

    token_url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }

    try:
        resp = await client.post(token_url, params=params, timeout=8.0)
        if resp.status_code != 200:
            logger.warning(
                "Twitch OAuth token request failed with status %d: %s",
                resp.status_code,
                resp.text,
            )
            return None

        data = resp.json()
        token = data.get("access_token")
        expires_in = data.get("expires_in", 3600)

        if token:
            _twitch_token_cache["token"] = token
            _twitch_token_cache["expires_at"] = now + float(expires_in)
            _twitch_token_cache["client_id"] = client_id
            return token
    except Exception as e:
        logger.warning("Error fetching Twitch OAuth token: %s", e)

    return None


async def _search_igdb_games(
    query: str, config: Settings, client: httpx.AsyncClient
) -> List[MediaItemCreate]:
    """Search IGDB /v4/games endpoint with Twitch OAuth authentication."""
    client_id = config.providers.igdb.client_id.strip()
    client_secret = config.providers.igdb.client_secret.strip()

    if not client_id or not client_secret:
        logger.info("IGDB client_id or client_secret is not configured. Skipping lookup.")
        return []

    token = await _get_twitch_oauth_token(client, client_id, client_secret)
    if not token:
        logger.warning("Failed to obtain Twitch OAuth token for IGDB.")
        return []

    headers = {
        "Client-ID": client_id,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    clean_query = query.replace('"', "").replace(";", "").strip()
    igdb_query = (
        f'search "{clean_query}"; '
        f"fields name, summary, first_release_date, cover.image_id, genres.name, "
        f"involved_companies.company.name, involved_companies.developer, platforms.name; "
        f"limit 10;"
    )

    try:
        resp = await client.post(
            "https://api.igdb.com/v4/games",
            content=igdb_query,
            headers=headers,
            timeout=8.0,
        )
        if resp.status_code != 200:
            logger.warning("IGDB search returned status %d: %s", resp.status_code, resp.text)
            return []

        games_data = resp.json()
        results: List[MediaItemCreate] = []

        for item in games_data:
            name = item.get("name")
            if not name:
                continue

            release_year: Optional[int] = None
            release_ts = item.get("first_release_date")
            if release_ts and isinstance(release_ts, (int, float)):
                try:
                    release_year = datetime.fromtimestamp(release_ts, tz=timezone.utc).year
                except Exception:
                    pass

            poster_url: Optional[str] = None
            cover = item.get("cover")
            if isinstance(cover, dict) and cover.get("image_id"):
                poster_url = (
                    f"https://images.igdb.com/igdb/image/upload/t_cover_big/{cover['image_id']}.jpg"
                )

            genres: List[str] = []
            for g in item.get("genres", []):
                if isinstance(g, dict) and g.get("name"):
                    genres.append(g["name"])

            creators: List[str] = []
            for ic in item.get("involved_companies", []):
                if isinstance(ic, dict) and ic.get("developer"):
                    company = ic.get("company")
                    if isinstance(company, dict) and company.get("name"):
                        creators.append(company["name"])

            results.append(
                MediaItemCreate(
                    media_type=MediaType.GAME,
                    title=name,
                    release_year=release_year,
                    poster_url=poster_url,
                    summary=item.get("summary"),
                    genres=genres,
                    creators=creators,
                    external_id=str(item.get("id")),
                    external_source="igdb",
                )
            )

        return results
    except Exception as e:
        logger.warning("IGDB search request failed: %s", e)
        return []


async def _search_tmdb_media(
    query: str, media_type: MediaType, config: Settings, client: httpx.AsyncClient
) -> List[MediaItemCreate]:
    """Search TMDB for movies or TV shows."""
    api_key = config.providers.tmdb.api_key.strip()
    if not api_key:
        logger.info("TMDB API key is not configured. Skipping lookup.")
        return []

    is_movie = media_type == MediaType.MOVIE
    endpoint = (
        "https://api.themoviedb.org/3/search/movie"
        if is_movie
        else "https://api.themoviedb.org/3/search/tv"
    )

    params = {
        "api_key": api_key,
        "query": query.strip(),
        "include_adult": "false",
        "language": "en-US",
        "page": 1,
    }

    try:
        resp = await client.get(endpoint, params=params, timeout=8.0)
        if resp.status_code != 200:
            logger.warning("TMDB search returned status %d: %s", resp.status_code, resp.text)
            return []

        data = resp.json()
        results: List[MediaItemCreate] = []

        for item in data.get("results", []):
            title = item.get("title") if is_movie else item.get("name")
            if not title:
                continue

            orig_title = item.get("original_title") if is_movie else item.get("original_name")
            date_str = item.get("release_date") if is_movie else item.get("first_air_date")
            release_year: Optional[int] = None
            if date_str and len(date_str) >= 4 and date_str[:4].isdigit():
                release_year = int(date_str[:4])

            poster_path = item.get("poster_path")
            poster_url = (
                f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
            )

            backdrop_path = item.get("backdrop_path")
            backdrop_url = (
                f"https://image.tmdb.org/t/p/w1280{backdrop_path}" if backdrop_path else None
            )

            genre_ids = item.get("genre_ids", [])
            genres = [
                TMDB_GENRES[gid]
                for gid in genre_ids
                if isinstance(gid, int) and gid in TMDB_GENRES
            ]

            results.append(
                MediaItemCreate(
                    media_type=media_type,
                    title=title,
                    original_title=orig_title,
                    release_year=release_year,
                    poster_url=poster_url,
                    backdrop_url=backdrop_url,
                    summary=item.get("overview"),
                    genres=genres,
                    creators=[],
                    external_id=str(item.get("id")),
                    external_source="tmdb",
                )
            )

        return results
    except Exception as e:
        logger.warning("TMDB search request failed: %s", e)
        return []


async def _search_openlibrary_books(
    query: str, client: httpx.AsyncClient
) -> List[MediaItemCreate]:
    """Search OpenLibrary search.json (keyless)."""
    endpoint = "https://openlibrary.org/search.json"
    params = {"q": query.strip(), "limit": 10}

    try:
        resp = await client.get(endpoint, params=params, timeout=8.0)
        if resp.status_code != 200:
            logger.warning("OpenLibrary returned status %d", resp.status_code)
            return []

        data = resp.json()
        results: List[MediaItemCreate] = []

        for doc in data.get("docs", []):
            title = doc.get("title")
            if not title:
                continue

            authors = doc.get("author_name", [])
            if isinstance(authors, str):
                authors = [authors]
            creators = [str(a).strip() for a in authors if str(a).strip()]

            first_publish = doc.get("first_publish_year")
            release_year: Optional[int] = None
            if first_publish and str(first_publish).isdigit():
                release_year = int(first_publish)

            cover_i = doc.get("cover_i")
            poster_url = (
                f"https://covers.openlibrary.org/b/id/{cover_i}-L.jpg" if cover_i else None
            )

            pages = doc.get("number_of_pages_median")
            total_pages = int(pages) if pages and str(pages).isdigit() else None

            isbns = doc.get("isbn", [])
            key = str(doc.get("key", "")).replace("/works/", "")
            external_id = key if key else (str(isbns[0]) if isbns else None)

            subjects = doc.get("subject", [])
            genres: List[str] = []
            if isinstance(subjects, list):
                genres = [str(s) for s in subjects[:5]]

            results.append(
                MediaItemCreate(
                    media_type=MediaType.BOOK,
                    title=title,
                    release_year=release_year,
                    poster_url=poster_url,
                    genres=genres,
                    creators=creators,
                    total_pages=total_pages,
                    external_id=external_id,
                    external_source="openlibrary",
                )
            )

        return results
    except Exception as e:
        logger.warning("OpenLibrary search failed: %s", e)
        return []


async def _search_google_books(
    query: str, config: Settings, client: httpx.AsyncClient
) -> List[MediaItemCreate]:
    """Search Google Books API (fallback or supplemental for books)."""
    endpoint = "https://www.googleapis.com/books/v1/volumes"
    params: Dict[str, Any] = {"q": query.strip(), "maxResults": 10}

    api_key = config.providers.books.google_books_api_key.strip()
    if api_key:
        params["key"] = api_key

    try:
        resp = await client.get(endpoint, params=params, timeout=8.0)
        if resp.status_code != 200:
            logger.warning("Google Books returned status %d", resp.status_code)
            return []

        data = resp.json()
        results: List[MediaItemCreate] = []

        for item in data.get("items", []):
            volume_info = item.get("volumeInfo", {})
            title = volume_info.get("title")
            if not title:
                continue

            creators = volume_info.get("authors", [])
            if isinstance(creators, str):
                creators = [creators]

            pub_date = volume_info.get("publishedDate", "")
            release_year: Optional[int] = None
            if pub_date and len(pub_date) >= 4 and pub_date[:4].isdigit():
                release_year = int(pub_date[:4])

            pages = volume_info.get("pageCount")
            total_pages = int(pages) if pages and str(pages).isdigit() else None

            images = volume_info.get("imageLinks", {})
            poster_url = images.get("thumbnail") or images.get("smallThumbnail")
            if poster_url and poster_url.startswith("http://"):
                poster_url = "https://" + poster_url[7:]

            genres = volume_info.get("categories", [])
            if isinstance(genres, str):
                genres = [genres]

            results.append(
                MediaItemCreate(
                    media_type=MediaType.BOOK,
                    title=title,
                    release_year=release_year,
                    poster_url=poster_url,
                    summary=volume_info.get("description"),
                    genres=genres,
                    creators=creators,
                    total_pages=total_pages,
                    external_id=str(item.get("id")),
                    external_source="google_books",
                )
            )

        return results
    except Exception as e:
        logger.warning("Google Books search failed: %s", e)
        return []


async def search_external_media(
    query: str,
    media_type: MediaType,
    config: Optional[Settings] = None,
) -> List[MediaItemCreate]:
    """
    Search external metadata providers based on media type.
    - GAME: IGDB (Twitch OAuth2 + /v4/games)
    - MOVIE & TV_SHOW: TMDB (/3/search/movie and /3/search/tv)
    - BOOK: OpenLibrary (search.json) + Google Books fallback
    Never crashes on missing credentials or upstream network errors.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    settings = config or get_settings()

    async with httpx.AsyncClient(timeout=8.0) as client:
        if media_type == MediaType.GAME:
            return await _search_igdb_games(cleaned_query, settings, client)

        elif media_type in (MediaType.MOVIE, MediaType.TV_SHOW):
            return await _search_tmdb_media(cleaned_query, media_type, settings, client)

        elif media_type == MediaType.BOOK:
            # 1. Try OpenLibrary if enabled
            if settings.providers.books.openlibrary_enabled:
                books = await _search_openlibrary_books(cleaned_query, client)
                if books:
                    return books

            # 2. Fallback to Google Books
            return await _search_google_books(cleaned_query, settings, client)

    return []

"""
Search API endpoints for HostCart.
Provides live external metadata search across Games, Movies, TV Shows, and Books.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query

from src.api.v1.auth import get_current_user
from src.api.v1.schemas import MediaItemCreate
from src.core.config import get_settings
from src.core.providers import search_external_media
from src.data.models import MediaType, User

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=List[MediaItemCreate])
@router.get("/", response_model=List[MediaItemCreate])
async def search_media(
    q: str = Query(..., min_length=1, description="Search query string"),
    media_type: MediaType = Query(..., description="Target media type (game, movie, tv_show, book)"),
    current_user: User = Depends(get_current_user),
) -> List[MediaItemCreate]:
    """
    Search external media metadata providers (IGDB, TMDB, OpenLibrary/Google Books).
    Requires active user authentication.
    """
    settings = get_settings()
    return await search_external_media(query=q, media_type=media_type, config=settings)

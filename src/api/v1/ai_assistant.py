"""
AI Media Assistant Endpoints for HostCart.
Provides POST /api/v1/ai/recommend for personalized recommendations
based on the user's tracked collection, routing requests through the System AI Gateway
or direct OpenRouter API with full Homelab attribution headers.
"""

from __future__ import annotations

from typing import Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from src.api.v1.auth import get_current_user
from src.core.config import get_settings
from src.data.database import get_session
from src.data.models import MediaItem, TrackingStatus, User, UserMediaEntry

router = APIRouter(prefix="/ai", tags=["ai"])


class RecommendRequest(BaseModel):
    media_type: Optional[str] = Field(
        default=None,
        description="Optional filter for specific media type ('game', 'movie', 'tv_show', 'book')",
    )
    prompt: Optional[str] = Field(
        default=None,
        description="Optional freeform prompt or specific preference guidance from the user",
    )


class RecommendResponse(BaseModel):
    recommendation: str
    model: str


@router.post("/recommend", response_model=RecommendResponse)
async def recommend_media(
    request: Optional[RecommendRequest] = Body(default=None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> RecommendResponse:
    """
    Generate personalized media recommendations based on the user's collection history.
    Includes X-Homelab-Service and X-Homelab-User headers for central AI Gateway attribution.
    """
    settings = get_settings()

    # Verify AI API key is configured
    ai_key = settings.homelab.ai_api_key
    if not ai_key or not ai_key.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Assistant is not configured. Please configure AI_API_KEY or OPENROUTER_API_KEY.",
        )

    # Fetch user's high-rated, in-progress, or completed collection items to build taste context
    stmt = (
        select(UserMediaEntry)
        .options(selectinload(UserMediaEntry.media_item))
        .join(MediaItem, UserMediaEntry.media_item_id == MediaItem.id)
        .where(UserMediaEntry.user_id == current_user.id)
    )

    if request and request.media_type:
        stmt = stmt.where(MediaItem.media_type == request.media_type.lower())

    # Prioritize favorites, high ratings, and active tracking
    entries = session.exec(
        stmt.order_by(
            UserMediaEntry.is_favorite.desc(),
            UserMediaEntry.rating.desc().nullslast(),
            UserMediaEntry.updated_at.desc(),
        ).limit(25)
    ).all()

    context_lines = []
    for e in entries:
        if e.media_item:
            m = e.media_item
            mtype = (
                m.media_type.value
                if hasattr(m.media_type, "value")
                else str(m.media_type)
            )
            status_str = (
                e.status.value if hasattr(e.status, "value") else str(e.status)
            )
            details = [f"Type: {mtype}", f"Status: {status_str}"]
            if e.rating is not None:
                details.append(f"Rating: {e.rating}/10")
            if m.genres:
                details.append(f"Genres: {', '.join(m.genres)}")
            if e.playtime_hours > 0:
                details.append(f"Playtime: {e.playtime_hours:.1f} hrs")
            if e.current_episode > 0:
                details.append(f"Episode: {e.current_episode}")
            if e.current_page > 0:
                details.append(f"Page: {e.current_page}")

            context_lines.append(f"- {m.title} ({'; '.join(details)})")

    history_summary = (
        "\n".join(context_lines)
        if context_lines
        else "The user has no tracked media entries yet."
    )

    system_prompt = (
        "You are HostCart's AI Media Assistant. Recommend movies, TV shows, games, or books "
        "tailored to the user's taste, tracking history, and stated preferences. "
        "Keep recommendations insightful, relevant, and engaging."
    )

    user_prompt = f"User's collection and activity history:\n{history_summary}\n\n"
    if request and request.media_type:
        user_prompt += f"Target media type: {request.media_type}\n"
    if request and request.prompt:
        user_prompt += f"User specific prompt: {request.prompt}\n"
    user_prompt += (
        "\nPlease provide 3 to 5 recommendations with reasons why the user would enjoy each."
    )

    endpoint_url = f"{settings.homelab.ai_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {ai_key}",
        "X-Homelab-Service": "hostcart",
        "X-Homelab-User": current_user.username,
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.homelab.ai_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint_url, headers=headers, json=payload)
            if resp.status_code >= 500:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Downstream AI service error ({resp.status_code}): {resp.text}",
                )
            elif resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Downstream AI service error ({resp.status_code}): {resp.text}",
                )
            data = resp.json()
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI Assistant request timed out while contacting upstream AI service.",
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to communicate with AI service: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unexpected error calling AI service: {exc}",
        )

    choices = data.get("choices", [])
    rec_content = ""
    if choices and isinstance(choices, list):
        rec_content = choices[0].get("message", {}).get("content", "")

    model_used = data.get("model", settings.homelab.ai_model)

    return RecommendResponse(
        recommendation=rec_content,
        model=model_used,
    )

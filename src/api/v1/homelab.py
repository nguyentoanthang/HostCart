"""
Inter-Service Homelab Endpoints for HostCart.
Provides /api/v1/homelab/health, /summary, /tools, and /tools/execute
for central dashboard metrics and BonTalk AI voice assistant collection management.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import selectinload
from sqlmodel import Session, func, select

from src.api.v1.auth import get_current_user
from src.core.config import get_settings
from src.data.database import get_database_backend, get_session
from src.data.models import MediaItem, MediaType, TrackingStatus, User, UserMediaEntry

router = APIRouter(prefix="/homelab", tags=["homelab"])


def _format_entry_progress(entry: UserMediaEntry) -> str:
    """Format human-readable progress string for activity summary and tool execution."""
    media_item = entry.media_item
    if not media_item:
        status_val = entry.status.value if hasattr(entry.status, "value") else str(entry.status)
        return status_val.replace("_", " ").title()

    mtype = (
        media_item.media_type.value
        if hasattr(media_item.media_type, "value")
        else str(media_item.media_type)
    )

    if mtype == MediaType.GAME.value:
        return f"{entry.playtime_hours:.1f} hrs"
    elif mtype == MediaType.TV_SHOW.value:
        if media_item.total_episodes:
            return f"Ep {entry.current_episode}/{media_item.total_episodes}"
        return f"Ep {entry.current_episode}"
    elif mtype == MediaType.BOOK.value:
        if media_item.total_pages:
            return f"p. {entry.current_page}/{media_item.total_pages}"
        return f"p. {entry.current_page}"
    elif mtype == MediaType.MOVIE.value:
        status_val = entry.status.value if hasattr(entry.status, "value") else str(entry.status)
        if status_val == TrackingStatus.COMPLETED.value:
            return "Completed"
        elif status_val == TrackingStatus.PLAN_TO.value:
            return "Plan to"
        elif status_val == TrackingStatus.IN_PROGRESS.value:
            return "In progress"
        return status_val.replace("_", " ").title()
    else:
        status_val = entry.status.value if hasattr(entry.status, "value") else str(entry.status)
        return status_val.replace("_", " ").title()


# =====================================================================
# 1. Health & Discovery Endpoint
# =====================================================================

@router.get("/health")
def homelab_health():
    """
    Public health and deployment mode discovery endpoint.
    Returns service name, status, deployment mode, auth mode, database backend, and version.
    """
    settings = get_settings()
    return {
        "service": "hostcart",
        "status": "ok",
        "deployment_mode": settings.homelab.deployment_mode,
        "auth_mode": settings.homelab.auth_mode,
        "database_backend": get_database_backend(),
        "version": "1.0.0",
    }


# =====================================================================
# 2. User Summary for Dashboard Overview
# =====================================================================

@router.get("/summary")
def homelab_summary(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    User collection summary endpoint for central Homelab Dashboard overview.
    Requires authentication (SSO session, cookie, or OBO headers).
    """
    # Total count
    total_items = (
        session.exec(
            select(func.count(UserMediaEntry.id)).where(
                UserMediaEntry.user_id == current_user.id
            )
        ).one()
        or 0
    )

    # In progress
    in_progress = (
        session.exec(
            select(func.count(UserMediaEntry.id)).where(
                UserMediaEntry.user_id == current_user.id,
                UserMediaEntry.status == TrackingStatus.IN_PROGRESS,
            )
        ).one()
        or 0
    )

    # Completed
    completed = (
        session.exec(
            select(func.count(UserMediaEntry.id)).where(
                UserMediaEntry.user_id == current_user.id,
                UserMediaEntry.status == TrackingStatus.COMPLETED,
            )
        ).one()
        or 0
    )

    # Plan to
    plan_to = (
        session.exec(
            select(func.count(UserMediaEntry.id)).where(
                UserMediaEntry.user_id == current_user.id,
                UserMediaEntry.status == TrackingStatus.PLAN_TO,
            )
        ).one()
        or 0
    )

    # Top 5 most recently updated entries
    recent_entries = session.exec(
        select(UserMediaEntry)
        .options(selectinload(UserMediaEntry.media_item))
        .where(UserMediaEntry.user_id == current_user.id)
        .order_by(UserMediaEntry.updated_at.desc())
        .limit(5)
    ).all()

    recent_activity = []
    for entry in recent_entries:
        if entry.media_item:
            mtype = (
                entry.media_item.media_type.value
                if hasattr(entry.media_item.media_type, "value")
                else str(entry.media_item.media_type)
            )
            status_val = (
                entry.status.value
                if hasattr(entry.status, "value")
                else str(entry.status)
            )
            recent_activity.append(
                {
                    "title": entry.media_item.title,
                    "media_type": mtype,
                    "status": status_val,
                    "progress": _format_entry_progress(entry),
                }
            )

    return {
        "service": "hostcart",
        "username": current_user.username,
        "stats": {
            "total_items": total_items,
            "in_progress": in_progress,
            "completed": completed,
            "plan_to": plan_to,
            "recent_activity": recent_activity,
        },
    }


# =====================================================================
# 3. Inter-Service Tool Discovery
# =====================================================================

TOOL_SCHEMAS = [
    {
        "name": "hostcart_get_user_collection",
        "description": "List or filter the current user's tracked movies, TV shows, games, or books in HostCart.",
        "parameters": {
            "type": "object",
            "properties": {
                "media_type": {
                    "type": "string",
                    "enum": ["game", "movie", "tv_show", "book"],
                },
                "status": {
                    "type": "string",
                    "enum": [
                        "plan_to",
                        "in_progress",
                        "completed",
                        "on_hold",
                        "dropped",
                        "wishlist",
                    ],
                },
                "search": {
                    "type": "string",
                    "description": "Search keyword matching title",
                },
            },
        },
    },
    {
        "name": "hostcart_update_progress",
        "description": "Add a media item or increment progress (episodes, hours, pages) in the user's HostCart collection.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "media_type": {
                    "type": "string",
                    "enum": ["game", "movie", "tv_show", "book"],
                },
                "action": {
                    "type": "string",
                    "enum": [
                        "add_to_watchlist",
                        "increment_progress",
                        "mark_completed",
                    ],
                },
                "amount": {"type": "number", "default": 1},
            },
            "required": ["title", "action"],
        },
    },
]


@router.get("/tools")
def homelab_tools():
    """
    Return OpenAI function-calling compatible tool schemas for BonTalk and other AI services.
    """
    return {
        "service": "hostcart",
        "tools": TOOL_SCHEMAS,
    }


# =====================================================================
# 4. Inter-Service Tool Execution
# =====================================================================

class ToolExecuteRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


@router.post("/tools/execute")
def homelab_execute_tool(
    request: ToolExecuteRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Execute tool action on behalf of authenticated current_user.
    Strictly scoped to current_user ownership.
    """
    tool_name = request.tool_name
    args = request.arguments or {}

    if tool_name == "hostcart_get_user_collection":
        media_type = args.get("media_type")
        status_param = args.get("status")
        search = args.get("search")

        stmt = (
            select(UserMediaEntry)
            .options(selectinload(UserMediaEntry.media_item))
            .join(MediaItem, UserMediaEntry.media_item_id == MediaItem.id)
            .where(UserMediaEntry.user_id == current_user.id)
        )

        if media_type:
            stmt = stmt.where(MediaItem.media_type == media_type.lower())
        if status_param:
            stmt = stmt.where(UserMediaEntry.status == status_param.lower())
        if search:
            search_clean = search.strip().lower()
            stmt = stmt.where(
                func.lower(MediaItem.title).like(f"%{search_clean}%")
                | func.lower(func.coalesce(MediaItem.original_title, "")).like(
                    f"%{search_clean}%"
                )
            )

        stmt = stmt.order_by(UserMediaEntry.updated_at.desc())
        entries = session.exec(stmt).all()

        results = []
        for e in entries:
            m = e.media_item
            results.append(
                {
                    "id": e.id,
                    "title": m.title if m else "",
                    "media_type": (
                        m.media_type.value
                        if m and hasattr(m.media_type, "value")
                        else str(m.media_type)
                        if m
                        else ""
                    ),
                    "status": (
                        e.status.value
                        if hasattr(e.status, "value")
                        else str(e.status)
                    ),
                    "rating": e.rating,
                    "playtime_hours": e.playtime_hours,
                    "current_episode": e.current_episode,
                    "total_episodes": m.total_episodes if m else None,
                    "current_page": e.current_page,
                    "total_pages": m.total_pages if m else None,
                    "progress": _format_entry_progress(e),
                }
            )
        return {"ok": True, "result": results}

    elif tool_name == "hostcart_update_progress":
        title = args.get("title")
        action = args.get("action")
        media_type_arg = args.get("media_type")
        raw_amount = args.get("amount", 1)
        try:
            amount = float(raw_amount)
        except (ValueError, TypeError):
            amount = 1.0

        if not title or not str(title).strip():
            return {"ok": False, "error": "Missing or empty 'title' argument"}

        title_clean = str(title).strip()

        if action == "add_to_watchlist":
            # Determine media type enum
            mtype = MediaType.MOVIE
            if media_type_arg:
                for mt in MediaType:
                    if mt.value == media_type_arg.lower():
                        mtype = mt
                        break

            # Find or create MediaItem
            media_item_stmt = select(MediaItem).where(
                func.lower(MediaItem.title) == title_clean.lower()
            )
            if media_type_arg:
                media_item_stmt = media_item_stmt.where(MediaItem.media_type == mtype)

            media_item = session.exec(media_item_stmt).first()
            if not media_item:
                media_item = MediaItem(
                    title=title_clean,
                    media_type=mtype,
                )
                session.add(media_item)
                session.commit()
                session.refresh(media_item)

            # Check if user already has entry
            entry = session.exec(
                select(UserMediaEntry).where(
                    UserMediaEntry.user_id == current_user.id,
                    UserMediaEntry.media_item_id == media_item.id,
                )
            ).first()

            if entry:
                if entry.status != TrackingStatus.PLAN_TO:
                    entry.status = TrackingStatus.PLAN_TO
                    entry.updated_at = datetime.now(timezone.utc)
                    session.add(entry)
                    session.commit()
            else:
                entry = UserMediaEntry(
                    user_id=current_user.id,
                    media_item_id=media_item.id,
                    status=TrackingStatus.PLAN_TO,
                )
                session.add(entry)
                session.commit()

            return {
                "ok": True,
                "result": f"Added '{media_item.title}' to watchlist for user '{current_user.username}'.",
            }

        elif action == "increment_progress":
            stmt = (
                select(UserMediaEntry)
                .options(selectinload(UserMediaEntry.media_item))
                .join(MediaItem, UserMediaEntry.media_item_id == MediaItem.id)
                .where(
                    UserMediaEntry.user_id == current_user.id,
                    func.lower(MediaItem.title) == title_clean.lower(),
                )
            )
            if media_type_arg:
                stmt = stmt.where(MediaItem.media_type == media_type_arg.lower())

            entry = session.exec(stmt).first()
            if not entry or not entry.media_item:
                return {
                    "ok": False,
                    "error": f"Item '{title_clean}' not found in collection for user '{current_user.username}'",
                }

            media_item = entry.media_item
            mtype_val = (
                media_item.media_type.value
                if hasattr(media_item.media_type, "value")
                else str(media_item.media_type)
            )

            if mtype_val == MediaType.TV_SHOW.value:
                entry.current_episode += int(amount)
                if (
                    media_item.total_episodes
                    and entry.current_episode >= media_item.total_episodes
                ):
                    entry.status = TrackingStatus.COMPLETED
                else:
                    entry.status = TrackingStatus.IN_PROGRESS
                entry.updated_at = datetime.now(timezone.utc)
                session.add(entry)
                session.commit()
                session.refresh(entry)

                tot_str = (
                    f"/{media_item.total_episodes}"
                    if media_item.total_episodes
                    else ""
                )
                res_msg = (
                    f"Updated '{media_item.title}' for user '{current_user.username}': "
                    f"episode progress is now {entry.current_episode}{tot_str} ({entry.status.value})."
                )
                return {"ok": True, "result": res_msg}

            elif mtype_val == MediaType.GAME.value:
                entry.playtime_hours += float(amount)
                entry.status = TrackingStatus.IN_PROGRESS
                entry.updated_at = datetime.now(timezone.utc)
                session.add(entry)
                session.commit()
                session.refresh(entry)

                res_msg = (
                    f"Updated '{media_item.title}' for user '{current_user.username}': "
                    f"playtime is now {entry.playtime_hours:.1f} hours ({entry.status.value})."
                )
                return {"ok": True, "result": res_msg}

            elif mtype_val == MediaType.BOOK.value:
                entry.current_page += int(amount)
                if (
                    media_item.total_pages
                    and entry.current_page >= media_item.total_pages
                ):
                    entry.status = TrackingStatus.COMPLETED
                else:
                    entry.status = TrackingStatus.IN_PROGRESS
                entry.updated_at = datetime.now(timezone.utc)
                session.add(entry)
                session.commit()
                session.refresh(entry)

                tot_str = (
                    f"/{media_item.total_pages}"
                    if media_item.total_pages
                    else ""
                )
                res_msg = (
                    f"Updated '{media_item.title}' for user '{current_user.username}': "
                    f"page progress is now {entry.current_page}{tot_str} ({entry.status.value})."
                )
                return {"ok": True, "result": res_msg}

            elif mtype_val == MediaType.MOVIE.value:
                entry.status = TrackingStatus.COMPLETED
                entry.updated_at = datetime.now(timezone.utc)
                session.add(entry)
                session.commit()
                session.refresh(entry)

                res_msg = f"Marked '{media_item.title}' as completed for user '{current_user.username}'."
                return {"ok": True, "result": res_msg}

            else:
                entry.status = TrackingStatus.IN_PROGRESS
                entry.updated_at = datetime.now(timezone.utc)
                session.add(entry)
                session.commit()
                session.refresh(entry)
                return {
                    "ok": True,
                    "result": f"Updated '{media_item.title}' for user '{current_user.username}'.",
                }

        elif action == "mark_completed":
            stmt = (
                select(UserMediaEntry)
                .options(selectinload(UserMediaEntry.media_item))
                .join(MediaItem, UserMediaEntry.media_item_id == MediaItem.id)
                .where(
                    UserMediaEntry.user_id == current_user.id,
                    func.lower(MediaItem.title) == title_clean.lower(),
                )
            )
            if media_type_arg:
                stmt = stmt.where(MediaItem.media_type == media_type_arg.lower())

            entry = session.exec(stmt).first()
            if not entry or not entry.media_item:
                return {
                    "ok": False,
                    "error": f"Item '{title_clean}' not found in collection for user '{current_user.username}'",
                }

            entry.status = TrackingStatus.COMPLETED
            entry.updated_at = datetime.now(timezone.utc)
            session.add(entry)
            session.commit()
            session.refresh(entry)

            return {
                "ok": True,
                "result": f"Marked '{entry.media_item.title}' as completed for user '{current_user.username}'.",
            }

        else:
            return {"ok": False, "error": f"Unknown action '{action}'"}

    else:
        return {"ok": False, "error": f"Unknown tool '{tool_name}'"}

"""
Collection Import and Export engine for HostCart.
Supports JSON and CSV formats with duplicate handling and media catalog reuse.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import selectinload
from sqlmodel import Session, func, select

from src.data.models import MediaItem, MediaType, TrackingStatus, UserMediaEntry

logger = logging.getLogger(__name__)

CSV_HEADERS: List[str] = [
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


def export_collection_json(
    session: Session,
    user_id: int,
    media_type: Optional[MediaType] = None,
) -> List[Dict[str, Any]]:
    """Export all user collection entries as a structured JSON list of dicts."""
    stmt = (
        select(UserMediaEntry)
        .options(selectinload(UserMediaEntry.media_item))
        .join(MediaItem, UserMediaEntry.media_item_id == MediaItem.id)
        .where(UserMediaEntry.user_id == user_id)
        .order_by(UserMediaEntry.id.asc())
    )

    if media_type is not None:
        stmt = stmt.where(MediaItem.media_type == media_type)

    entries = list(session.exec(stmt).all())
    result: List[Dict[str, Any]] = []

    for entry in entries:
        media = entry.media_item
        item_dict: Dict[str, Any] = {
            "id": entry.id,
            "media_type": media.media_type.value,
            "title": media.title,
            "original_title": media.original_title,
            "status": entry.status.value,
            "rating": entry.rating,
            "is_favorite": entry.is_favorite,
            "playtime_hours": entry.playtime_hours,
            "current_episode": entry.current_episode,
            "current_page": entry.current_page,
            "rewatch_count": entry.rewatch_count,
            "release_year": media.release_year,
            "poster_url": media.poster_url,
            "backdrop_url": media.backdrop_url,
            "summary": media.summary,
            "total_episodes": media.total_episodes,
            "total_pages": media.total_pages,
            "runtime_minutes": media.runtime_minutes,
            "genres": media.genres or [],
            "creators": media.creators or [],
            "external_id": media.external_id,
            "external_source": media.external_source,
            "notes": entry.notes,
            "tags": entry.tags or [],
            "started_at": entry.started_at.isoformat() if entry.started_at else None,
            "completed_at": entry.completed_at.isoformat() if entry.completed_at else None,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
            "media": {
                "id": media.id,
                "media_type": media.media_type.value,
                "title": media.title,
                "original_title": media.original_title,
                "release_year": media.release_year,
                "poster_url": media.poster_url,
                "backdrop_url": media.backdrop_url,
                "summary": media.summary,
                "genres": media.genres or [],
                "creators": media.creators or [],
                "external_id": media.external_id,
                "external_source": media.external_source,
                "total_episodes": media.total_episodes,
                "total_pages": media.total_pages,
                "runtime_minutes": media.runtime_minutes,
            },
        }
        result.append(item_dict)

    return result


def export_collection_csv(
    session: Session,
    user_id: int,
    media_type: Optional[MediaType] = None,
) -> str:
    """Export user collection entries as a formatted CSV string."""
    stmt = (
        select(UserMediaEntry)
        .options(selectinload(UserMediaEntry.media_item))
        .join(MediaItem, UserMediaEntry.media_item_id == MediaItem.id)
        .where(UserMediaEntry.user_id == user_id)
        .order_by(UserMediaEntry.id.asc())
    )

    if media_type is not None:
        stmt = stmt.where(MediaItem.media_type == media_type)

    entries = list(session.exec(stmt).all())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_HEADERS, lineterminator="\n")
    writer.writeheader()

    for entry in entries:
        m = entry.media_item
        row = {
            "media_type": m.media_type.value,
            "title": m.title,
            "status": entry.status.value,
            "rating": str(entry.rating) if entry.rating is not None else "",
            "is_favorite": "true" if entry.is_favorite else "false",
            "playtime_hours": str(entry.playtime_hours),
            "current_episode": str(entry.current_episode),
            "current_page": str(entry.current_page),
            "rewatch_count": str(entry.rewatch_count),
            "release_year": str(m.release_year) if m.release_year is not None else "",
            "total_episodes": str(m.total_episodes) if m.total_episodes is not None else "",
            "total_pages": str(m.total_pages) if m.total_pages is not None else "",
            "runtime_minutes": str(m.runtime_minutes) if m.runtime_minutes is not None else "",
            "genres": ";".join(m.genres or []),
            "creators": ";".join(m.creators or []),
            "external_id": m.external_id or "",
            "external_source": m.external_source or "",
            "notes": entry.notes or "",
            "tags": ";".join(entry.tags or []),
        }
        writer.writerow(row)

    return output.getvalue()


def _parse_list_field(val: Any) -> List[str]:
    """Parse list field from JSON list or semicolon/comma-delimited string."""
    if isinstance(val, list):
        return [str(item).strip() for item in val if str(item).strip()]
    if isinstance(val, str):
        if ";" in val:
            return [part.strip() for part in val.split(";") if part.strip()]
        elif "," in val:
            return [part.strip() for part in val.split(",") if part.strip()]
        val_clean = val.strip()
        return [val_clean] if val_clean else []
    return []


def _parse_int_field(val: Any) -> Optional[int]:
    """Safely parse integer field."""
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _parse_float_field(val: Any, default: float = 0.0) -> float:
    """Safely parse float field."""
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _parse_bool_field(val: Any) -> bool:
    """Safely parse boolean field."""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes", "t", "y")
    return False


def _update_entry_fields(entry: UserMediaEntry, item: Dict[str, Any]) -> None:
    """Update existing UserMediaEntry fields from import item dictionary."""
    status_raw = str(item.get("status", "")).strip().lower()
    if status_raw:
        try:
            entry.status = TrackingStatus(status_raw)
        except ValueError:
            pass

    if "rating" in item and item["rating"] != "":
        try:
            entry.rating = float(item["rating"])
        except (ValueError, TypeError):
            pass

    if "is_favorite" in item:
        entry.is_favorite = _parse_bool_field(item["is_favorite"])

    if "playtime_hours" in item:
        entry.playtime_hours = _parse_float_field(item["playtime_hours"], entry.playtime_hours)

    if "current_episode" in item:
        ep = _parse_int_field(item["current_episode"])
        if ep is not None:
            entry.current_episode = ep

    if "current_page" in item:
        p = _parse_int_field(item["current_page"])
        if p is not None:
            entry.current_page = p

    if "rewatch_count" in item:
        rc = _parse_int_field(item["rewatch_count"])
        if rc is not None:
            entry.rewatch_count = rc

    if "notes" in item and item["notes"] is not None:
        entry.notes = str(item["notes"])

    if "tags" in item:
        entry.tags = _parse_list_field(item["tags"])

    entry.updated_at = datetime.now(timezone.utc)


def import_collection_json(
    session: Session,
    user_id: int,
    items: List[Dict[str, Any]],
    skip_duplicates: bool = True,
) -> Dict[str, int]:
    """
    Import collection entries from a list of dicts.
    Creates or reuses catalog MediaItems, creates UserMediaEntries,
    and returns a summary of total, imported, and skipped counts.
    """
    imported_count = 0
    skipped_count = 0

    for item in items:
        # Resolve media metadata (nested "media" object takes precedence if present)
        media_info = item.get("media") if isinstance(item.get("media"), dict) else item

        title_raw = media_info.get("title")
        if not title_raw or not str(title_raw).strip():
            skipped_count += 1
            continue
        title = str(title_raw).strip()

        media_type_raw = str(media_info.get("media_type", "")).strip().lower()
        try:
            media_type = MediaType(media_type_raw)
        except ValueError:
            skipped_count += 1
            continue

        external_id = (
            str(media_info.get("external_id")).strip()
            if media_info.get("external_id")
            else None
        )
        external_source = (
            str(media_info.get("external_source")).strip()
            if media_info.get("external_source")
            else None
        )

        # 1. Attempt lookup by external_id + external_source
        media_item: Optional[MediaItem] = None
        if external_id and external_source:
            media_item = session.exec(
                select(MediaItem).where(
                    MediaItem.external_id == external_id,
                    MediaItem.external_source == external_source,
                )
            ).first()

        # 2. Attempt lookup by title + media_type
        if not media_item:
            media_item = session.exec(
                select(MediaItem).where(
                    func.lower(MediaItem.title) == title.lower(),
                    MediaItem.media_type == media_type,
                )
            ).first()

        # 3. Create new MediaItem if not found
        if not media_item:
            genres = _parse_list_field(media_info.get("genres"))
            creators = _parse_list_field(media_info.get("creators"))

            media_item = MediaItem(
                media_type=media_type,
                title=title,
                original_title=media_info.get("original_title"),
                release_year=_parse_int_field(media_info.get("release_year")),
                poster_url=media_info.get("poster_url"),
                backdrop_url=media_info.get("backdrop_url"),
                summary=media_info.get("summary"),
                genres=genres,
                creators=creators,
                external_id=external_id,
                external_source=external_source,
                total_episodes=_parse_int_field(media_info.get("total_episodes")),
                total_pages=_parse_int_field(media_info.get("total_pages")),
                runtime_minutes=_parse_int_field(media_info.get("runtime_minutes")),
            )
            session.add(media_item)
            session.flush()

        assert media_item.id is not None

        # Check for existing user collection entry
        existing = session.exec(
            select(UserMediaEntry).where(
                UserMediaEntry.user_id == user_id,
                UserMediaEntry.media_item_id == media_item.id,
            )
        ).first()

        if existing:
            if skip_duplicates:
                skipped_count += 1
                continue
            else:
                _update_entry_fields(existing, item)
                session.add(existing)
                imported_count += 1
                continue

        # Create new UserMediaEntry
        status_raw = str(item.get("status", "plan_to")).strip().lower()
        try:
            entry_status = TrackingStatus(status_raw)
        except ValueError:
            entry_status = TrackingStatus.PLAN_TO

        rating: Optional[float] = None
        rating_raw = item.get("rating")
        if rating_raw is not None and rating_raw != "":
            try:
                rating = float(rating_raw)
            except (ValueError, TypeError):
                pass

        is_fav = _parse_bool_field(item.get("is_favorite", False))
        tags = _parse_list_field(item.get("tags"))

        now = datetime.now(timezone.utc)
        started_at = (
            now
            if entry_status in (TrackingStatus.IN_PROGRESS, TrackingStatus.COMPLETED)
            else None
        )
        completed_at = now if entry_status == TrackingStatus.COMPLETED else None

        entry = UserMediaEntry(
            user_id=user_id,
            media_item_id=media_item.id,
            status=entry_status,
            rating=rating,
            is_favorite=is_fav,
            playtime_hours=_parse_float_field(item.get("playtime_hours"), 0.0),
            current_episode=_parse_int_field(item.get("current_episode")) or 0,
            current_page=_parse_int_field(item.get("current_page")) or 0,
            rewatch_count=_parse_int_field(item.get("rewatch_count")) or 0,
            notes=str(item.get("notes")) if item.get("notes") is not None else None,
            tags=tags,
            started_at=started_at,
            completed_at=completed_at,
        )
        session.add(entry)
        imported_count += 1

    session.commit()
    return {
        "total": len(items),
        "imported": imported_count,
        "skipped": skipped_count,
    }


def import_collection_csv(
    session: Session,
    user_id: int,
    csv_text: str,
    skip_duplicates: bool = True,
) -> Dict[str, int]:
    """Parse CSV text, extract items, and import into user collection."""
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    rows = list(reader)
    if not rows:
        return {"total": 0, "imported": 0, "skipped": 0}

    return import_collection_json(session, user_id, rows, skip_duplicates=skip_duplicates)

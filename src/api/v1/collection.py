"""
Collection API endpoints for HostCart.
Provides multi-media CRUD, filtering, quick progress increment (+1),
and comprehensive collection analytics for the Statistics tab.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, func, select

from src.api.v1.auth import get_current_user
from src.api.v1.schemas import (
    CollectionEntryCreate,
    CollectionEntryRead,
    CollectionEntryUpdate,
    CollectionStatsResponse,
    MonthlyActivityPoint,
    NameCountMetric,
    QuickIncrementRequest,
    RatingBucket,
)
from src.data.database import get_session
from src.data.models import MediaItem, MediaType, TrackingStatus, User, UserMediaEntry

router = APIRouter(prefix="/collection", tags=["collection"])


@router.get("", response_model=List[CollectionEntryRead])
@router.get("/", response_model=List[CollectionEntryRead])
def list_collection(
    media_type: Optional[MediaType] = Query(default=None),
    status: Optional[TrackingStatus] = Query(default=None),
    search: Optional[str] = Query(default=None),
    tag: Optional[str] = Query(default=None),
    is_favorite: Optional[bool] = Query(default=None),
    min_rating: Optional[float] = Query(default=None, ge=0.0, le=10.0),
    sort_by: Optional[str] = Query(default="updated_at_desc"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> List[CollectionEntryRead]:
    """
    List user collection entries with rich filtering and sorting.
    Strictly isolated: users only see their own collection items.
    """
    stmt = (
        select(UserMediaEntry)
        .options(selectinload(UserMediaEntry.media_item))
        .join(MediaItem, UserMediaEntry.media_item_id == MediaItem.id)
        .where(UserMediaEntry.user_id == current_user.id)
    )

    if media_type is not None:
        stmt = stmt.where(MediaItem.media_type == media_type)

    if status is not None:
        stmt = stmt.where(UserMediaEntry.status == status)

    if is_favorite is not None:
        stmt = stmt.where(UserMediaEntry.is_favorite == is_favorite)

    if min_rating is not None:
        stmt = stmt.where(UserMediaEntry.rating >= min_rating)

    if search:
        search_pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            func.lower(MediaItem.title).like(search_pattern)
            | func.lower(func.coalesce(MediaItem.original_title, "")).like(search_pattern)
        )

    # Sorting
    if sort_by == "title_asc":
        stmt = stmt.order_by(MediaItem.title.asc())
    elif sort_by == "title_desc":
        stmt = stmt.order_by(MediaItem.title.desc())
    elif sort_by == "rating_desc":
        stmt = stmt.order_by(UserMediaEntry.rating.desc().nullslast())
    elif sort_by == "rating_asc":
        stmt = stmt.order_by(UserMediaEntry.rating.asc().nullslast())
    elif sort_by == "created_at_desc":
        stmt = stmt.order_by(UserMediaEntry.created_at.desc())
    elif sort_by == "created_at_asc":
        stmt = stmt.order_by(UserMediaEntry.created_at.asc())
    elif sort_by == "updated_at_asc":
        stmt = stmt.order_by(UserMediaEntry.updated_at.asc())
    else:  # default "updated_at_desc"
        stmt = stmt.order_by(UserMediaEntry.updated_at.desc())

    entries = list(session.exec(stmt).all())

    # Tag filter (in-memory for robust SQLite JSON array matching)
    if tag:
        target_tag = tag.strip().lower()
        entries = [
            e for e in entries
            if e.tags and any(str(t).strip().lower() == target_tag for t in e.tags)
        ]

    return [CollectionEntryRead.model_validate(e) for e in entries]


@router.post("", response_model=CollectionEntryRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=CollectionEntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: CollectionEntryCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CollectionEntryRead:
    """
    Create a new collection entry for the current user.
    Creates or reuses global MediaItem based on external identifiers or title + media_type.
    """
    media_item: Optional[MediaItem] = None

    if payload.media_item_id is not None:
        media_item = session.get(MediaItem, payload.media_item_id)
        if not media_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Referenced media item not found",
            )
    elif payload.media is not None:
        m = payload.media
        # Attempt match by external ID + provider source
        if m.external_id and m.external_source:
            media_item = session.exec(
                select(MediaItem).where(
                    MediaItem.external_id == m.external_id,
                    MediaItem.external_source == m.external_source,
                )
            ).first()

        # If not matched, attempt match by title + media_type
        if not media_item:
            media_item = session.exec(
                select(MediaItem).where(
                    func.lower(MediaItem.title) == m.title.strip().lower(),
                    MediaItem.media_type == m.media_type,
                )
            ).first()

        # If still not found, create new catalog MediaItem
        if not media_item:
            media_item = MediaItem(
                media_type=m.media_type,
                title=m.title.strip(),
                original_title=m.original_title,
                release_year=m.release_year,
                poster_url=m.poster_url,
                backdrop_url=m.backdrop_url,
                summary=m.summary,
                genres=m.genres or [],
                creators=m.creators or [],
                external_id=m.external_id,
                external_source=m.external_source,
                total_episodes=m.total_episodes,
                total_pages=m.total_pages,
                runtime_minutes=m.runtime_minutes,
            )
            session.add(media_item)
            session.flush()

    assert media_item is not None and media_item.id is not None

    # Check if user already tracks this media item
    existing = session.exec(
        select(UserMediaEntry).where(
            UserMediaEntry.user_id == current_user.id,
            UserMediaEntry.media_item_id == media_item.id,
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Media item is already in your collection",
        )

    now = datetime.now(timezone.utc)
    started_at = now if payload.status in (TrackingStatus.IN_PROGRESS, TrackingStatus.COMPLETED) else None
    completed_at = now if payload.status == TrackingStatus.COMPLETED else None

    entry = UserMediaEntry(
        user_id=current_user.id,
        media_item_id=media_item.id,
        status=payload.status,
        rating=payload.rating,
        is_favorite=payload.is_favorite,
        playtime_hours=payload.playtime_hours,
        current_episode=payload.current_episode,
        current_page=payload.current_page,
        rewatch_count=payload.rewatch_count,
        notes=payload.notes,
        tags=payload.tags or [],
        started_at=started_at,
        completed_at=completed_at,
        created_at=now,
        updated_at=now,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)

    # Ensure media_item relationship is loaded
    entry.media_item = media_item
    return CollectionEntryRead.model_validate(entry)


@router.get("/stats", response_model=CollectionStatsResponse)
def get_collection_stats(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CollectionStatsResponse:
    """
    Compute comprehensive media collection analytics for the current user.
    Powers the Statistics & Media Analytics tab.
    """
    entries = list(
        session.exec(
            select(UserMediaEntry)
            .options(selectinload(UserMediaEntry.media_item))
            .where(UserMediaEntry.user_id == current_user.id)
        ).all()
    )

    total_items = len(entries)

    # 1. KPIs
    game_hours = 0.0
    movie_hours = 0.0
    tv_hours = 0.0
    episodes_watched = 0
    pages_read = 0

    for e in entries:
        mt = e.media_item.media_type
        if mt == MediaType.GAME:
            game_hours += e.playtime_hours
        elif mt == MediaType.MOVIE:
            rt = e.media_item.runtime_minutes or 120
            watches = e.rewatch_count + (1 if e.status == TrackingStatus.COMPLETED else 0)
            movie_hours += (rt * watches) / 60.0
        elif mt == MediaType.TV_SHOW:
            episodes_watched += e.current_episode
            rt = e.media_item.runtime_minutes or 45
            tv_hours += (e.current_episode * rt) / 60.0
        elif mt == MediaType.BOOK:
            if e.status == TrackingStatus.COMPLETED and e.media_item.total_pages:
                pages_read += max(e.current_page, e.media_item.total_pages)
            else:
                pages_read += e.current_page

    book_hours = pages_read / 50.0  # 50 pages per hour reading speed
    game_hours = round(game_hours, 1)
    movie_hours = round(movie_hours, 1)
    tv_hours = round(tv_hours, 1)
    book_hours = round(book_hours, 1)
    total_time_hours = round(game_hours + movie_hours + tv_hours + book_hours, 1)

    rated_entries = [e.rating for e in entries if e.rating is not None and e.rating > 0]
    avg_rating = round(sum(rated_entries) / len(rated_entries), 1) if rated_entries else 0.0

    completed_count = sum(1 for e in entries if e.status == TrackingStatus.COMPLETED)
    completion_rate = round(completed_count / total_items * 100, 1) if total_items > 0 else 0.0

    curator_xp = int(
        (total_items * 10)
        + (completed_count * 25)
        + int(game_hours * 2)
        + (episodes_watched * 5)
        + int(pages_read * 0.1)
    )
    curator_level = max(1, curator_xp // 100 + 1)

    # 2. Charts: Status Counts
    status_counts = {st.value: 0 for st in TrackingStatus}
    for e in entries:
        status_counts[e.status.value] += 1

    # 3. Charts: Media Type Counts
    media_type_counts = {mt.value: 0 for mt in MediaType}
    for e in entries:
        media_type_counts[e.media_item.media_type.value] += 1

    # 4. Charts: Time Breakdown
    time_by_media_type = {
        "game": game_hours,
        "movie": movie_hours,
        "tv_show": tv_hours,
        "book": book_hours,
    }

    # 5. Charts: Rating Distribution
    rating_buckets = {"10★": 0, "9★": 0, "8★": 0, "7★": 0, "≤6★": 0}
    for e in entries:
        if e.rating is not None and e.rating > 0:
            if e.rating >= 9.5:
                rating_buckets["10★"] += 1
            elif e.rating >= 8.5:
                rating_buckets["9★"] += 1
            elif e.rating >= 7.5:
                rating_buckets["8★"] += 1
            elif e.rating >= 6.5:
                rating_buckets["7★"] += 1
            else:
                rating_buckets["≤6★"] += 1

    rating_distribution = [
        RatingBucket(label=label, count=cnt)
        for label, cnt in rating_buckets.items()
    ]

    # 6. Charts: Top Genres
    genre_counts: Dict[str, int] = {}
    for e in entries:
        for g in (e.media_item.genres or []):
            g_clean = str(g).strip()
            if g_clean:
                genre_counts[g_clean] = genre_counts.get(g_clean, 0) + 1

    total_genre_occurrences = sum(genre_counts.values())
    sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_genres = [
        NameCountMetric(
            name=g_name,
            count=cnt,
            percentage=round(cnt / total_genre_occurrences * 100, 1) if total_genre_occurrences > 0 else 0.0,
        )
        for g_name, cnt in sorted_genres
    ]

    # 7. Charts: Top Formats
    top_formats = [
        NameCountMetric(
            name=mt.value,
            count=media_type_counts[mt.value],
            percentage=round(media_type_counts[mt.value] / total_items * 100, 1) if total_items > 0 else 0.0,
        )
        for mt in MediaType
    ]

    # 8. Charts: Monthly Activity (last 6 months in chronological order)
    now = datetime.now(timezone.utc)
    month_keys: List[str] = []
    for i in range(5, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        month_keys.append(f"{y:04d}-{m:02d}")

    activity_map = {
        m_key: {"games": 0, "movies": 0, "tv": 0, "books": 0, "total": 0}
        for m_key in month_keys
    }

    for e in entries:
        dt = e.completed_at if (e.status == TrackingStatus.COMPLETED and e.completed_at) else (e.updated_at or e.created_at)
        if dt:
            m_key = dt.strftime("%Y-%m")
            if m_key in activity_map:
                mt = e.media_item.media_type
                if mt == MediaType.GAME:
                    activity_map[m_key]["games"] += 1
                elif mt == MediaType.MOVIE:
                    activity_map[m_key]["movies"] += 1
                elif mt == MediaType.TV_SHOW:
                    activity_map[m_key]["tv"] += 1
                elif mt == MediaType.BOOK:
                    activity_map[m_key]["books"] += 1
                activity_map[m_key]["total"] += 1

    monthly_activity = [
        MonthlyActivityPoint(
            month=m_key,
            games=activity_map[m_key]["games"],
            movies=activity_map[m_key]["movies"],
            tv=activity_map[m_key]["tv"],
            books=activity_map[m_key]["books"],
            total=activity_map[m_key]["total"],
        )
        for m_key in month_keys
    ]

    return CollectionStatsResponse(
        total_items=total_items,
        game_hours=game_hours,
        movie_hours=movie_hours,
        tv_hours=tv_hours,
        episodes_watched=episodes_watched,
        pages_read=pages_read,
        book_hours=book_hours,
        total_time_hours=total_time_hours,
        avg_rating=avg_rating,
        completion_rate=completion_rate,
        curator_xp=curator_xp,
        curator_level=curator_level,
        status_counts=status_counts,
        media_type_counts=media_type_counts,
        time_by_media_type=time_by_media_type,
        rating_distribution=rating_distribution,
        top_genres=top_genres,
        top_formats=top_formats,
        monthly_activity=monthly_activity,
    )


@router.get("/{entry_id}", response_model=CollectionEntryRead)
def get_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CollectionEntryRead:
    """Retrieve a single collection entry by ID. Strictly scoped to current user."""
    entry = session.exec(
        select(UserMediaEntry)
        .options(selectinload(UserMediaEntry.media_item))
        .where(
            UserMediaEntry.id == entry_id,
            UserMediaEntry.user_id == current_user.id,
        )
    ).first()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection entry not found",
        )

    return CollectionEntryRead.model_validate(entry)


@router.put("/{entry_id}", response_model=CollectionEntryRead)
def update_entry(
    entry_id: int,
    payload: CollectionEntryUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CollectionEntryRead:
    """Update a collection entry or its linked media item. Strictly scoped to current user."""
    entry = session.exec(
        select(UserMediaEntry)
        .options(selectinload(UserMediaEntry.media_item))
        .where(
            UserMediaEntry.id == entry_id,
            UserMediaEntry.user_id == current_user.id,
        )
    ).first()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection entry not found",
        )

    now = datetime.now(timezone.utc)

    if payload.status is not None:
        if payload.status == TrackingStatus.COMPLETED and entry.status != TrackingStatus.COMPLETED:
            if not entry.completed_at:
                entry.completed_at = now
            if not entry.started_at:
                entry.started_at = now
        elif payload.status == TrackingStatus.IN_PROGRESS and not entry.started_at:
            entry.started_at = now
        entry.status = payload.status

    if payload.rating is not None:
        entry.rating = payload.rating
    if payload.is_favorite is not None:
        entry.is_favorite = payload.is_favorite
    if payload.playtime_hours is not None:
        entry.playtime_hours = payload.playtime_hours
    if payload.current_episode is not None:
        entry.current_episode = payload.current_episode
    if payload.current_page is not None:
        entry.current_page = payload.current_page
    if payload.rewatch_count is not None:
        entry.rewatch_count = payload.rewatch_count
    if payload.notes is not None:
        entry.notes = payload.notes
    if payload.tags is not None:
        entry.tags = payload.tags

    # Optional linked media item update
    if payload.media is not None and entry.media_item:
        media_updates = payload.media.model_dump(exclude_unset=True)
        for attr, value in media_updates.items():
            if value is not None:
                setattr(entry.media_item, attr, value)
        entry.media_item.updated_at = now
        session.add(entry.media_item)

    entry.updated_at = now
    session.add(entry)
    session.commit()
    session.refresh(entry)

    return CollectionEntryRead.model_validate(entry)


@router.post("/{entry_id}/increment", response_model=CollectionEntryRead)
def quick_increment(
    entry_id: int,
    payload: QuickIncrementRequest = QuickIncrementRequest(),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CollectionEntryRead:
    """
    Quick-increment progress by +amount:
    - Game: playtime_hours += amount
    - Movie: rewatch_count += int(amount)
    - TV Show: current_episode += int(amount); auto-completes when total_episodes reached
    - Book: current_page += int(amount); auto-completes when total_pages reached
    Automatically moves plan_to items to in_progress.
    """
    entry = session.exec(
        select(UserMediaEntry)
        .options(selectinload(UserMediaEntry.media_item))
        .where(
            UserMediaEntry.id == entry_id,
            UserMediaEntry.user_id == current_user.id,
        )
    ).first()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection entry not found",
        )

    now = datetime.now(timezone.utc)
    amount = payload.amount

    # Auto start if status was plan_to
    if entry.status == TrackingStatus.PLAN_TO:
        entry.status = TrackingStatus.IN_PROGRESS
        if not entry.started_at:
            entry.started_at = now

    mt = entry.media_item.media_type
    if mt == MediaType.GAME:
        entry.playtime_hours = round(entry.playtime_hours + amount, 2)
    elif mt == MediaType.MOVIE:
        entry.rewatch_count += int(amount)
    elif mt == MediaType.TV_SHOW:
        entry.current_episode += int(amount)
        if entry.media_item.total_episodes and entry.current_episode >= entry.media_item.total_episodes:
            entry.status = TrackingStatus.COMPLETED
            if not entry.completed_at:
                entry.completed_at = now
    elif mt == MediaType.BOOK:
        entry.current_page += int(amount)
        if entry.media_item.total_pages and entry.current_page >= entry.media_item.total_pages:
            entry.status = TrackingStatus.COMPLETED
            if not entry.completed_at:
                entry.completed_at = now

    entry.updated_at = now
    session.add(entry)
    session.commit()
    session.refresh(entry)

    return CollectionEntryRead.model_validate(entry)


@router.delete("/{entry_id}")
def delete_entry(
    entry_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Delete a collection entry. Strictly scoped to current user."""
    entry = session.exec(
        select(UserMediaEntry).where(
            UserMediaEntry.id == entry_id,
            UserMediaEntry.user_id == current_user.id,
        )
    ).first()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection entry not found",
        )

    session.delete(entry)
    session.commit()

    return {"ok": True, "deleted_id": entry_id}

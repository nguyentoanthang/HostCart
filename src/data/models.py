"""
SQLModel database models and enums for HostCart.
Defines schemas for Users, MediaItems (catalog items), and UserMediaEntries (tracking).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from sqlalchemy import JSON
from sqlmodel import Column, Field, Relationship, SQLModel


class MediaType(str, Enum):
    """Supported multi-media types in HostCart."""
    GAME = "game"
    MOVIE = "movie"
    TV_SHOW = "tv_show"
    BOOK = "book"


class TrackingStatus(str, Enum):
    """Collection tracking status states."""
    PLAN_TO = "plan_to"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    DROPPED = "dropped"
    WISHLIST = "wishlist"


class User(SQLModel, table=True):
    """HostCart user account."""
    __tablename__ = "user"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, nullable=False)
    email: str = Field(index=True, unique=True, nullable=False)
    hashed_password: str = Field(nullable=False)
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    entries: List["UserMediaEntry"] = Relationship(
        back_populates="user",
        cascade_delete=True,
    )


class MediaItem(SQLModel, table=True):
    """Global media catalog item shared across user collections."""
    __tablename__ = "mediaitem"

    id: Optional[int] = Field(default=None, primary_key=True)
    media_type: MediaType = Field(index=True, nullable=False)
    title: str = Field(index=True, nullable=False)
    original_title: Optional[str] = Field(default=None)
    release_year: Optional[int] = Field(default=None)
    poster_url: Optional[str] = Field(default=None)
    backdrop_url: Optional[str] = Field(default=None)
    summary: Optional[str] = Field(default=None)
    genres: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    creators: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    external_id: Optional[str] = Field(default=None, index=True)
    external_source: Optional[str] = Field(default=None)
    total_episodes: Optional[int] = Field(default=None)
    total_pages: Optional[int] = Field(default=None)
    runtime_minutes: Optional[int] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    entries: List["UserMediaEntry"] = Relationship(
        back_populates="media_item",
        cascade_delete=True,
    )


class UserMediaEntry(SQLModel, table=True):
    """User collection tracking record linking a User and a MediaItem."""
    __tablename__ = "usermediaentry"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    media_item_id: int = Field(foreign_key="mediaitem.id", index=True, nullable=False)
    status: TrackingStatus = Field(
        default=TrackingStatus.PLAN_TO, index=True, nullable=False
    )
    rating: Optional[float] = Field(default=None)
    is_favorite: bool = Field(default=False)
    playtime_hours: float = Field(default=0.0)
    current_episode: int = Field(default=0)
    current_page: int = Field(default=0)
    rewatch_count: int = Field(default=0)
    notes: Optional[str] = Field(default=None)
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    user: Optional[User] = Relationship(back_populates="entries")
    media_item: Optional[MediaItem] = Relationship(back_populates="entries")

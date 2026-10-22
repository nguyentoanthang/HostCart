"""
Pydantic schemas for HostCart API v1.
Defines request and response data models for Authentication, MediaItems,
Collection entries, Quick Increments, and Analytics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from src.data.models import MediaType, TrackingStatus


# ==========================================
# Authentication Schemas
# ==========================================


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    is_admin: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


# ==========================================
# Media Item Schemas
# ==========================================


class MediaItemCreate(BaseModel):
    media_type: MediaType
    title: str = Field(min_length=1, max_length=300)
    original_title: Optional[str] = None
    release_year: Optional[int] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    summary: Optional[str] = None
    genres: List[str] = Field(default_factory=list)
    creators: List[str] = Field(default_factory=list)
    external_id: Optional[str] = None
    external_source: Optional[str] = None
    total_episodes: Optional[int] = None
    total_pages: Optional[int] = None
    runtime_minutes: Optional[int] = None


class MediaItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    media_type: MediaType
    title: str
    original_title: Optional[str] = None
    release_year: Optional[int] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    summary: Optional[str] = None
    genres: List[str] = Field(default_factory=list)
    creators: List[str] = Field(default_factory=list)
    external_id: Optional[str] = None
    external_source: Optional[str] = None
    total_episodes: Optional[int] = None
    total_pages: Optional[int] = None
    runtime_minutes: Optional[int] = None
    created_at: datetime
    updated_at: datetime


# ==========================================
# Collection Entry Schemas
# ==========================================


class CollectionEntryCreate(BaseModel):
    media: Optional[MediaItemCreate] = None
    media_item_id: Optional[int] = None
    status: TrackingStatus = TrackingStatus.PLAN_TO
    rating: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    is_favorite: bool = False
    playtime_hours: float = 0.0
    current_episode: int = 0
    current_page: int = 0
    rewatch_count: int = 0
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_media_target(self) -> "CollectionEntryCreate":
        if self.media is None and self.media_item_id is None:
            raise ValueError("Either 'media' or 'media_item_id' must be provided.")
        return self


class CollectionEntryUpdate(BaseModel):
    status: Optional[TrackingStatus] = None
    rating: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    is_favorite: Optional[bool] = None
    playtime_hours: Optional[float] = None
    current_episode: Optional[int] = None
    current_page: Optional[int] = None
    rewatch_count: Optional[int] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    media: Optional[MediaItemCreate] = None


class CollectionEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    user_id: int
    media_item_id: int
    status: TrackingStatus
    rating: Optional[float] = None
    is_favorite: bool = False
    playtime_hours: float = 0.0
    current_episode: int = 0
    current_page: int = 0
    rewatch_count: int = 0
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    media: MediaItemRead = Field(validation_alias=AliasChoices("media", "media_item"))


class QuickIncrementRequest(BaseModel):
    amount: float = 1.0


# ==========================================
# Analytics / Statistics Schemas
# ==========================================


class NameCountMetric(BaseModel):
    name: str
    count: int
    percentage: Optional[float] = None


class MonthlyActivityPoint(BaseModel):
    month: str
    games: int = 0
    movies: int = 0
    tv: int = 0
    books: int = 0
    total: int = 0


class RatingBucket(BaseModel):
    label: str
    count: int = 0


class CollectionStatsResponse(BaseModel):
    # KPIs
    total_items: int
    game_hours: float
    movie_hours: float
    tv_hours: float
    episodes_watched: int
    pages_read: int
    book_hours: float
    total_time_hours: float
    avg_rating: float
    completion_rate: float
    curator_xp: int
    curator_level: int

    # Charts
    status_counts: Dict[str, int]
    media_type_counts: Dict[str, int]
    time_by_media_type: Dict[str, float]
    rating_distribution: List[RatingBucket]
    top_genres: List[NameCountMetric]
    top_formats: List[NameCountMetric]
    monthly_activity: List[MonthlyActivityPoint]

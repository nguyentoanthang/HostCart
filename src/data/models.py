from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

class GameStatus(Enum):
    NOT_PLAYED = "not_played"
    PLAYING = "playing"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    DROPPED = "dropped"
    BACKLOG = "backlog"

class Platform(Enum):
    PC = "pc"
    PLAYSTATION = "playstation"
    XBOX = "xbox"
    NINTENDO_DS = "nintendo ds"
    NINTENDO_3DS = "nintendo 3ds"
    NINTENDO_SWITCH = "nintendo switch"
    NINTENDO_SWITCH_2 = "nintendo switch 2"
    MOBILE = "mobile"
    OTHER = "other"

@dataclass
class Game:
    _game_id: str
    _name: str
    summary: Optional[str]
    release_date: Optional[datetime]
    genres: Optional[List[str]]
    platforms: Optional[List[str]]
    cover_url: Optional[str]
    screenshots: Optional[List[str]]
    developer: Optional[str]
    publisher: Optional[str]
    rating: Optional[float]
    metacritic_score: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    def __init__(self,
               id: str,
               name: str,
               summary: Optional[str] = None,
               release_date: Optional[datetime] = None,
               genres: Optional[List[str]] = None,
               platforms: Optional[List[str]] = None,
               cover_url: Optional[str] = None,
               screenshots: Optional[List[str]] = None,
               developer: Optional[str] = None,
               publisher: Optional[str] = None,
               rating: Optional[float] = None,
               metacritic_score: Optional[int] = None,
               created_at: Optional[datetime] = None,
               updated_at: Optional[datetime] = None):
        # Check id is not empty
        if id == "":
            raise ValueError("game_id must not empty.")
        self._game_id = id

        # Check name is not empty
        if name == "":
            raise ValueError("name must not empty.")
        self._name = name

        self.summary = summary
        self.release_date = release_date
        self.genres = genres
        self.platforms = platforms
        self.cover_url = cover_url
        self.screenshots = screenshots
        self.developer = developer
        self.publisher = publisher
        self.rating = rating
        self.metacritic_score = metacritic_score
        self.created_at = created_at
        self.updated_at = updated_at

    @property
    def game_id(self) -> str:
        """Read-only access to the ID"""
        return self._game_id
    
    @property
    def name(self) -> str:
        """Read-only access to the ID"""
        return self._name

@dataclass
class Tag:
    _id: Optional[int]
    _name: str
    # Optional: Only add if you want these features
    # color: Optional[str] = None          # For UI organization
    # created_at: Optional[datetime] = None # For history tracking
    # category: Optional[str] = None        # For grouping tags
    # description: Optional[str] = None     # For tag documentation

    def __init__(self, name: str, id: Optional[int] = None):
        self._id = id
        self._name = name

    @property
    def id(self) -> Optional[int]:
        """Read-only access to the ID"""
        return self._id

    @property
    def name(self) -> str:
        """Read-only access to the name"""
        return self._name

@dataclass
class UserGame:
    _game: Game
    tags: List[Tag]
    _id: Optional[int]               # sqlite will use default id column
    status: GameStatus
    user_rating: Optional[int]
    user_review: Optional[str]
    played_time: int            # minutes
    date_added: datetime
    date_started: Optional[datetime]
    date_completed: Optional[datetime]
    last_played: Optional[datetime]
    notes: Optional[str]
    igdb_updated_at: Optional[datetime]
    local_refreshed_at: Optional[datetime]

    def __init__(self,
                 game: Game,
                 tags: List[Tag],
                 id: Optional[int] = None,
                 status: GameStatus = GameStatus.NOT_PLAYED,
                 user_rating: Optional[int] = None,
                 user_review: Optional[str] = None,
                 played_time: int = 0,
                 date_added: Optional[datetime] = None,
                 date_started: Optional[datetime] = None,
                 date_completed: Optional[datetime] = None,
                 last_played: Optional[datetime] = None,
                 notes: Optional[str] = None):
        self._game = game
        # Tag must not empty
        if not tags:
            raise ValueError("Tags must not empty.")
        self.tags = tags

        self._id = id
        self.status = status
        self.user_rating = user_rating
        self.user_review = user_review

        # Played time must > 0
        if played_time < 0:
            raise ValueError("played_time must larger than 0.")
        self.played_time = played_time

        if date_added is None:
            self.date_added = datetime.now()
        else:
            self.date_added = date_added
        
        self.date_started = date_started
        self.date_completed = date_completed
        self.last_played = last_played
        self.notes = notes
    
    @property
    def game(self) -> Game:
        """Return the IGDB game id"""
        return self._game

    @property
    def id(self) -> Optional[int]:
        """Read-only access to the ID"""
        return self._id

    def add_tag(self, tag: Tag) -> bool:
        """Add a tag to the game if not already present"""
        if not self.has_tag_by_name(tag.name):
            self.tags.append(tag)
            return True
        return False

    def add_tags(self, tags: List[Tag]) -> int:
        """Add multiple tags to the game, returns count of added tags"""
        added_count = 0
        for tag in tags:
            if self.add_tag(tag):
                added_count += 1
        return added_count

    def remove_tag(self, tag: Tag) -> bool:
        """Remove a tag from the game if present"""
        return self.remove_tag_by_name(tag.name)

    def remove_tag_by_name(self, tag_name: str) -> bool:
        """Remove a tag by its name"""
        for i, tag in enumerate(self.tags):
            if tag.name.lower() == tag_name.lower():
                self.tags.pop(i)
                return True
        return False

    def remove_tags(self, tags: List[Tag]) -> int:
        """Remove multiple tags from the game, returns count of removed tags"""
        removed_count = 0
        for tag in tags:
            if self.remove_tag(tag):
                removed_count += 1
        return removed_count

    def has_tag_by_name(self, tag_name: str) -> bool:
        """Check if the game has a tag with specific name (case-insensitive)"""
        return any(tag.name.lower() == tag_name.lower() for tag in self.tags)

    def get_tag_names(self) -> List[str]:
        """Get list of tag names"""
        return [tag.name for tag in self.tags]

    def clear_tags(self) -> int:
        """Remove all tags and return count of removed tags"""
        count = len(self.tags)
        self.tags.clear()
        return count

    # Convenience methods for special tags
    @property
    def is_wishlisted(self) -> bool:
        """Check if game is in wishlist"""
        return self.has_tag_by_name("Wishlist")

    @property
    def is_favorite(self) -> bool:
        """Check if game is marked as favorite"""
        return self.has_tag_by_name("Favorite")

    def add_to_wishlist(self, wishlist_tag: Tag) -> bool:
        """Add game to wishlist using the wishlist tag"""
        if not self.is_wishlisted:
            return self.add_tag(wishlist_tag)
        return False

    def remove_from_wishlist(self) -> bool:
        """Remove game from wishlist"""
        return self.remove_tag_by_name("Wishlist")

    def add_to_favorites(self, favorite_tag: Tag) -> bool:
        """Add game to favorites using the favorite tag"""
        if not self.is_favorite:
            return self.add_tag(favorite_tag)
        return False

    def remove_from_favorites(self) -> bool:
        """Remove game from favorites"""
        return self.remove_tag_by_name("Favorite")

    def update_playtime(self, additional_minutes: int) -> None:
        """Add playtime and update last_played timestamp"""
        self.played_time += additional_minutes
        self.last_played = datetime.now()

    def mark_as_completed(self) -> None:
        """Mark game as completed and update relevant fields"""
        self.status = GameStatus.COMPLETED
        self.date_completed = datetime.now()

    def get_playtime_hours(self) -> float:
        """Get playtime in hours"""
        return round(self.played_time / 60, 2)

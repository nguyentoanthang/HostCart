import pytest
from datetime import datetime
from src.data.models import Game, UserGame, Tag, GameStatus, Platform

class TestGameStatus:
    """Test GameStatus enum"""
    
    def test_game_status_values(self):
        """Test that GameStatus enum has correct values"""
        assert GameStatus.NOT_PLAYED.value == "not_played"
        assert GameStatus.PLAYING.value == "playing"
        assert GameStatus.COMPLETED.value == "completed"
        assert GameStatus.ON_HOLD.value == "on_hold"
        assert GameStatus.DROPPED.value == "dropped"
        assert GameStatus.BACKLOG.value == "backlog"

class TestPlatform:
    """Test Platform enum"""
    
    def test_platform_values(self):
        """Test that Platform enum has correct values"""
        assert Platform.PC.value == "pc"
        assert Platform.PLAYSTATION.value == "playstation"
        assert Platform.XBOX.value == "xbox"
        assert Platform.NINTENDO_DS.value == "nintendo ds"
        assert Platform.NINTENDO_3DS.value == "nintendo 3ds"
        assert Platform.NINTENDO_SWITCH.value == "nintendo switch"
        assert Platform.NINTENDO_SWITCH_2.value == "nintendo switch 2"
        assert Platform.MOBILE.value == "mobile"
        assert Platform.OTHER.value == "other"

class TestTag:
    """Test Tag dataclass"""
    
    def test_tag_creation_minimal(self):
        """Test creating a tag with minimal required fields"""
        tag = Tag(name="Test Tag", id=1)
        assert tag.name == "Test Tag"
        assert tag.id == 1

class TestGame:
    """Test Game dataclass"""
    
    def test_game_creation_minimal(self, minimal_game):
        """Test creating a game with minimal required fields"""
        assert minimal_game.game_id == "minimal_game"
        assert minimal_game.name == "Minimal Game"
        assert minimal_game.summary is None
        assert minimal_game.release_date is None

    def test_game_creation_with_empty_id(self):
        """Test creating a game with empty id"""
        with pytest.raises(ValueError, match="game_id must not empty."):
            game = Game(id="", name="Test Name")

    def test_game_creation_with_empty_name(self):
        """Test creating a game with empty name"""
        with pytest.raises(ValueError, match="name must not empty."):
            game = Game(id="Test id", name="")
    
    def test_game_creation_full(self, sample_game):
        """Test creating a game with all fields"""
        assert sample_game.game_id == "game_123"
        assert sample_game.name == "Test Game"
        assert sample_game.summary == "A test game for unit testing"
        assert sample_game.release_date == datetime(2023, 1, 15)
        assert sample_game.genres == ["Action", "Adventure"]
        assert sample_game.platforms == ["PC", "PlayStation"]
        assert sample_game.cover_url == "https://example.com/cover.jpg"
        assert len(sample_game.screenshots) == 2
        assert sample_game.developer == "Test Developer"
        assert sample_game.publisher == "Test Publisher"
        assert sample_game.rating == 8.5
        assert sample_game.metacritic_score == 85
    
    def test_game_id_property_readonly(self, sample_game):
        """Test that game_id property is read-only"""
        assert sample_game.game_id == "game_123"
        # Should not be able to set it (no setter)
        with pytest.raises(AttributeError):
            sample_game.game_id = "new_id"
    
    def test_game_name_property_readonly(self, sample_game):
        """Test that name property is read-only"""
        assert sample_game.name == "Test Game"
        # Should not be able to set it (no setter)
        with pytest.raises(AttributeError):
            sample_game.name = "New Name"

class TestUserGame:
    """Test UserGame dataclass"""
    
    def test_user_game_creation_minimal(self, minimal_user_game, sample_tags):
        """Test creating a user game with minimal fields"""
        assert minimal_user_game.game.game_id == "minimal_game"
        assert minimal_user_game.status == GameStatus.NOT_PLAYED
        assert minimal_user_game.played_time == 0
        assert minimal_user_game.tags[0].name == "Test" 
        assert minimal_user_game.date_added is not None  # Should be auto-set

    def test_user_game_creation_with_empty_tags(self, minimal_game):
        """Test creating a user game with empty tags"""
        with pytest.raises(ValueError, match="Tags must not empty."):
            user_game = UserGame(game=minimal_game, tags=[])

    def test_user_game_creation_with_negative_played_time(self, minimal_game):
        """Test creating a user game with empty tags"""
        with pytest.raises(ValueError, match="played_time must larger than 0."):
            user_game = UserGame(game=minimal_game, tags=[Tag("Test Tag")], played_time=-1)
    
    def test_user_game_creation_full(self, sample_user_game):
        """Test creating a user game with all fields"""
        assert sample_user_game.id == 1
        assert sample_user_game.status == GameStatus.PLAYING
        assert sample_user_game.user_rating == 9
        assert sample_user_game.user_review == "Great game!"
        assert sample_user_game.played_time == 120
        assert len(sample_user_game.tags) == 2
        assert sample_user_game.notes == "Need to finish the main quest"
    
    def test_user_game_auto_date_added(self, minimal_game, sample_tags):
        """Test that date_added is automatically set when not provided"""
        before_creation = datetime.now()
        user_game = UserGame(game=minimal_game, tags=sample_tags)
        after_creation = datetime.now()
        
        assert before_creation <= user_game.date_added <= after_creation
    
    def test_user_game_properties_readonly(self, sample_user_game):
        """Test that certain properties are read-only"""
        assert sample_user_game.game.game_id == "game_123"
        assert sample_user_game.id == 1
        
        # Should not be able to set these (no setters)
        with pytest.raises(AttributeError):
            sample_user_game.game = None
        with pytest.raises(AttributeError):
            sample_user_game.id = 2

class TestUserGameTagMethods:
    """Test UserGame tag-related methods"""
    
    def test_add_tag_new(self, minimal_user_game, sample_tags):
        """Test adding a new tag"""
        tag = sample_tags[0]
        result = minimal_user_game.add_tag(tag)
        
        assert result is True
        assert len(minimal_user_game.tags) == 2
        assert minimal_user_game.tags[1].name == tag.name
    
    def test_add_tag_duplicate(self, sample_user_game, sample_tags):
        """Test adding a duplicate tag"""
        # sample_user_game already has "Favorite" and "Wishlist" tags
        favorite_tag = Tag(name="Favorite")
        result = sample_user_game.add_tag(favorite_tag)
        
        assert result is False
        assert len(sample_user_game.tags) == 2  # Should remain unchanged
    
    def test_add_tags_multiple(self, minimal_user_game, sample_tags):
        """Test adding multiple tags"""
        result = minimal_user_game.add_tags(sample_tags)
        
        assert result == 3  # All 3 tags should be added
        assert len(minimal_user_game.tags) == 4
    
    def test_add_tags_some_duplicates(self, sample_user_game, sample_tags):
        """Test adding multiple tags with some duplicates"""
        # sample_user_game already has "Favorite" and "Wishlist"
        # sample_tags contains "Favorite", "Wishlist", and "Multiplayer"
        result = sample_user_game.add_tags(sample_tags)
        
        assert result == 1  # Only "Multiplayer" should be added
        assert len(sample_user_game.tags) == 3
    
    def test_remove_tag_exists(self, sample_user_game, sample_tags):
        """Test removing an existing tag"""
        favorite_tag = sample_tags[0]  # "Favorite"
        result = sample_user_game.remove_tag(favorite_tag)
        
        assert result is True
        assert len(sample_user_game.tags) == 1
        assert not sample_user_game.has_tag_by_name("Favorite")
    
    def test_remove_tag_not_exists(self, sample_user_game):
        """Test removing a non-existent tag"""
        non_existent_tag = Tag(name="NonExistent")
        result = sample_user_game.remove_tag(non_existent_tag)
        
        assert result is False
        assert len(sample_user_game.tags) == 2  # Should remain unchanged
    
    def test_remove_tag_by_name_case_insensitive(self, sample_user_game):
        """Test removing tag by name (case insensitive)"""
        result = sample_user_game.remove_tag_by_name("FAVORITE")
        
        assert result is True
        assert len(sample_user_game.tags) == 1
        assert not sample_user_game.has_tag_by_name("Favorite")
    
    def test_remove_tags_multiple(self, sample_user_game, sample_tags):
        """Test removing multiple tags"""
        tags_to_remove = sample_tags[:2]  # "Favorite" and "Wishlist"
        result = sample_user_game.remove_tags(tags_to_remove)
        
        assert result == 2
        assert len(sample_user_game.tags) == 0
    
    def test_has_tag_by_name_case_insensitive(self, sample_user_game):
        """Test checking for tag existence (case insensitive)"""
        assert sample_user_game.has_tag_by_name("favorite")
        assert sample_user_game.has_tag_by_name("WISHLIST")
        assert sample_user_game.has_tag_by_name("Favorite")
        assert not sample_user_game.has_tag_by_name("NonExistent")
    
    def test_get_tag_names(self, sample_user_game):
        """Test getting list of tag names"""
        tag_names = sample_user_game.get_tag_names()
        
        assert len(tag_names) == 2
        assert "Favorite" in tag_names
        assert "Wishlist" in tag_names
    
    def test_clear_tags(self, sample_user_game):
        """Test clearing all tags"""
        initial_count = len(sample_user_game.tags)
        result = sample_user_game.clear_tags()
        
        assert result == initial_count
        assert len(sample_user_game.tags) == 0

class TestUserGameConvenienceMethods:
    """Test UserGame convenience methods for special tags"""
    
    def test_is_wishlisted_true(self, sample_user_game):
        """Test is_wishlisted when game has Wishlist tag"""
        assert sample_user_game.is_wishlisted is True
    
    def test_is_wishlisted_false(self, minimal_user_game):
        """Test is_wishlisted when game doesn't have Wishlist tag"""
        assert minimal_user_game.is_wishlisted is False
    
    def test_is_favorite_true(self, sample_user_game):
        """Test is_favorite when game has Favorite tag"""
        assert sample_user_game.is_favorite is True
    
    def test_is_favorite_false(self, minimal_user_game):
        """Test is_favorite when game doesn't have Favorite tag"""
        assert minimal_user_game.is_favorite is False
    
    def test_add_to_wishlist_success(self, minimal_user_game, wishlist_tag):
        """Test adding game to wishlist"""
        result = minimal_user_game.add_to_wishlist(wishlist_tag)
        
        assert result is True
        assert minimal_user_game.is_wishlisted is True
    
    def test_add_to_wishlist_already_exists(self, sample_user_game, wishlist_tag):
        """Test adding game to wishlist when already wishlisted"""
        result = sample_user_game.add_to_wishlist(wishlist_tag)
        
        assert result is False
        assert sample_user_game.is_wishlisted is True
    
    def test_remove_from_wishlist_success(self, sample_user_game):
        """Test removing game from wishlist"""
        result = sample_user_game.remove_from_wishlist()
        
        assert result is True
        assert sample_user_game.is_wishlisted is False
    
    def test_remove_from_wishlist_not_wishlisted(self, minimal_user_game):
        """Test removing game from wishlist when not wishlisted"""
        result = minimal_user_game.remove_from_wishlist()
        
        assert result is False
        assert minimal_user_game.is_wishlisted is False
    
    def test_add_to_favorites_success(self, minimal_user_game, favorite_tag):
        """Test adding game to favorites"""
        result = minimal_user_game.add_to_favorites(favorite_tag)
        
        assert result is True
        assert minimal_user_game.is_favorite is True
    
    def test_add_to_favorites_already_exists(self, sample_user_game, favorite_tag):
        """Test adding game to favorites when already favorite"""
        result = sample_user_game.add_to_favorites(favorite_tag)
        
        assert result is False
        assert sample_user_game.is_favorite is True
    
    def test_remove_from_favorites_success(self, sample_user_game):
        """Test removing game from favorites"""
        result = sample_user_game.remove_from_favorites()
        
        assert result is True
        assert sample_user_game.is_favorite is False
    
    def test_remove_from_favorites_not_favorite(self, minimal_user_game):
        """Test removing game from favorites when not favorite"""
        result = minimal_user_game.remove_from_favorites()
        
        assert result is False
        assert minimal_user_game.is_favorite is False

class TestUserGamePlaytimeMethods:
    """Test UserGame playtime-related methods"""
    
    def test_update_playtime(self, sample_user_game):
        """Test updating playtime"""
        initial_playtime = sample_user_game.played_time
        initial_last_played = sample_user_game.last_played
        
        sample_user_game.update_playtime(60)  # Add 1 hour
        
        assert sample_user_game.played_time == initial_playtime + 60
        assert sample_user_game.last_played > initial_last_played
    
    def test_get_playtime_hours(self, sample_user_game):
        """Test getting playtime in hours"""
        # sample_user_game has 120 minutes = 2 hours
        hours = sample_user_game.get_playtime_hours()
        assert hours == 2.0
    
    def test_get_playtime_hours_with_decimals(self, minimal_user_game):
        """Test getting playtime in hours with decimal places"""
        minimal_user_game.played_time = 90  # 1.5 hours
        hours = minimal_user_game.get_playtime_hours()
        assert hours == 1.5
    
    def test_mark_as_completed(self, sample_user_game):
        """Test marking game as completed"""
        initial_status = sample_user_game.status
        
        sample_user_game.mark_as_completed()
        
        assert sample_user_game.status == GameStatus.COMPLETED
        assert sample_user_game.date_completed is not None
        assert sample_user_game.date_completed > sample_user_game.date_added

class TestUserGameEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_user_game_with_none_values(self, minimal_game):
        """Test creating UserGame with None values where allowed"""
        user_game = UserGame(
            game=minimal_game,
            tags=[Tag("Test")],
            user_rating=None,
            user_review=None,
            date_started=None,
            date_completed=None,
            last_played=None,
            notes=None
        )
        
        assert user_game.user_rating is None
        assert user_game.user_review is None
        assert user_game.date_started is None
        assert user_game.date_completed is None
        assert user_game.last_played is None
        assert user_game.notes is None
    
    def test_tag_operations_with_empty_list(self, minimal_user_game):
        """Test tag operations when tags list is empty"""
        assert minimal_user_game.get_tag_names() == ["Test"]
        assert minimal_user_game.clear_tags() == 1
        assert minimal_user_game.clear_tags() == 0
        assert not minimal_user_game.has_tag_by_name("AnyTag")
        assert minimal_user_game.remove_tag_by_name("AnyTag") is False

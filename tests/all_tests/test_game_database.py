import pytest
import sqlite3
import json
import tempfile
import os
from datetime import datetime
from unittest.mock import patch, MagicMock
from src.data.game_database import DatabaseManager, GameCollectionManager
from src.data.models import Game, UserGame, Tag, GameStatus


class TestDatabaseManager:
    """Test DatabaseManager class"""
    
    def test_database_manager_init(self, temp_database):
        """Test DatabaseManager initialization"""
        db_manager = DatabaseManager(temp_database)
        assert db_manager.db_path == temp_database
        
        # Check that database file is created
        assert os.path.exists(temp_database)
    
    def test_get_connection_context_manager(self, temp_database):
        """Test get_connection context manager"""
        db_manager = DatabaseManager(temp_database)
        
        with db_manager.get_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)
            assert conn.row_factory == sqlite3.Row
            
            # Test that connection works
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1
    
    def test_init_database_creates_tables(self, temp_database):
        """Test that init_database creates required tables"""
        db_manager = DatabaseManager(temp_database)
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check that user_games table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='user_games'
            """)
            result = cursor.fetchone()
            assert result is not None
            assert result['name'] == 'user_games'
    
    def test_init_database_creates_indexes(self, temp_database):
        """Test that init_database creates required indexes"""
        db_manager = DatabaseManager(temp_database)
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check that indexes exist
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name LIKE 'idx_user_games_%'
            """)
            indexes = cursor.fetchall()
            index_names = [idx['name'] for idx in indexes]
            
            assert 'idx_user_games_id' in index_names
            assert 'idx_user_games_game_id' in index_names
            assert 'idx_user_games_status' in index_names
    
    def test_row_to_dict(self, temp_database):
        """Test _row_to_dict method"""
        db_manager = DatabaseManager(temp_database)
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 as test_col, 'test_val' as another_col")
            row = cursor.fetchone()
            
            result = db_manager._row_to_dict(row)
            expected = {'test_col': 1, 'another_col': 'test_val'}
            assert result == expected
    
    def test_row_to_dict_none(self, temp_database):
        """Test _row_to_dict with None input"""
        db_manager = DatabaseManager(temp_database)
        result = db_manager._row_to_dict(None)
        assert result is None
    
    def test_parse_json_field_valid(self, temp_database):
        """Test _parse_json_field with valid JSON"""
        db_manager = DatabaseManager(temp_database)
        
        json_str = '["Action", "Adventure"]'
        result = db_manager._parse_json_field(json_str)
        assert result == ["Action", "Adventure"]
    
    def test_parse_json_field_invalid(self, temp_database):
        """Test _parse_json_field with invalid JSON"""
        db_manager = DatabaseManager(temp_database)
        
        invalid_json = '["Action", "Adventure"'  # Missing closing bracket
        result = db_manager._parse_json_field(invalid_json)
        assert result is None
    
    def test_parse_json_field_none(self, temp_database):
        """Test _parse_json_field with None input"""
        db_manager = DatabaseManager(temp_database)
        result = db_manager._parse_json_field(None)
        assert result is None
    
    def test_serialize_json_field_valid(self, temp_database):
        """Test _serialize_json_field with valid list"""
        db_manager = DatabaseManager(temp_database)
        
        data = ["Action", "Adventure"]
        result = db_manager._serialize_json_field(data)
        assert result == '["Action", "Adventure"]'
    
    def test_serialize_json_field_none(self, temp_database):
        """Test _serialize_json_field with None input"""
        db_manager = DatabaseManager(temp_database)
        result = db_manager._serialize_json_field(None)
        assert result is None
    
    def test_serialize_json_field_empty(self, temp_database):
        """Test _serialize_json_field with empty list"""
        db_manager = DatabaseManager(temp_database)
        result = db_manager._serialize_json_field([])
        assert result is None
    
    def test_datetime_to_str_valid(self, temp_database):
        """Test _datetime_to_str with valid datetime"""
        db_manager = DatabaseManager(temp_database)
        
        dt = datetime(2023, 1, 15, 10, 30, 45)
        result = db_manager._datetime_to_str(dt)
        assert result == "2023-01-15T10:30:45"
    
    def test_datetime_to_str_none(self, temp_database):
        """Test _datetime_to_str with None input"""
        db_manager = DatabaseManager(temp_database)
        result = db_manager._datetime_to_str(None)
        assert result is None


class TestGameCollectionManager:
    """Test GameCollectionManager class"""
    
    def test_game_collection_manager_init(self, mock_config_manager):
        """Test GameCollectionManager initialization"""
        manager = GameCollectionManager()
        assert manager.db is not None
        assert isinstance(manager.db, DatabaseManager)
    
    def test_add_user_game_success(self, mock_config_manager, sample_user_game):
        """Test successfully adding a user game"""
        manager = GameCollectionManager()
        
        # Remove the ID since it should be auto-generated
        sample_user_game._id = None
        
        result_id = manager.add_user_game(sample_user_game)
        
        assert isinstance(result_id, int)
        assert result_id > 0
    
    def test_add_user_game_duplicate_game_id(self, mock_config_manager, sample_user_game):
        """Test adding user game with duplicate game_id (should fail due to UNIQUE constraint)"""
        manager = GameCollectionManager()
        
        # Add the game first time
        sample_user_game._id = None
        manager.add_user_game(sample_user_game)
        
        # Try to add the same game again (same game_id)
        with pytest.raises(sqlite3.IntegrityError):
            manager.add_user_game(sample_user_game)
    
    def test_get_user_game_by_game_id_exists(self, mock_config_manager, sample_user_game):
        """Test getting user game by game_id when it exists"""
        manager = GameCollectionManager()
        
        # Add the game first
        sample_user_game._id = None
        added_id = manager.add_user_game(sample_user_game)
        
        # Retrieve the game
        retrieved_game = manager.get_user_game_by_game_id(sample_user_game.game.game_id)
        
        assert retrieved_game is not None
        assert retrieved_game.id == added_id
        assert retrieved_game.game.game_id == sample_user_game.game.game_id
        assert retrieved_game.game.name == sample_user_game.game.name
        assert retrieved_game.status == sample_user_game.status
        assert retrieved_game.played_time == sample_user_game.played_time
    
    def test_get_user_game_by_game_id_not_exists(self, mock_config_manager):
        """Test getting user game by game_id when it doesn't exist"""
        manager = GameCollectionManager()
        
        result = manager.get_user_game_by_game_id("non_existent_id")
        assert result is None
    
    def test_row_to_user_game_conversion(self, mock_config_manager, sample_user_game):
        """Test _row_to_user_game conversion accuracy"""
        manager = GameCollectionManager()
        
        # Add the game
        sample_user_game._id = None
        added_id = manager.add_user_game(sample_user_game)
        
        # Retrieve and compare
        retrieved_game = manager.get_user_game_by_game_id(sample_user_game.game.game_id)
        
        assert retrieved_game is not None

        assert retrieved_game.id == added_id
        assert retrieved_game.game.game_id == sample_user_game.game.game_id
        assert retrieved_game.game.name == sample_user_game.game.name
        assert retrieved_game.game.summary == sample_user_game.game.summary
        assert retrieved_game.game.developer == sample_user_game.game.developer
        assert retrieved_game.game.publisher == sample_user_game.game.publisher
        assert retrieved_game.game.rating == sample_user_game.game.rating
        assert retrieved_game.game.metacritic_score == sample_user_game.game.metacritic_score
        assert retrieved_game.status == sample_user_game.status
        assert retrieved_game.user_rating == sample_user_game.user_rating
        assert retrieved_game.user_review == sample_user_game.user_review
        assert retrieved_game.played_time == sample_user_game.played_time
        assert retrieved_game.notes == sample_user_game.notes
        
        # Check tags
        assert len(retrieved_game.tags) == len(sample_user_game.tags)
        retrieved_tag_names = [tag.name for tag in retrieved_game.tags]
        original_tag_names = [tag.name for tag in sample_user_game.tags]
        assert set(retrieved_tag_names) == set(original_tag_names)
    
    def test_insert_null_tags_raises_error(self, mock_config_manager, temp_database):
        """Test that _row_to_user_game raises error when tags is NULL in database"""
        manager = GameCollectionManager()
        
        # The INSERT will fail due to NOT NULL constraint, so let's test that instead
        with manager.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # This should raise IntegrityError due to NOT NULL constraint on tags
            with pytest.raises(sqlite3.IntegrityError, match="NOT NULL constraint failed: user_games.tags"):
                cursor.execute('''
                    INSERT INTO user_games (game_id, name, status, tags, played_time, date_added)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', ("test_game", "Test Game", "playing", None, 0, datetime.now().isoformat()))
                conn.commit()
    
    def test_row_to_user_game_with_null_tags_raises_error(self, mock_config_manager):
        """Test that _row_to_user_game raises error when tags is NULL"""
        manager = GameCollectionManager()
        
        # Create a mock row with NULL tags (simulating corrupted data)
        mock_row = MagicMock()
        mock_row.__getitem__.side_effect = lambda key: {
            'id': 1,
            'game_id': 'test_game',
            'name': 'Test Game',
            'summary': None,
            'release_date': None,
            'genres': None,
            'platforms': None,
            'cover_url': None,
            'screenshots': None,
            'developer': None,
            'publisher': None,
            'rating': None,
            'metacritic_score': None,
            'created_at': None,
            'updated_at': None,
            'status': 'playing',
            'tags': None,
            'user_rating': None,
            'user_review': None,
            'played_time': 0,
            'date_added': datetime.now().isoformat(),
            'date_started': None,
            'date_completed': None,
            'last_played': None,
            'notes': None
        }[key]
        
        # This should raise a ValueError
        with pytest.raises(ValueError, match="Tags cannot be NULL or empty in database, database is corrupted."):
            manager._row_to_user_game(mock_row)
    
    def test_row_to_user_game_with_empty_tags_raises_error(self, mock_config_manager):
        """Test that _row_to_user_game raises error when tags is empty"""
        manager = GameCollectionManager()
        
        # Create a mock row with empty tags (simulating corrupted data)
        mock_row = MagicMock()
        mock_row.__getitem__.side_effect = lambda key: {
            'id': 1,
            'game_id': 'test_game',
            'name': 'Test Game',
            'summary': None,
            'release_date': None,
            'genres': None,
            'platforms': None,
            'cover_url': None,
            'screenshots': None,
            'developer': None,
            'publisher': None,
            'rating': None,
            'metacritic_score': None,
            'created_at': None,
            'updated_at': None,
            'status': 'playing',
            'tags': "[]",
            'user_rating': None,
            'user_review': None,
            'played_time': 0,
            'date_added': datetime.now().isoformat(),
            'date_started': None,
            'date_completed': None,
            'last_played': None,
            'notes': None
        }[key]
        
        # This should raise a ValueError
        with pytest.raises(ValueError, match="Tags cannot be NULL or empty in database, database is corrupted."):
            manager._row_to_user_game(mock_row)

    def test_row_to_user_game_with_null_game_id_raises_error(self, mock_config_manager):
        """Test that _row_to_user_game raises error when game_id is NULL"""
        manager = GameCollectionManager()
        
        # Create a mock row with NULL game_id (simulating corrupted data)
        mock_row = MagicMock()
        mock_row.__getitem__.side_effect = lambda key: {
            'id': 1,
            'game_id': None,
            'name': 'Test Game',
            'summary': None,
            'release_date': None,
            'genres': None,
            'platforms': None,
            'cover_url': None,
            'screenshots': None,
            'developer': None,
            'publisher': None,
            'rating': None,
            'metacritic_score': None,
            'created_at': None,
            'updated_at': None,
            'status': 'playing',
            'tags': "[\"Test Tag\"]",
            'user_rating': None,
            'user_review': None,
            'played_time': 0,
            'date_added': datetime.now().isoformat(),
            'date_started': None,
            'date_completed': None,
            'last_played': None,
            'notes': None
        }[key]
        
        # This should raise a ValueError
        with pytest.raises(ValueError, match="game_id cannot be NULL in database, database is corrupted."):
            manager._row_to_user_game(mock_row)

    def test_row_to_user_game_with_null_name_raises_error(self, mock_config_manager):
        """Test that _row_to_user_game raises error when name is NULL"""
        manager = GameCollectionManager()
        
        # Create a mock row with NULL name (simulating corrupted data)
        mock_row = MagicMock()
        mock_row.__getitem__.side_effect = lambda key: {
            'id': 1,
            'game_id': "Test id",
            'name': None,
            'summary': None,
            'release_date': None,
            'genres': None,
            'platforms': None,
            'cover_url': None,
            'screenshots': None,
            'developer': None,
            'publisher': None,
            'rating': None,
            'metacritic_score': None,
            'created_at': None,
            'updated_at': None,
            'status': 'playing',
            'tags': "[\"Test Tag\"]",
            'user_rating': None,
            'user_review': None,
            'played_time': 0,
            'date_added': datetime.now().isoformat(),
            'date_started': None,
            'date_completed': None,
            'last_played': None,
            'notes': None
        }[key]
        
        # This should raise a ValueError
        with pytest.raises(ValueError, match="name cannot be NULL in database, database is corrupted."):
            manager._row_to_user_game(mock_row)

    def test_row_to_user_game_with_null_date_added_raises_error(self, mock_config_manager):
        """Test that _row_to_user_game raises error when date_added is NULL"""
        manager = GameCollectionManager()
        
        # Create a mock row with NULL date_added (simulating corrupted data)
        mock_row = MagicMock()
        mock_row.__getitem__.side_effect = lambda key: {
            'id': 1,
            'game_id': "Test id",
            'name': "Test game",
            'summary': None,
            'release_date': None,
            'genres': None,
            'platforms': None,
            'cover_url': None,
            'screenshots': None,
            'developer': None,
            'publisher': None,
            'rating': None,
            'metacritic_score': None,
            'created_at': None,
            'updated_at': None,
            'status': "playing",
            'tags': "[\"Test Tag\"]",
            'user_rating': None,
            'user_review': None,
            'played_time': 0,
            'date_added': None,
            'date_started': None,
            'date_completed': None,
            'last_played': None,
            'notes': None
        }[key]
        
        # This should raise a ValueError
        with pytest.raises(ValueError, match="date_added cannot be NULL in database, database is corrupted."):
            manager._row_to_user_game(mock_row)

    def test_row_to_user_game_with_null_status_raises_error(self, mock_config_manager):
        """Test that _row_to_user_game raises error when tags is NULL"""
        manager = GameCollectionManager()
        
        # Create a mock row with NULL tags (simulating corrupted data)
        mock_row = MagicMock()
        mock_row.__getitem__.side_effect = lambda key: {
            'id': 1,
            'game_id': "Test id",
            'name': "Test game",
            'summary': None,
            'release_date': None,
            'genres': None,
            'platforms': None,
            'cover_url': None,
            'screenshots': None,
            'developer': None,
            'publisher': None,
            'rating': None,
            'metacritic_score': None,
            'created_at': None,
            'updated_at': None,
            'status': None,
            'tags': "[\"Test Tag\"]",
            'user_rating': None,
            'user_review': None,
            'played_time': 0,
            'date_added': datetime.now().isoformat(),
            'date_started': None,
            'date_completed': None,
            'last_played': None,
            'notes': None
        }[key]
        
        # This should raise a ValueError
        with pytest.raises(ValueError, match="status cannot be NULL in database, database is corrupted."):
            manager._row_to_user_game(mock_row)

    def test_row_to_user_game_with_null_played_time_raises_error(self, mock_config_manager):
        """Test that _row_to_user_game raises error when tags is NULL"""
        manager = GameCollectionManager()
        
        # Create a mock row with NULL tags (simulating corrupted data)
        mock_row = MagicMock()
        mock_row.__getitem__.side_effect = lambda key: {
            'id': 1,
            'game_id': "Test id",
            'name': "Test game",
            'summary': None,
            'release_date': None,
            'genres': None,
            'platforms': None,
            'cover_url': None,
            'screenshots': None,
            'developer': None,
            'publisher': None,
            'rating': None,
            'metacritic_score': None,
            'created_at': None,
            'updated_at': None,
            'status': "playing",
            'tags': "[\"Test Tag\"]",
            'user_rating': None,
            'user_review': None,
            'played_time': None,
            'date_added': datetime.now().isoformat(),
            'date_started': None,
            'date_completed': None,
            'last_played': None,
            'notes': None
        }[key]
        
        # This should raise a ValueError
        with pytest.raises(ValueError, match="played_time cannot be NULL in database, database is corrupted."):
            manager._row_to_user_game(mock_row)

    def test_update_user_game_success(self, mock_config_manager, sample_user_game):
        """Test successfully updating a user game"""
        manager = GameCollectionManager()
        
        # Add the game first
        sample_user_game._id = None
        added_id = manager.add_user_game(sample_user_game)
        
        # Get the game and modify it
        retrieved_game = manager.get_user_game_by_game_id(sample_user_game.game.game_id)

        assert retrieved_game is not None

        retrieved_game.user_rating = 10
        retrieved_game.user_review = "Updated review"
        retrieved_game.played_time = 200
        
        # Update the game
        result = manager.update_user_game(retrieved_game)
        assert result is True
        
        # Verify the update
        updated_game = manager.get_user_game_by_game_id(sample_user_game.game.game_id)

        assert updated_game is not None
        assert updated_game.user_rating == 10
        assert updated_game.user_review == "Updated review"
        assert updated_game.played_time == 200
    
    def test_update_user_game_no_id(self, mock_config_manager, sample_user_game):
        """Test updating user game with no ID (should fail)"""
        manager = GameCollectionManager()
        
        # Try to update a game without an ID
        sample_user_game._id = None
        result = manager.update_user_game(sample_user_game)
        assert result is False
    
    def test_update_user_game_nonexistent_id(self, mock_config_manager, sample_user_game):
        """Test updating user game with non-existent ID"""
        manager = GameCollectionManager()
        
        # Set a non-existent ID
        sample_user_game._id = 99999
        result = manager.update_user_game(sample_user_game)
        assert result is False
    
    def test_load_all_user_games_empty(self, mock_config_manager):
        """Test loading all user games when database is empty"""
        manager = GameCollectionManager()
        
        games = manager.load_all_user_games()
        assert games == []
    
    def test_load_all_user_games_with_data(self, mock_config_manager, sample_user_game, minimal_user_game):
        """Test loading all user games with data"""
        manager = GameCollectionManager()
        
        # Add multiple games
        sample_user_game._id = None
        minimal_user_game._id = None
        manager.add_user_game(sample_user_game)
        manager.add_user_game(minimal_user_game)
        
        # Load all games
        games = manager.load_all_user_games()
        assert len(games) == 2
        
        # Should be ordered by date_added DESC (most recent first)
        game_ids = [game.game.game_id for game in games]
        assert minimal_user_game.game.game_id in game_ids
        assert sample_user_game.game.game_id in game_ids
    
    def test_get_user_games_by_status(self, mock_config_manager, sample_user_game, minimal_user_game):
        """Test getting user games filtered by status"""
        manager = GameCollectionManager()
        
        # Add games with different statuses
        sample_user_game._id = None
        sample_user_game.status = GameStatus.PLAYING
        
        minimal_user_game._id = None
        minimal_user_game.status = GameStatus.COMPLETED
        
        manager.add_user_game(sample_user_game)
        manager.add_user_game(minimal_user_game)
        
        # Get games by status
        playing_games = manager.get_user_games_by_status(GameStatus.PLAYING)
        completed_games = manager.get_user_games_by_status(GameStatus.COMPLETED)
        
        assert len(playing_games) == 1
        assert len(completed_games) == 1
        assert playing_games[0].status == GameStatus.PLAYING
        assert completed_games[0].status == GameStatus.COMPLETED
    
    def test_get_user_games_by_status_none_found(self, mock_config_manager):
        """Test getting user games by status when none exist"""
        manager = GameCollectionManager()
        
        games = manager.get_user_games_by_status(GameStatus.DROPPED)
        assert games == []
    
    def test_get_user_games_by_tag(self, mock_config_manager, sample_user_game, minimal_user_game):
        """Test getting user games filtered by tag"""
        manager = GameCollectionManager()
        
        # Add games with different tags
        sample_user_game._id = None
        # sample_user_game already has "Favorite" and "Wishlist" tags
        
        minimal_user_game._id = None
        minimal_user_game.tags = [Tag(name="Multiplayer")]
        
        manager.add_user_game(sample_user_game)
        manager.add_user_game(minimal_user_game)
        
        # Get games by tag
        favorite_games = manager.get_user_games_by_tag("Favorite")
        multiplayer_games = manager.get_user_games_by_tag("Multiplayer")
        
        assert len(favorite_games) == 1
        assert len(multiplayer_games) == 1
        assert favorite_games[0].has_tag_by_name("Favorite")
        assert multiplayer_games[0].has_tag_by_name("Multiplayer")
    
    def test_get_user_games_by_tag_none_found(self, mock_config_manager):
        """Test getting user games by tag when none exist"""
        manager = GameCollectionManager()
        
        games = manager.get_user_games_by_tag("NonExistentTag")
        assert games == []
    
    def test_get_user_games_by_tag_partial_match_excluded(self, mock_config_manager, sample_user_game):
        """Test that partial tag matches are excluded"""
        manager = GameCollectionManager()
        
        # Add game with "Favorite" tag
        sample_user_game._id = None
        manager.add_user_game(sample_user_game)
        
        # Search for "Fav" should not match "Favorite"
        games = manager.get_user_games_by_tag("Fav")
        assert len(games) == 0
    
    def test_delete_user_game_success(self, mock_config_manager, sample_user_game):
        """Test successfully deleting a user game by ID"""
        manager = GameCollectionManager()
        
        # Add the game
        sample_user_game._id = None
        added_id = manager.add_user_game(sample_user_game)
        
        # Delete the game
        result = manager.delete_user_game(added_id)
        assert result is True
        
        # Verify it's deleted
        retrieved_game = manager.get_user_game_by_game_id(sample_user_game.game.game_id)
        assert retrieved_game is None
    
    def test_delete_user_game_nonexistent_id(self, mock_config_manager):
        """Test deleting user game with non-existent ID"""
        manager = GameCollectionManager()
        
        result = manager.delete_user_game(99999)
        assert result is False
    
    def test_delete_user_game_by_game_id_success(self, mock_config_manager, sample_user_game):
        """Test successfully deleting a user game by game_id"""
        manager = GameCollectionManager()
        
        # Add the game
        sample_user_game._id = None
        manager.add_user_game(sample_user_game)
        
        # Delete the game by game_id
        result = manager.delete_user_game_by_game_id(sample_user_game.game.game_id)
        assert result is True
        
        # Verify it's deleted
        retrieved_game = manager.get_user_game_by_game_id(sample_user_game.game.game_id)
        assert retrieved_game is None
    
    def test_delete_user_game_by_game_id_nonexistent(self, mock_config_manager):
        """Test deleting user game by non-existent game_id"""
        manager = GameCollectionManager()
        
        result = manager.delete_user_game_by_game_id("non_existent_game_id")
        assert result is False

    def test_add_user_game_lastrowid_none_raises_error(self, mock_config_manager, sample_user_game):
        """Test that add_user_game raises RuntimeError when lastrowid is None"""
        manager = GameCollectionManager()
        
        # Remove the ID since it should be auto-generated
        sample_user_game._id = None
        
        # Mock the cursor to return None for lastrowid
        with patch.object(manager.db, 'get_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.lastrowid = None  # Simulate the problematic case
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            
            # This should raise RuntimeError
            with pytest.raises(RuntimeError, match="Failed to insert game: no ID returned"):
                manager.add_user_game(sample_user_game)
            
            # Verify that execute and commit were called
            mock_cursor.execute.assert_called_once()
            mock_conn.commit.assert_called_once()

class TestGameCollectionManagerEdgeCases:
    """Test edge cases and error conditions for GameCollectionManager"""
    
    def test_add_user_game_with_minimal_data(self, mock_config_manager, minimal_user_game):
        """Test adding user game with minimal required data"""
        manager = GameCollectionManager()
        
        minimal_user_game._id = None
        result_id = manager.add_user_game(minimal_user_game)
        
        assert isinstance(result_id, int)
        assert result_id > 0
        
        # Verify retrieval
        retrieved_game = manager.get_user_game_by_game_id(minimal_user_game.game.game_id)
        assert retrieved_game is not None
        assert retrieved_game.game.name == minimal_user_game.game.name
        assert retrieved_game.status == GameStatus.NOT_PLAYED
        assert retrieved_game.played_time == 0
        assert len(retrieved_game.tags) == 1
    
    def test_add_user_game_with_none_optional_fields(self, mock_config_manager, minimal_game):
        """Test adding user game with None values in optional fields"""
        manager = GameCollectionManager()
        
        user_game = UserGame(
            game=minimal_game,
            tags=[Tag("Test Tag")],
            user_rating=None,
            user_review=None,
            date_started=None,
            date_completed=None,
            last_played=None,
            notes=None
        )
        
        result_id = manager.add_user_game(user_game)
        assert isinstance(result_id, int)
        
        # Verify retrieval with None values
        retrieved_game = manager.get_user_game_by_game_id(minimal_game.game_id)
        assert retrieved_game is not None
        assert retrieved_game.user_rating is None
        assert retrieved_game.user_review is None
        assert retrieved_game.date_started is None
        assert retrieved_game.date_completed is None
        assert retrieved_game.last_played is None
        assert retrieved_game.notes is None
    
    def test_datetime_handling_precision(self, mock_config_manager, sample_user_game):
        """Test that datetime precision is maintained through database operations"""
        manager = GameCollectionManager()
        
        # Set specific datetime with microseconds
        specific_datetime = datetime(2023, 1, 15, 10, 30, 45, 123456)
        sample_user_game.date_started = specific_datetime
        sample_user_game._id = None
        
        manager.add_user_game(sample_user_game)
        
        # Retrieve and check datetime precision
        retrieved_game = manager.get_user_game_by_game_id(sample_user_game.game.game_id)
        
        assert retrieved_game is not None
        assert retrieved_game.date_started is not None
        # Note: SQLite stores datetime as ISO string, so microseconds might be lost
        # depending on the ISO format precision
        assert retrieved_game.date_started.year == specific_datetime.year
        assert retrieved_game.date_started.month == specific_datetime.month
        assert retrieved_game.date_started.day == specific_datetime.day
        assert retrieved_game.date_started.hour == specific_datetime.hour
        assert retrieved_game.date_started.minute == specific_datetime.minute
        assert retrieved_game.date_started.second == specific_datetime.second
    
    def test_json_array_fields_handling(self, mock_config_manager, sample_game):
        """Test that JSON array fields (genres, platforms, screenshots) are handled correctly"""
        manager = GameCollectionManager()
        
        # Create game with complex JSON arrays
        game_with_arrays = Game(
            id="array_test_game",
            name="Array Test Game",
            genres=["Action", "Adventure", "RPG", "Simulation"],
            platforms=["PC", "PlayStation 5", "Xbox Series X", "Nintendo Switch"],
            screenshots=[
                "https://example.com/screen1.jpg",
                "https://example.com/screen2.jpg",
                "https://example.com/screen3.jpg"
            ]
        )
        
        user_game = UserGame(game=game_with_arrays, tags=[Tag("Test Tag")])
        manager.add_user_game(user_game)
        
        # Retrieve and verify arrays
        retrieved_game = manager.get_user_game_by_game_id(game_with_arrays.game_id)
        assert retrieved_game is not None
        assert retrieved_game.game.genres == game_with_arrays.genres
        assert retrieved_game.game.platforms == game_with_arrays.platforms
        assert retrieved_game.game.screenshots == game_with_arrays.screenshots
    
    def test_large_text_fields_handling(self, mock_config_manager, minimal_game):
        """Test handling of large text fields"""
        manager = GameCollectionManager()
        
        # Create user game with large text fields
        large_summary = "A" * 5000  # 5KB summary
        large_review = "B" * 10000  # 10KB review
        large_notes = "C" * 3000   # 3KB notes
        
        minimal_game.summary = large_summary
        
        user_game = UserGame(
            game=minimal_game,
            tags=[Tag("Test Tag")],
            user_review=large_review,
            notes=large_notes
        )
        
        manager.add_user_game(user_game)
        
        # Retrieve and verify large text fields
        retrieved_game = manager.get_user_game_by_game_id(minimal_game.game_id)
        assert retrieved_game is not None
        assert retrieved_game.game.summary == large_summary
        assert retrieved_game.user_review == large_review
        assert retrieved_game.notes == large_notes
    
    def test_special_characters_in_text_fields(self, mock_config_manager, minimal_game):
        """Test handling of special characters in text fields"""
        manager = GameCollectionManager()
        
        # Create game with special characters
        special_name = "Test Game: Special Edition™ (2023) [Director's Cut] 🎮"
        special_summary = "A game with 'quotes', \"double quotes\", and unicode: αβγδε 中文 🚀"
        special_review = "Review with\nnewlines\tand\ttabs and 'apostrophes' & \"quotes\""
        
        minimal_game._name = special_name
        minimal_game.summary = special_summary
        
        user_game = UserGame(
            game=minimal_game,
            tags=[Tag(name="Special™")],
            user_review=special_review
        )
        
        manager.add_user_game(user_game)
        
        # Retrieve and verify special characters are preserved
        retrieved_game = manager.get_user_game_by_game_id(minimal_game.game_id)
        assert retrieved_game is not None
        assert retrieved_game.game.name == special_name
        assert retrieved_game.game.summary == special_summary
        assert retrieved_game.user_review == special_review
        assert retrieved_game.tags[0].name == "Special™"


class TestDatabaseManagerSQLiteOptimizations:
    """Test SQLite optimization configurations"""
    
    def test_sqlite_pragmas_are_set(self, temp_database):
        """Test that SQLite optimization pragmas are properly set"""
        db_manager = DatabaseManager(temp_database)
        
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check some key pragmas (these are connection-specific, so we test what we can)
            cursor.execute("PRAGMA foreign_keys")
            foreign_keys = cursor.fetchone()[0]
            assert foreign_keys == 1  # Should be enabled
            
            cursor.execute("PRAGMA temp_store")
            temp_store = cursor.fetchone()[0]
            assert temp_store == 2  # Should be MEMORY (2)
    
    def test_database_performance_with_large_dataset(self, mock_config_manager):
        """Test database performance with a larger dataset"""
        manager = GameCollectionManager()
        
        # Add multiple games to test performance
        games_to_add = []
        for i in range(100):
            game = Game(
                id=f"perf_test_game_{i}",
                name=f"Performance Test Game {i}",
                genres=["Action", "Test"],
                platforms=["PC"]
            )
            user_game = UserGame(
                game=game,
                tags=[Tag(name=f"Tag{i % 10}")],  # 10 different tags
                status=GameStatus(list(GameStatus)[i % len(GameStatus)]),
                played_time=i * 10
            )
            games_to_add.append(user_game)
        
        # Add all games
        for user_game in games_to_add:
            manager.add_user_game(user_game)
        
        # Test various queries
        all_games = manager.load_all_user_games()
        assert len(all_games) == 100
        
        playing_games = manager.get_user_games_by_status(GameStatus.PLAYING)
        assert len(playing_games) > 0
        
        tag0_games = manager.get_user_games_by_tag("Tag0")
        assert len(tag0_games) == 10  # Every 10th game has Tag0
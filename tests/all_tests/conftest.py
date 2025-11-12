import pytest
import tempfile
import os
import json
import shutil
from unittest.mock import patch
from pathlib import Path
from datetime import datetime
from src.data.game_database import Game, Tag, UserGame, GameStatus

#########################################
# New fixtures for Config Managertesting
#########################################

@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for config files during testing"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def temp_config_file(temp_config_dir):
    """Create a temporary config file path"""
    config_file = os.path.join(temp_config_dir, "config.json")
    return config_file

@pytest.fixture
def sample_config_data():
    """Sample configuration data for testing"""
    return {
        "igdb": {
            "token_timestamp": "2023-01-01T00:00:00Z",
            "data_refresh_limit": 5
        },
        "server": {},
        "web_ui": {},
        "database": {}
    }

@pytest.fixture
def config_file_with_data(temp_config_file, sample_config_data):
    """Create a config file with sample data"""
    os.makedirs(os.path.dirname(temp_config_file), exist_ok=True)
    with open(temp_config_file, 'w') as f:
        json.dump(sample_config_data, f)
    return temp_config_file

@pytest.fixture
def mock_env_vars():
    """Mock environment variables for IGDB config"""
    env_vars = {
        'IGDB_CLIENT_ID': 'test_client_id',
        'IGDB_CLIENT_SECRET': 'test_client_secret',
        'IGDB_AUTH_TOKEN': 'test_auth_token'
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars

@pytest.fixture(autouse=True)
def reset_config_manager():
    """Reset ConfigManager singleton between tests"""
    from src.utils.config_manager import ConfigManager
    ConfigManager._instance = None
    ConfigManager._config = None
    yield
    ConfigManager._instance = None
    ConfigManager._config = None

@pytest.fixture
def mock_config_file_path():
    """Mock the CONFIG_FILE path"""
    def _mock_path(path):
        return patch('src.utils.config_manager.CONFIG_FILE', path)
    return _mock_path

@pytest.fixture
def mock_database_file_path():
    """Mock the CONFIG_FILE path"""
    def _mock_path(path):
        return patch('src.utils.config_manager.DATABASE_FILE', path)
    return _mock_path

@pytest.fixture
def dummy_database_file():
    """Create the dummy database file"""
    temp_dir = tempfile.mkdtemp()
    database_file = os.path.join(temp_dir, "data.db")
    yield database_file
    shutil.rmtree(temp_dir)

##############################################
# New fixtures for models and database testing
##############################################

@pytest.fixture
def sample_game():
    """Create a sample Game instance for testing"""
    return Game(
        id="game_123",
        name="Test Game",
        summary="A test game for unit testing",
        release_date=datetime(2023, 1, 15),
        genres=["Action", "Adventure"],
        platforms=["PC", "PlayStation"],
        cover_url="https://example.com/cover.jpg",
        screenshots=["https://example.com/screen1.jpg", "https://example.com/screen2.jpg"],
        developer="Test Developer",
        publisher="Test Publisher",
        rating=8.5,
        metacritic_score=85,
        created_at=datetime(2023, 1, 1),
        updated_at=datetime(2023, 1, 10)
    )

@pytest.fixture
def sample_tags():
    """Create sample Tag instances for testing"""
    return [
        Tag(name="Favorite"),
        Tag(name="Wishlist"),
        Tag(name="Multiplayer")
    ]

@pytest.fixture
def sample_user_game(sample_game, sample_tags):
    """Create a sample UserGame instance for testing"""
    return UserGame(
        game=sample_game,
        tags=sample_tags[:2],  # Use first two tags
        id=1,
        status=GameStatus.PLAYING,
        user_rating=9,
        user_review="Great game!",
        played_time=120,  # 2 hours
        date_added=datetime(2023, 1, 5),
        date_started=datetime(2023, 1, 6),
        date_completed=None,
        last_played=datetime(2023, 1, 10),
        notes="Need to finish the main quest"
    )

@pytest.fixture
def temp_database():
    """Create a temporary database file for testing"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_game_collection.db")
    yield db_path
    shutil.rmtree(temp_dir)

@pytest.fixture
def mock_config_manager(temp_database):
    """Mock ConfigManager to return test database path"""
    with patch('src.data.game_database.ConfigManager') as mock_config:
        mock_config_instance = mock_config.return_value
        mock_config_instance.get_config.return_value.database.db_file = temp_database
        yield mock_config_instance

@pytest.fixture
def wishlist_tag():
    """Create a Wishlist tag for testing"""
    return Tag(name="Wishlist")

@pytest.fixture
def favorite_tag():
    """Create a Favorite tag for testing"""
    return Tag(name="Favorite")

@pytest.fixture
def minimal_game():
    """Create a minimal Game instance with only required fields"""
    return Game(
        id="minimal_game",
        name="Minimal Game"
    )

@pytest.fixture
def minimal_user_game(minimal_game):
    """Create a minimal UserGame instance with only required fields"""
    return UserGame(
        game=minimal_game,
        tags=[Tag("Test")]
    )

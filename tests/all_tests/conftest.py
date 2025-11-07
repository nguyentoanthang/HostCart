import pytest
import tempfile
import os
import json
import shutil
from unittest.mock import patch
from pathlib import Path

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

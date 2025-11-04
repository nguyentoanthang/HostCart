import pytest
import json
import os
from unittest.mock import patch, mock_open, MagicMock

from src.utils.config_manager import (
    IGDBConfig, 
    WebUIConfig, 
    DatabaseConfig, 
    ServerConfig, 
    ConfigData, 
    ConfigManager,
    DATABASE_FILE,
    HOST,
    PORT
)

class TestIGDBConfig:
    """Test IGDBConfig dataclass"""
    
    def test_igdb_config_init_with_defaults(self, mock_env_vars):
        """Test IGDBConfig initialization with default values"""
        config = IGDBConfig()
        assert config.token_timestamp == ""
        assert config.data_refresh_limit == 1
        assert config.client_id == "test_client_id"
        assert config.client_secret == "test_client_secret"
        assert config.auth_token == "test_auth_token"
    
    def test_igdb_config_init_with_values(self, mock_env_vars):
        """Test IGDBConfig initialization with custom values"""
        config = IGDBConfig(
            token_timestamp="2023-01-01T00:00:00Z",
            data_refresh_limit=5
        )
        assert config.token_timestamp == "2023-01-01T00:00:00Z"
        assert config.data_refresh_limit == 5
        assert config.client_id == "test_client_id"
        assert config.client_secret == "test_client_secret"
        assert config.auth_token == "test_auth_token"
    
    def test_igdb_config_init_with_kwargs(self, mock_env_vars):
        """Test IGDBConfig initialization ignoring extra kwargs"""
        config = IGDBConfig(
            token_timestamp="2023-01-01T00:00:00Z",
            data_refresh_limit=3,
            extra_field="ignored"
        )
        assert config.token_timestamp == "2023-01-01T00:00:00Z"
        assert config.data_refresh_limit == 3
    
    def test_igdb_config_post_init_with_env_vars(self, mock_env_vars):
        """Test IGDBConfig __post_init__ with environment variables"""
        config = IGDBConfig()
        assert config.client_id == "test_client_id"
        assert config.client_secret == "test_client_secret"
        assert config.auth_token == "test_auth_token"
    
    def test_igdb_config_post_init_missing_client_id(self):
        """Test IGDBConfig __post_init__ missing IGDB_CLIENT_ID"""
        env_vars = {
            'IGDB_CLIENT_SECRET': 'test_client_secret',
            'IGDB_AUTH_TOKEN': 'test_auth_token'
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError, match="IGDB_CLIENT_ID environment variable is required"):
                IGDBConfig()
    
    def test_igdb_config_post_init_missing_client_secret(self):
        """Test IGDBConfig __post_init__ missing IGDB_CLIENT_SECRET"""
        env_vars = {
            'IGDB_CLIENT_ID': 'test_client_id',
            'IGDB_AUTH_TOKEN': 'test_auth_token'
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError, match="IGDB_CLIENT_SECRET environment variable is required"):
                IGDBConfig()
    
    def test_igdb_config_post_init_missing_auth_token(self):
        """Test IGDBConfig __post_init__ missing IGDB_AUTH_TOKEN"""
        env_vars = {
            'IGDB_CLIENT_ID': 'test_client_id',
            'IGDB_CLIENT_SECRET': 'test_client_secret'
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValueError, match="IGDB_AUTH_TOKEN environment variable is required"):
                IGDBConfig()
    
    def test_igdb_config_post_init_missing_all_env_vars(self):
        """Test IGDBConfig __post_init__ missing all environment variables"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="IGDB_CLIENT_ID environment variable is required"):
                IGDBConfig()
    
    def test_igdb_config_properties(self, mock_env_vars):
        """Test IGDBConfig property access"""
        config = IGDBConfig()
        
        # Test that properties return the correct values
        assert config.client_id == "test_client_id"
        assert config.client_secret == "test_client_secret"
        assert config.auth_token == "test_auth_token"
        
        # Test that private attributes exist
        assert hasattr(config, '_client_id')
        assert hasattr(config, '_client_secret')
        assert hasattr(config, '_auth_token')

class TestWebUIConfig:
    """Test WebUIConfig dataclass"""
    
    def test_web_ui_config_init(self):
        """Test WebUIConfig initialization"""
        config = WebUIConfig()
        # WebUIConfig is currently empty (pass statement)
        assert isinstance(config, WebUIConfig)

class TestDatabaseConfig:
    """Test DatabaseConfig dataclass"""
    
    def test_database_config_init_directory_exists(self, mock_database_file_path, dummy_database_file):
        """Test DatabaseConfig initialization when directory exists"""
        
        with mock_database_file_path(dummy_database_file):
            config = DatabaseConfig()
            expected_path = dummy_database_file
            assert config.db_file == expected_path
            assert os.path.exists(os.path.dirname(expected_path))

    def test_database_config_init_directory_not_exists(self, temp_config_dir, mock_database_file_path):
        """Test DatabaseConfig initialization when directory doesn't exist"""
        
        non_exist_database_file = os.path.join(temp_config_dir, "new_dir", "data.db")

        # Verify directory doesn't exist initially
        assert not os.path.exists(os.path.dirname(non_exist_database_file))

        with mock_database_file_path(non_exist_database_file):
            config = DatabaseConfig()
            expected_path = non_exist_database_file
            assert config.db_file == expected_path
        
            # makedirs should be called to create directory
            expected_dir = os.path.dirname(expected_path)
            assert os.path.exists(expected_dir)
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_database_config_property(self, mock_exists, mock_makedirs, mock_database_file_path, dummy_database_file):
        """Test DatabaseConfig db_file property"""
            
        with mock_database_file_path(dummy_database_file):    
            config = DatabaseConfig()
            
            # Test that property returns the correct value
            expected_path = dummy_database_file
            assert config.db_file == expected_path
            
            # Test that private attribute exists
            assert hasattr(config, '_db_file')

class TestServerConfig:
    """Test ServerConfig dataclass"""
    
    def test_server_config_init(self):
        """Test ServerConfig initialization"""
        config = ServerConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8000
    
    def test_server_config_properties(self):
        """Test ServerConfig property access"""
        config = ServerConfig()
        
        # Test that properties return the correct values
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        
        # Test that private attributes exist
        assert hasattr(config, '_host')
        assert hasattr(config, '_port')


class TestConfigData:
    """Test ConfigData dataclass"""
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_config_data_init_without_dict(self, mock_exists, mock_makedirs, mock_env_vars):
        """Test ConfigData initialization without config dict"""
        config = ConfigData()
        assert isinstance(config.igdb, IGDBConfig)
        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.database, DatabaseConfig)
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_config_data_init_with_dict(self, mock_exists, mock_makedirs, sample_config_data, mock_env_vars):
        """Test ConfigData initialization with config dict"""
        config = ConfigData(sample_config_data)
        assert isinstance(config.igdb, IGDBConfig)
        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.database, DatabaseConfig)
        assert config.igdb.token_timestamp == "2023-01-01T00:00:00Z"
        assert config.igdb.data_refresh_limit == 5
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_config_data_init_with_empty_dict(self, mock_exists, mock_makedirs, mock_env_vars):
        """Test ConfigData initialization with empty dict"""
        config = ConfigData({})
        assert isinstance(config.igdb, IGDBConfig)
        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.database, DatabaseConfig)
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_config_data_to_dict(self, mock_exists, mock_makedirs, mock_env_vars):
        """Test ConfigData to_dict method"""
        config = ConfigData()
        result = config.to_dict()
        
        expected_keys = ["igdb", "server", "web_ui", "database"]
        assert all(key in result for key in expected_keys)
        
        # Check IGDB section
        igdb_section = result["igdb"]
        assert igdb_section["token_timestamp"] == ""
        assert igdb_section["data_refresh_limit"] == 1
        
        # Check server section
        assert result["server"] == {}
        
        # Check web_ui section (empty)
        assert result["web_ui"] == {}
        
        # Check database section
        assert result["database"] == {}

class TestConfigManager:
    """Test ConfigManager singleton class"""
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_config_manager_singleton(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test ConfigManager singleton pattern"""
        
        with mock_config_file_path(config_file_with_data):
            manager1 = ConfigManager()
            manager2 = ConfigManager()
            assert manager1 is manager2
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_config_manager_load_config_success(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test successful config loading"""
        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            config = manager.get_config()
            assert isinstance(config, ConfigData)
            assert config.igdb.token_timestamp == "2023-01-01T00:00:00Z"
            assert config.igdb.data_refresh_limit == 5
            assert config.igdb.client_id == "test_client_id"
            assert config.igdb.auth_token == "test_auth_token"
            assert config.igdb.client_secret == "test_client_secret"
            assert config.database.db_file == DATABASE_FILE
            assert config.server.host == HOST
            assert config.server.port == PORT
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_config_manager_load_config_file_not_found(self, mock_exists, mock_makedirs, mock_config_file_path):
        """Test config loading when file doesn't exist"""
        with mock_config_file_path("/nonexistent/config.json"):
            with pytest.raises(FileNotFoundError, match="Configuration file '/nonexistent/config.json' not found"):
                ConfigManager()
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_get_config_full(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test getting full configuration"""
        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            config = manager.get_config()
            assert isinstance(config, ConfigData)
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_get_config_igdb_section(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test getting IGDB configuration section"""
        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            igdb_config = manager.get_config("igdb")
            assert isinstance(igdb_config, IGDBConfig)
            assert igdb_config.token_timestamp == "2023-01-01T00:00:00Z"
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_get_config_server_section(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test getting server configuration section"""
        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            server_config = manager.get_config("server")
            assert isinstance(server_config, ServerConfig)
            assert server_config.host == HOST
            assert server_config.port == PORT

    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_get_config_database_section(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test getting database configuration section"""
        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            db_config = manager.get_config("database")
            assert isinstance(db_config, DatabaseConfig)
            assert db_config.db_file == DATABASE_FILE
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_get_config_unknown_section(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test getting unknown configuration section"""
        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            with pytest.raises(ValueError, match="Unknown configuration section: unknown"):
                manager.get_config("unknown")
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_get_config_no_config_loaded(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test getting config when none is loaded"""

        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            manager._config = None

            with pytest.raises(RuntimeError, match="Configuration not loaded"):
                manager.get_config()
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_save_config_success(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test successful config saving"""
        
        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            manager.update_config('igdb', data_refresh_limit=20)
            manager.save_config()

            # Verify file was saved
            assert os.path.exists(config_file_with_data)
            with open(config_file_with_data, 'r') as f:
                saved_data = json.load(f)
                assert "igdb" in saved_data
                assert "server" in saved_data
                assert "web_ui" in saved_data
                assert "database" in saved_data
                assert saved_data['igdb']['data_refresh_limit'] == 20
    
    def test_save_config_creates_directory(self, mock_config_file_path, config_file_with_data, sample_config_data, mock_env_vars):
        """Test config saving creates directory if it doesn't exist"""

        new_config_file = os.path.join(os.path.dirname(config_file_with_data), "new_dir", "config.json")

        with patch('os.path.exists', return_value=True), patch('os.makedirs'):
            # This will mock all the os.path.exits() in both source and test files to return value True
            with mock_config_file_path(config_file_with_data):
                manager = ConfigManager()
        
        # Check the new config dir is not exist at initial
        assert not os.path.exists(os.path.dirname(new_config_file))

        # Now test saving to new location
        with mock_config_file_path(new_config_file):
            manager.save_config()
            assert os.path.exists(new_config_file)
            assert os.path.isfile(new_config_file)
            with open(new_config_file, 'r') as f:
                saved_data = json.load(f)
                assert saved_data == sample_config_data
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_save_config_no_config_loaded(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test saving config when none is loaded"""
        # Create initial config file

        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            manager._config = None

            with pytest.raises(RuntimeError, match="No configuration loaded to save"):
                manager.save_config()
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_save_config_io_error(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test save config with IO error"""
        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            with patch('builtins.open', side_effect=OSError("Permission denied")), pytest.raises(RuntimeError, match="Failed to save configuration file"):
                manager.save_config()
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_update_config_igdb_section(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test updating IGDB configuration section"""
        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            manager.update_config("igdb", token_timestamp="2024-01-01T00:00:00Z", data_refresh_limit=10)
            
            igdb_config = manager.get_config("igdb")
            assert igdb_config.token_timestamp == "2024-01-01T00:00:00Z" # type: ignore
            assert igdb_config.data_refresh_limit == 10 # type: ignore
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_update_config_server_section(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test updating server configuration section"""
        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            with pytest.raises(ValueError, match="Field 'host' is not updatable in section 'server'"):
                manager.update_config("server", host="127.0.0.1", port=9000)
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_update_config_database_section(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test updating database configuration section"""
        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            with pytest.raises(ValueError, match="Field 'db_file' is not updatable in section 'database'"):
                manager.update_config("database", db_file="/new/path/db.sqlite")
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_update_config_unknown_section(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test updating unknown configuration section"""
        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            with pytest.raises(ValueError, match="Unknown configuration section: unknown"):
                manager.update_config("unknown", field="value")
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_update_config_unknown_igdb_field(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test updating unknown section field"""
        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            with pytest.raises(ValueError, match="Field 'unknown_field' is not updatable in section 'igdb'"):
                manager.update_config("igdb", unknown_field="value")
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_update_config_no_config_loaded(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test updating config when none is loaded"""
        # Create initial config file

        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()
            manager._config = None

            with pytest.raises(RuntimeError, match="Configuration not loaded"):
                manager.update_config("igdb", token_timestamp="test")
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_reload_config(self, mock_exists, mock_makedirs, mock_config_file_path, temp_config_file, sample_config_data, mock_env_vars):
        """Test reloading configuration"""
        # Create initial config
        os.makedirs(os.path.dirname(temp_config_file), exist_ok=True)
        with open(temp_config_file, 'w') as f:
            json.dump(sample_config_data, f)
        
        with mock_config_file_path(temp_config_file):
            manager = ConfigManager()
            original_timestamp = manager.get_config("igdb").token_timestamp # type: ignore
            
            # Modify the file
            modified_data = sample_config_data.copy()
            modified_data["igdb"]["token_timestamp"] = "2024-12-31T23:59:59Z"
            with open(temp_config_file, 'w') as f:
                json.dump(modified_data, f)
            
            # Reload and verify change
            manager.reload_config()
            new_timestamp = manager.get_config("igdb").token_timestamp # type: ignore
            assert new_timestamp != original_timestamp
            assert new_timestamp == "2024-12-31T23:59:59Z"
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_reload_config_file_not_found(self, mock_exists, mock_makedirs, mock_config_file_path, config_file_with_data, mock_env_vars):
        """Test reloading config when file is deleted"""
        with mock_config_file_path(config_file_with_data):
            manager = ConfigManager()

            # Delete the file
            os.remove(config_file_with_data)
            
            # Reload should raise FileNotFoundError
            with pytest.raises(FileNotFoundError):
                manager.reload_config()

class TestIntegration:
    """Integration tests for the entire config system"""
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_full_workflow(self, mock_exists, mock_makedirs, mock_config_file_path, temp_config_file, sample_config_data, mock_env_vars):
        """Test complete workflow: load, get, update, save, reload"""
        # Create initial config
        os.makedirs(os.path.dirname(temp_config_file), exist_ok=True)
        with open(temp_config_file, 'w') as f:
            json.dump(sample_config_data, f)
        
        with mock_config_file_path(temp_config_file):
            # Load config
            manager = ConfigManager()
            
            # Get sections
            igdb_config = manager.get_config("igdb")
            assert igdb_config.client_id == "test_client_id"  # type: ignore # From env vars
            assert igdb_config.token_timestamp == "2023-01-01T00:00:00Z"  # type: ignore # From file
            
            server_config = manager.get_config("server")
            assert server_config.host == "0.0.0.0" # type: ignore
            assert server_config.port == 8000 # type: ignore
            
            # Update config (only IGDB fields are mutable)
            manager.update_config("igdb", data_refresh_limit=20)
            
            # Verify updates
            assert manager.get_config("igdb").data_refresh_limit == 20 # type: ignore
            
            # Reload and verify persistence
            manager.reload_config()
            assert manager.get_config("igdb").data_refresh_limit == 20 # type: ignore

class TestConfigurationValidation:
    """Test configuration validation and error handling"""
    
    def test_igdb_config_missing_env_vars_sequence(self):
        """Test that all IGDB environment variables are properly validated"""
        # Test missing CLIENT_ID first
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="IGDB_CLIENT_ID environment variable is required"):
                IGDBConfig()
        
        # Test missing CLIENT_SECRET with CLIENT_ID present
        with patch.dict(os.environ, {'IGDB_CLIENT_ID': 'test'}, clear=True):
            with pytest.raises(ValueError, match="IGDB_CLIENT_SECRET environment variable is required"):
                IGDBConfig()
        
        # Test missing AUTH_TOKEN with CLIENT_ID and CLIENT_SECRET present
        with patch.dict(os.environ, {
            'IGDB_CLIENT_ID': 'test',
            'IGDB_CLIENT_SECRET': 'test'
        }, clear=True):
            with pytest.raises(ValueError, match="IGDB_AUTH_TOKEN environment variable is required"):
                IGDBConfig()
    
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_config_data_initialization_with_missing_env_vars(self, mock_exists, mock_makedirs):
        """Test ConfigData initialization fails when IGDB env vars are missing"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="IGDB_CLIENT_ID environment variable is required"):
                ConfigData()
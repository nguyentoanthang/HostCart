from dataclasses import dataclass
import json
import os
from typing import Dict, Any, Optional, List, Union

# Config file
CONFIG_FILE = os.path.normpath("../../config/config.json")
# Database file
DATABASE_FILE = os.path.normpath("../../database/data.db")
# Host
HOST = "0.0.0.0"
# Port
PORT = 8000

@dataclass
class IGDBConfig:
    _client_id: Optional[str]
    _client_secret: Optional[str]
    _auth_token: Optional[str]
    token_timestamp: str
    data_refresh_limit: int

    def __init__(self, token_timestamp: str = "", data_refresh_limit: int = 1, **kwargs):
        # Only unpack the non-sensitive fields from config
        self.token_timestamp = token_timestamp
        self.data_refresh_limit = data_refresh_limit
        
        # Override with environment variables if they exist
        self._client_id = os.getenv('IGDB_CLIENT_ID')
        if self._client_id is None:
            raise ValueError("IGDB_CLIENT_ID environment variable is required")
            
        self._client_secret = os.getenv('IGDB_CLIENT_SECRET')
        if self._client_secret is None:
            raise ValueError("IGDB_CLIENT_SECRET environment variable is required")
            
        self._auth_token = os.getenv('IGDB_AUTH_TOKEN')
        if self._auth_token is None:
            raise ValueError("IGDB_AUTH_TOKEN environment variable is required")

    @property
    def client_id(self) -> str:
        return self._client_id # type: ignore - will raise error in __post_init__ if this attribute is None
    
    @property
    def client_secret(self) -> str:
        return self._client_secret # type: ignore - will raise error in __post_init__ if this attribute is None
    
    @property
    def auth_token(self) -> str:
        return self._auth_token # type: ignore - will raise error in __post_init__ if this attribute is None

@dataclass
class WebUIConfig:
    # title: str = "HostCart Game Collection"
    # api_base_url: str = "/api/v1"  # Relative URL since same server
    # theme: str = "dark"
    # items_per_page: int = 20
    pass

@dataclass
class DatabaseConfig:
    _db_file: str

    def __init__(self):
        self._db_file = DATABASE_FILE
        database_dir = os.path.dirname(self._db_file)
        if not os.path.exists(database_dir):
            os.makedirs(database_dir)

    @property
    def db_file(self) -> str:
        return self._db_file

@dataclass
class ServerConfig:
    _host: str
    _port: int

    def __init__(self):
        self._host = HOST
        self._port = PORT

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    # debug: bool = False
    # cors_origins: Optional[List[str]] = None
    # cors_allow_credentials: bool = True
    # cors_allow_methods: Optional[List[str]] = None
    # cors_allow_headers: Optional[List[str]] = None
    # api_prefix: str = "/api/v1"
    # docs_url: str = "/docs"
    # redoc_url: str = "/redoc"
    # max_request_size: int = 16777216
    # serve_static_files: bool = True
    # static_directory: str = "/app/web_ui/dist"
    pass

@dataclass
class ConfigData:
    igdb: IGDBConfig
    server: ServerConfig
    # web_ui: WebUIConfig
    database: DatabaseConfig
    
    def __init__(self, config_dict: Optional[dict] = None):
        if config_dict:
            igdb_data = config_dict.get("igdb", {})
            # server_data = config_dict.get("server", {})
            # web_ui_data = config_dict.get("web_ui", {})
            # database = config_dict.get("database", {})

            self.igdb = IGDBConfig(**igdb_data)
            self.server = ServerConfig()
            # self.web_ui = WebUIConfig(**web_ui_data)
            self.database = DatabaseConfig()
        else:
            self.igdb = IGDBConfig()
            self.server = ServerConfig()
            # self.web_ui = WebUIConfig()
            self.database = DatabaseConfig()
    
    def to_dict(self) -> dict:
        return {
            "igdb": {
                # token information cannot be configured via config.json, they are configured via environment variables
                # "client_id": self.igdb.client_id,
                # "client_secret": self.igdb.client_secret,
                # "auth_token": self.igdb.auth_token,
                "token_timestamp": self.igdb.token_timestamp,
                "data_refresh_limit": self.igdb.data_refresh_limit
            },
            "server": {
                # "host": self.server.host,
                # "port": self.server.port,
                # "debug": self.server.debug,
                # "cors_origins": self.server.cors_origins,
                # "cors_allow_credentials": self.server.cors_allow_credentials,
                # "cors_allow_methods": self.server.cors_allow_methods,
                # "cors_allow_headers": self.server.cors_allow_headers,
                # "api_prefix": self.server.api_prefix,
                # "docs_url": self.server.docs_url,
                # "redoc_url": self.server.redoc_url,
                # "max_request_size": self.server.max_request_size,
                # "serve_static_files": self.server.serve_static_files,
                # "static_directory": self.server.static_directory
            },
            "web_ui": {
                # Add web_ui fields here when you define them
            },
            "database": {
                # "db_file": self.database.db_file
            }
        }

class ConfigManager:
    _instance: Optional['ConfigManager'] = None
    _config: Optional[ConfigData] = None
    # Define which fields can be updated for each section
    _UPDATABLE_FIELDS = {
        "igdb": {"token_timestamp", "data_refresh_limit"},
        "server": {},
        "database": {}
    }
    _VALID_SECTIONS = {"igdb", "server", "database"}  # Add "web_ui" when implemented
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from JSON file and environment variables"""
        try:
            with open(CONFIG_FILE, 'r') as f:
                config_dict = json.load(f)
                self._config = ConfigData(config_dict)
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file '{CONFIG_FILE}' not found")

    def get_config(self, section: Optional[str] = None):
        """Get configuration section or entire config"""
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call _load_config() first.")

        if section:            
            if section not in self._VALID_SECTIONS:
                raise ValueError(f"Unknown configuration section: {section}.")
            
            return getattr(self._config, section)
        
        return self._config
    
    def save_config(self) -> None:
        """Save current configuration to JSON file"""
        if self._config is None:
            raise RuntimeError("No configuration loaded to save")
        
        try:
            # Ensure the config directory exists
            config_dir = os.path.dirname(CONFIG_FILE)
            os.makedirs(config_dir, exist_ok=True)

            # Convert config to dictionary and save
            config_dict = self._config.to_dict()
            
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_dict, f, indent=2)
                
        except (OSError, IOError) as e:
            raise RuntimeError(f"Failed to save configuration file '{CONFIG_FILE}': {e}")

    def update_config(self, section: str, **kwargs) -> None:
        """Update specific configuration section and save to file"""
        if self._config is None:
            raise RuntimeError("Configuration not loaded")
        
        # Check if section exists
        if section not in self._UPDATABLE_FIELDS:
            raise ValueError(f"Unknown configuration section: {section}")
        
        config_obj = getattr(self._config, section)
        allowed_fields = self._UPDATABLE_FIELDS[section]
        
        for key, value in kwargs.items():
            if key not in allowed_fields:
                raise ValueError(f"Field '{key}' is not updatable in section '{section}'. "
                               f"Allowed fields: {', '.join(allowed_fields)}")
            
            # Only set attributes that are explicitly allowed
            setattr(config_obj, key, value)
        
        # Save the updated configuration
        self.save_config()

    def reload_config(self) -> None:
        """Reload configuration from file"""
        self._load_config()

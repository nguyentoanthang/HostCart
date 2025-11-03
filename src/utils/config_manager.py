from dataclasses import dataclass
import json
import os
from typing import Dict, Any, Optional, List, Union

# Config files
CONFIG_FILE = os.path.normpath("../../config/config.json")

@dataclass
class IGDBConfig:
    client_id: str = ""
    client_secret: str = ""
    auth_token: str = ""
    token_timestamp: str = ""
    data_refresh_limit: int = 1

    def __init__(self, token_timestamp: str = "", data_refresh_limit: int = 1, **kwargs):
        # Only unpack the non-sensitive fields from config
        self.token_timestamp = token_timestamp
        self.data_refresh_limit = data_refresh_limit

    def __post_init__(self):
        # Override with environment variables if they exist
        self.client_id = os.getenv('IGDB_CLIENT_ID', self.client_id)
        self.client_secret = os.getenv('IGDB_CLIENT_SECRET', self.client_secret)
        self.auth_token = os.getenv('IGDB_AUTH_TOKEN', self.auth_token)

@dataclass
class WebUIConfig:
    # title: str = "HostCart Game Collection"
    # api_base_url: str = "/api/v1"  # Relative URL since same server
    # theme: str = "dark"
    # items_per_page: int = 20
    pass

@dataclass
class DatabaseConfig:
    db_file: str = ""

    def __init__(self):
        self.db_file = os.path.normpath("../../database/hostcart.db")

@dataclass
class ServerConfig:
    host: str = ""
    port: int = 0

    def __init__(self):
        self.host = "0.0.0.0"
        self.port = 8000

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
    db_config: DatabaseConfig
    
    def __init__(self, config_dict: Optional[dict] = None):
        if config_dict:
            igdb_data = config_dict.get("igdb", {})
            # server_data = config_dict.get("server", {})
            # web_ui_data = config_dict.get("web_ui", {})
            # database = config_dict.get("database", {})

            self.igdb = IGDBConfig(**igdb_data)
            self.server = ServerConfig()
            # self.web_ui = WebUIConfig(**web_ui_data)
            self.db_config = DatabaseConfig()
        else:
            self.igdb = IGDBConfig()
            self.server = ServerConfig()
            # self.web_ui = WebUIConfig()
            self.db_config = DatabaseConfig()
    
    def to_dict(self) -> dict:
        return {
            "igdb": {
                "client_id": self.igdb.client_id,
                "client_secret": self.igdb.client_secret,
                "auth_token": self.igdb.auth_token,
                "token_timestamp": self.igdb.token_timestamp,
                "data_refresh_limit": self.igdb.data_refresh_limit
            },
            "server": {
                "host": self.server.host,
                "port": self.server.port
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
                "db_file": self.db_config.db_file
            }
        }

class ConfigManager:
    _instance: Optional['ConfigManager'] = None
    _config: Optional[ConfigData] = None
    
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
            if section == "igdb":
                return self._config.igdb
            elif section == "server":
                return self._config.server
            # elif section == "web_ui":
            #     return self._config.web_ui
            elif section == "database":
                return self._config.db_config
            else:
                raise ValueError(f"Unknown configuration section: {section}")
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
        
        if section == "igdb":
            for key, value in kwargs.items():
                if hasattr(self._config.igdb, key):
                    setattr(self._config.igdb, key, value)
                else:
                    raise ValueError(f"Unknown IGDB config field: {key}")
        elif section == "server":
            for key, value in kwargs.items():
                if hasattr(self._config.server, key):
                    setattr(self._config.server, key, value)
                else:
                    raise ValueError(f"Unknown server config field: {key}")
        elif section == "database":
            for key, value in kwargs.items():
                if hasattr(self._config.db_config, key):
                    setattr(self._config.db_config, key, value)
                else:
                    raise ValueError(f"Unknown database config field: {key}")
        else:
            raise ValueError(f"Unknown configuration section: {section}")
        
        # Save the updated configuration
        self.save_config()

    def reload_config(self) -> None:
        """Reload configuration from file"""
        self._load_config()

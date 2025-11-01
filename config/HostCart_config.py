from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

# Config files
config_file = os.path.join(os.path.dirname(__file__), "config.json")

# Display types
display_types = ['cards', 'table']

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
        
        # Initialize sensitive fields to empty (will be set in __post_init__)
        self.client_id = ""
        self.client_secret = ""
        self.auth_token = ""

    def __post_init__(self):
        # Override with environment variables if they exist
        self.client_id = os.getenv('IGDB_CLIENT_ID', self.client_id)
        self.client_secret = os.getenv('IGDB_CLIENT_SECRET', self.client_secret)
        self.auth_token = os.getenv('IGDB_AUTH_TOKEN', self.auth_token)

@dataclass
class SecurityConfig:
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    def __post_init__(self):
        self.secret_key = os.getenv('SECRET_KEY', self.secret_key)
        # Generate a random secret key if none provided
        if not self.secret_key:
            import secrets
            self.secret_key = secrets.token_urlsafe(32)

@dataclass
class WebUIConfig:
    title: str = "HostCart Game Collection"
    api_base_url: str = "/api/v1"  # Relative URL since same server
    theme: str = "dark"
    items_per_page: int = 20

@dataclass
class DatabaseConfig:
    db_file: str = ""

@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: Optional[List[str]] = None
    cors_allow_credentials: bool = True
    cors_allow_methods: Optional[List[str]] = None
    cors_allow_headers: Optional[List[str]] = None
    api_prefix: str = "/api/v1"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    max_request_size: int = 16777216
    serve_static_files: bool = True
    static_directory: str = "/app/web_ui/dist"

@dataclass
class ConfigData:
    igdb: IGDBConfig
    server: ServerConfig
    web_ui: WebUIConfig
    db_config: DatabaseConfig
    platforms: List[str]
    
    def __init__(self, config_dict: Optional[dict] = None):
        if config_dict:
            igdb_data = config_dict.get("igdb", {})
            server_data = config_dict.get("server", {})
            web_ui_data = config_dict.get("web_ui", {})
            database = config_dict.get("database", {})
            platforms = config_dict.get("platforms", [])

            self.igdb = IGDBConfig(**igdb_data)
            self.server = ServerConfig(**server_data)
            self.web_ui = WebUIConfig(**web_ui_data)
            self.db_config = DatabaseConfig(**database)
            self.platforms = platforms
        else:
            self.igdb = IGDBConfig()
            self.server = ServerConfig()
            self.web_ui = WebUIConfig()
            self.db_config = DatabaseConfig()
            self.platforms = []
    
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
                "port": self.server.port,
                "debug": self.server.debug,
                "cors_origins": self.server.cors_origins,
                "cors_allow_credentials": self.server.cors_allow_credentials,
                "cors_allow_methods": self.server.cors_allow_methods,
                "cors_allow_headers": self.server.cors_allow_headers,
                "api_prefix": self.server.api_prefix,
                "docs_url": self.server.docs_url,
                "redoc_url": self.server.redoc_url,
                "max_request_size": self.server.max_request_size,
                "serve_static_files": self.server.serve_static_files,
                "static_directory": self.server.static_directory
            },
            "web_ui": {
                # Add web_ui fields here when you define them
            },
            "database": {
                "db_file": self.db_config.db_file
            },
            "platforms": self.platforms
        }

class ConfigLoader:
    _instance: Optional['ConfigLoader'] = None
    _config: Optional[ConfigData] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from JSON file and environment variables"""
        try:
            with open(config_file, 'r') as f:
                config_dict = json.load(f)
                self._config = ConfigData(config_dict)
                
            # Override sensitive data with environment variables
            self._load_env_overrides()
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file '{config_file}' not found")
    
    def _load_env_overrides(self):
        """Load sensitive configuration from environment variables"""
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call _load_config() first.")
        
        # Database
        if db_file := os.getenv('DATABASE_FILE'):
            self._config.db_config.db_file = db_file
            
        # Server
        if host := os.getenv('SERVER_HOST'):
            self._config.server.host = host
        if port := os.getenv('SERVER_PORT'):
            self._config.server.port = int(port)

    def get_config(self, section: Optional[str] = None):
        """Get configuration section or entire config"""
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call _load_config() first.")

        if section:
            if section == "igdb":
                return self._config.igdb
            elif section == "server":
                return self._config.server
            elif section == "web_ui":
                return self._config.web_ui
            elif section == "database":
                return self._config.db_config
            elif section == "platforms":
                return self._config.platforms
            else:
                raise ValueError(f"Unknown configuration section: {section}")
        return self._config
    
    def set_igdb_credentials(self, client_id: str, client_secret: str):
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call _load_config() first.")
        
        self._config.igdb.client_id = client_id
        self._config.igdb.client_secret = client_secret

    def add_platforms(self, platforms: List[str]) -> List[str]:
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call _load_config() first.")

        added_platforms = []
        for platform in platforms:
            if platform not in self._config.platforms:
                self._config.platforms.append(platform)
                added_platforms.append(platform)
        
        return added_platforms
    
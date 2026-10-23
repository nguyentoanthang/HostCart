"""
Core Configuration Management for HostCart.
Provides path-safe settings loading from JSON and environment variables.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel, Field

# Discover project root safely: HostCart/src/core/config.py -> HostCart
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])
    api_prefix: str = "/api/v1"


class DatabaseConfig(BaseModel):
    db_file: str = "data/hostcart.db"

    def get_resolved_path(self, root: Optional[Path] = None) -> Path:
        """Resolve database path relative to project root if not absolute."""
        if self.db_file == ":memory:":
            return Path(":memory:")

        for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
            if self.db_file.startswith(prefix):
                return Path(self.db_file)

        path_str = self.db_file
        if path_str.startswith("sqlite:///"):
            path_str = path_str.replace("sqlite:///", "")

        p = Path(path_str)
        if p.is_absolute():
            return p

        base_root = root or PROJECT_ROOT
        return (base_root / p).resolve()


class SecurityConfig(BaseModel):
    secret_key: str = "insecure-change-in-production-secret-key-hostcart"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    bcrypt_rounds: int = 12


class IGDBConfig(BaseModel):
    client_id: str = ""
    client_secret: str = ""


class TMDBConfig(BaseModel):
    api_key: str = ""


class BooksConfig(BaseModel):
    google_books_api_key: str = ""
    openlibrary_enabled: bool = True


class ProvidersConfig(BaseModel):
    igdb: IGDBConfig = Field(default_factory=IGDBConfig)
    tmdb: TMDBConfig = Field(default_factory=TMDBConfig)
    books: BooksConfig = Field(default_factory=BooksConfig)


class FeaturesConfig(BaseModel):
    wishlist: Dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "max_items": 1000}
    )
    playtime_tracking: Dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True}
    )
    ratings: Dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "scale": 10}
    )
    reviews: Dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "max_length": 2000}
    )
    tags: Dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "max_tags": 20}
    )


class WebUIConfig(BaseModel):
    title: str = "HostCart Multi-Media Collection"
    theme: str = "arcadia"


class HomelabConfig(BaseModel):
    deployment_mode: str = "standalone"
    auth_mode: str = "standalone"
    homelab_sso_secret: str = ""
    homelab_internal_token: str = ""
    ai_base_url: str = "https://openrouter.ai/api/v1"
    ai_api_key: str = ""
    ai_model: str = "openai/gpt-4o-mini"


class Settings(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    web_ui: WebUIConfig = Field(default_factory=WebUIConfig)
    homelab: HomelabConfig = Field(default_factory=HomelabConfig)


def _deep_merge_dicts(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge updates dict into base dict."""
    result = dict(base)
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


class ConfigStore:
    """Manages loading, validating, updating, and persisting configuration."""

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        env_file: Optional[Union[str, Path]] = None,
        load_now: bool = True,
    ):
        self.config_path: Path = Path(config_path or DEFAULT_CONFIG_PATH).resolve()
        self.env_file: Optional[Path] = (
            Path(env_file).resolve() if env_file is not None else DEFAULT_ENV_PATH
        )
        self._settings: Optional[Settings] = None

        if load_now:
            self.load()

    def load(self) -> Settings:
        """Load settings from config.json and overlay environment variables."""
        config_data: Dict[str, Any] = {}

        # 1. Read JSON file if it exists
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to parse config file at {self.config_path}: {e}"
                )

        # 2. Read .env file if it exists
        env_dict: Dict[str, Optional[str]] = {}
        if self.env_file and self.env_file.exists():
            env_dict = dotenv_values(self.env_file)

        # 3. Apply environment variable overrides (system environment takes highest priority)
        merged_env: Dict[str, str] = {}
        for k, v in env_dict.items():
            if v is not None:
                merged_env[k] = v
        for k, v in os.environ.items():
            merged_env[k] = v

        env_overrides: Dict[str, Any] = {}

        if "SECRET_KEY" in merged_env and merged_env["SECRET_KEY"]:
            env_overrides.setdefault("security", {})["secret_key"] = merged_env[
                "SECRET_KEY"
            ]

        if "ACCESS_TOKEN_EXPIRE_MINUTES" in merged_env and merged_env["ACCESS_TOKEN_EXPIRE_MINUTES"]:
            try:
                env_overrides.setdefault("security", {})["access_token_expire_minutes"] = int(
                    merged_env["ACCESS_TOKEN_EXPIRE_MINUTES"]
                )
            except ValueError:
                pass

        if "SERVER_HOST" in merged_env and merged_env["SERVER_HOST"]:
            env_overrides.setdefault("server", {})["host"] = merged_env["SERVER_HOST"]
        elif "HOST" in merged_env and merged_env["HOST"]:
            env_overrides.setdefault("server", {})["host"] = merged_env["HOST"]

        if "SERVER_PORT" in merged_env and merged_env["SERVER_PORT"]:
            try:
                env_overrides.setdefault("server", {})["port"] = int(merged_env["SERVER_PORT"])
            except ValueError:
                pass
        elif "PORT" in merged_env and merged_env["PORT"]:
            try:
                env_overrides.setdefault("server", {})["port"] = int(merged_env["PORT"])
            except ValueError:
                pass

        if "DATABASE_URL" in merged_env and merged_env["DATABASE_URL"]:
            env_overrides.setdefault("database", {})["db_file"] = merged_env["DATABASE_URL"]
        elif "DB_FILE" in merged_env and merged_env["DB_FILE"]:
            env_overrides.setdefault("database", {})["db_file"] = merged_env["DB_FILE"]

        # External providers overrides
        if "IGDB_CLIENT_ID" in merged_env:
            env_overrides.setdefault("providers", {}).setdefault("igdb", {})[
                "client_id"
            ] = merged_env["IGDB_CLIENT_ID"]

        if "IGDB_CLIENT_SECRET" in merged_env:
            env_overrides.setdefault("providers", {}).setdefault("igdb", {})[
                "client_secret"
            ] = merged_env["IGDB_CLIENT_SECRET"]

        if "TMDB_API_KEY" in merged_env:
            env_overrides.setdefault("providers", {}).setdefault("tmdb", {})[
                "api_key"
            ] = merged_env["TMDB_API_KEY"]

        if "GOOGLE_BOOKS_API_KEY" in merged_env:
            env_overrides.setdefault("providers", {}).setdefault("books", {})[
                "google_books_api_key"
            ] = merged_env["GOOGLE_BOOKS_API_KEY"]

        # Homelab and AI settings overrides
        if "DEPLOYMENT_MODE" in merged_env and merged_env["DEPLOYMENT_MODE"]:
            env_overrides.setdefault("homelab", {})["deployment_mode"] = merged_env[
                "DEPLOYMENT_MODE"
            ]

        if "AUTH_MODE" in merged_env and merged_env["AUTH_MODE"]:
            env_overrides.setdefault("homelab", {})["auth_mode"] = merged_env[
                "AUTH_MODE"
            ]

        if "HOMELAB_SSO_SECRET" in merged_env and merged_env["HOMELAB_SSO_SECRET"]:
            env_overrides.setdefault("homelab", {})["homelab_sso_secret"] = merged_env[
                "HOMELAB_SSO_SECRET"
            ]

        if "HOMELAB_INTERNAL_TOKEN" in merged_env and merged_env["HOMELAB_INTERNAL_TOKEN"]:
            env_overrides.setdefault("homelab", {})["homelab_internal_token"] = merged_env[
                "HOMELAB_INTERNAL_TOKEN"
            ]

        if "AI_BASE_URL" in merged_env and merged_env["AI_BASE_URL"]:
            env_overrides.setdefault("homelab", {})["ai_base_url"] = merged_env[
                "AI_BASE_URL"
            ]

        if "AI_API_KEY" in merged_env and merged_env["AI_API_KEY"]:
            env_overrides.setdefault("homelab", {})["ai_api_key"] = merged_env[
                "AI_API_KEY"
            ]
        elif "OPENROUTER_API_KEY" in merged_env and merged_env["OPENROUTER_API_KEY"]:
            env_overrides.setdefault("homelab", {})["ai_api_key"] = merged_env[
                "OPENROUTER_API_KEY"
            ]

        if "AI_MODEL" in merged_env and merged_env["AI_MODEL"]:
            env_overrides.setdefault("homelab", {})["ai_model"] = merged_env[
                "AI_MODEL"
            ]

        final_data = _deep_merge_dicts(config_data, env_overrides)
        self._settings = Settings.model_validate(final_data)
        return self._settings

    def get_settings(self) -> Settings:
        """Return the current loaded Settings instance."""
        if self._settings is None:
            return self.load()
        return self._settings

    def update_config(
        self, updates: Dict[str, Any], save: bool = True
    ) -> Settings:
        """Update settings with a partial dictionary, validate, and optionally persist to disk."""
        current_data = self.get_settings().model_dump()
        new_data = _deep_merge_dicts(current_data, updates)
        new_settings = Settings.model_validate(new_data)
        self._settings = new_settings

        if save:
            self.save_config()

        return self._settings

    def save_config(self, target_path: Optional[Union[str, Path]] = None) -> None:
        """Persist current configuration to disk as clean JSON."""
        dest = Path(target_path or self.config_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dumped = self.get_settings().model_dump()
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(dumped, f, indent=2)


_global_config_store: Optional[ConfigStore] = None


def get_config_store(
    config_path: Optional[Union[str, Path]] = None,
    env_file: Optional[Union[str, Path]] = None,
    force_reload: bool = False,
) -> ConfigStore:
    """Return the global ConfigStore singleton."""
    global _global_config_store
    if _global_config_store is None or force_reload or config_path is not None:
        _global_config_store = ConfigStore(
            config_path=config_path, env_file=env_file, load_now=True
        )
    return _global_config_store


def get_settings() -> Settings:
    """Return the global Settings instance."""
    return get_config_store().get_settings()


def reset_config_store() -> None:
    """Reset the global ConfigStore singleton (useful for isolated tests)."""
    global _global_config_store
    _global_config_store = None

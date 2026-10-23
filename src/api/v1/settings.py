"""
Runtime Settings API endpoints for HostCart.
Provides administrative runtime configuration inspection and updates.
Sensitive secrets (passwords, tokens, API keys) are masked on retrieval.
"""

from __future__ import annotations

import copy
from typing import Any, Dict

from fastapi import APIRouter, Depends

from src.api.v1.auth import get_admin_user
from src.core.config import get_config_store
from src.data.models import User

router = APIRouter(prefix="/settings", tags=["settings"])


def mask_sensitive_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive API keys and secrets before returning configuration."""
    masked = copy.deepcopy(data)

    # Security settings
    if "security" in masked and isinstance(masked["security"], dict):
        if masked["security"].get("secret_key"):
            masked["security"]["secret_key"] = "********"

    # Providers settings
    if "providers" in masked and isinstance(masked["providers"], dict):
        prov = masked["providers"]
        if "igdb" in prov and isinstance(prov["igdb"], dict):
            if prov["igdb"].get("client_secret"):
                prov["igdb"]["client_secret"] = "********"
        if "tmdb" in prov and isinstance(prov["tmdb"], dict):
            if prov["tmdb"].get("api_key"):
                prov["tmdb"]["api_key"] = "********"
        if "books" in prov and isinstance(prov["books"], dict):
            if prov["books"].get("google_books_api_key"):
                prov["books"]["google_books_api_key"] = "********"

    # Homelab settings
    if "homelab" in masked and isinstance(masked["homelab"], dict):
        if masked["homelab"].get("homelab_sso_secret"):
            masked["homelab"]["homelab_sso_secret"] = "********"
        if masked["homelab"].get("homelab_internal_token"):
            masked["homelab"]["homelab_internal_token"] = "********"
        if masked["homelab"].get("ai_api_key"):
            masked["homelab"]["ai_api_key"] = "********"

    return masked


def _filter_masked_and_normalize(updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove masked placeholder values ("********") so secrets are not overwritten.
    Normalize flat configuration keys into structured nested dictionary.
    """
    normalized: Dict[str, Any] = {}

    for k, v in updates.items():
        # Skip masked placeholders
        if v == "********":
            continue

        if isinstance(v, dict):
            sub = _filter_masked_and_normalize(v)
            if sub:
                normalized[k] = sub
            continue

        # Handle flat key mappings
        if k == "igdb_client_id":
            normalized.setdefault("providers", {}).setdefault("igdb", {})["client_id"] = v
        elif k == "igdb_client_secret":
            normalized.setdefault("providers", {}).setdefault("igdb", {})["client_secret"] = v
        elif k == "tmdb_api_key":
            normalized.setdefault("providers", {}).setdefault("tmdb", {})["api_key"] = v
        elif k == "google_books_api_key":
            normalized.setdefault("providers", {}).setdefault("books", {})[
                "google_books_api_key"
            ] = v
        elif k == "openlibrary_enabled":
            normalized.setdefault("providers", {}).setdefault("books", {})[
                "openlibrary_enabled"
            ] = bool(v)
        elif k == "secret_key":
            normalized.setdefault("security", {})["secret_key"] = v
        elif k in ("server_host", "host"):
            normalized.setdefault("server", {})["host"] = v
        elif k in ("server_port", "port"):
            try:
                normalized.setdefault("server", {})["port"] = int(v)
            except (ValueError, TypeError):
                pass
        else:
            normalized[k] = v

    return normalized


@router.get("")
@router.get("/")
def get_runtime_settings(
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """
    Retrieve current runtime settings.
    Restricted to system administrators. Sensitive credentials are masked.
    """
    store = get_config_store()
    settings_dict = store.get_settings().model_dump()
    return mask_sensitive_settings(settings_dict)


@router.put("")
@router.put("/")
def update_runtime_settings(
    updates: Dict[str, Any],
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """
    Update runtime settings and persist to config/config.json.
    Restricted to system administrators.
    Preserves masked credentials if not modified.
    """
    clean_updates = _filter_masked_and_normalize(updates)
    store = get_config_store()
    updated_settings = store.update_config(clean_updates, save=True)
    return mask_sensitive_settings(updated_settings.model_dump())

"""Settings load/save — manages ``settings.json`` and free Zen LLM profiles."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from gui.config import FREE_ZEN_MODELS, SETTINGS_FILE, ZEN_BASE_URL, logger
from gui.state import settings

# --- Constants ---

LEGACY_SETTINGS_KEYS: tuple[str, ...] = ("api_key", "base_url", "model")
"""Keys that were migrated from the top-level settings dict into ``llm_profiles``."""

SETTINGS_TEMPLATE_FILENAME: str = "settings.json.template"
"""Name of the settings template file (in the config directory)."""


# --- Public API ---


def load_settings() -> dict[str, Any]:
    """Load settings from disk, merging with template defaults and auto-migrating legacy keys.

    The load order (later overwrites earlier):
    1. Template defaults from ``settings.json.template``.
    2. User settings from ``settings.json``.
    3. Auto-migration of legacy top-level LLM keys.
    4. Auto-population / pruning of free Zen LLM profiles.

    Returns:
        The loaded settings dictionary (also stored in :data:`gui.state.settings`).
    """
    # 1. Load defaults from template file
    defaults: dict[str, Any] = _load_template_defaults()

    # 2. Build new settings dict
    new: dict[str, Any] = {}
    new.update(defaults)

    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                new_settings: dict[str, Any] = json.load(f)
                new.update(new_settings)
        except Exception as e:
            logger.warning(
                "Failed to load settings from %s: %s",
                SETTINGS_FILE,
                e,
                exc_info=True,
            )

    settings.clear()
    settings.update(new)

    # 3. Auto-migrate legacy LLM config
    _migrate_legacy_llm_settings()

    # 4. Auto-populate / prune free Zen LLM profiles
    _sync_free_zen_profiles()

    # Initialise Sentry if DSN is configured
    _init_sentry()

    return settings


def save_settings(settings_dict: dict[str, Any]) -> bool:
    """Persist settings to disk and update the in-memory dict.

    Includes a safety check to prevent accidentally wiping the ``llm_profiles``
    field when the incoming dict lacks them.

    Args:
        settings_dict: The settings dictionary to persist.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    # Prevent accidentally wiping llm_profiles
    _preserve_llm_profiles(settings_dict)

    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings_dict, f, indent=2)
        if settings is not settings_dict:
            settings.clear()
            settings.update(settings_dict)
        return True
    except Exception as e:
        logger.warning(
            "Failed to save settings to %s: %s", SETTINGS_FILE, e, exc_info=True
        )
        return False


# --- Internal helpers ---


def _load_template_defaults() -> dict[str, Any]:
    """Load default values from the settings template file, if it exists.

    Returns:
        Dictionary of default values (may be empty).
    """
    defaults: dict[str, Any] = {}
    template_file: str = os.path.join(
        os.path.dirname(SETTINGS_FILE), SETTINGS_TEMPLATE_FILENAME
    )
    if os.path.exists(template_file):
        try:
            with open(template_file) as f:
                defaults = json.load(f)
                if defaults.get("api_key") == "YOUR_API_KEY_HERE":
                    defaults["api_key"] = ""
        except Exception as e:
            logger.warning(
                "Failed to load defaults from template %s: %s",
                template_file,
                e,
                exc_info=True,
            )
    return defaults


def _migrate_legacy_llm_settings() -> None:
    """Migrate top-level ``api_key`` / ``base_url`` / ``model`` keys into ``llm_profiles``."""
    if "llm_profiles" not in settings:
        settings["llm_profiles"] = []

    has_legacy_keys: bool = any(k in settings for k in LEGACY_SETTINGS_KEYS)
    if has_legacy_keys and not settings.get("llm_profiles"):
        profile_id: str = str(uuid.uuid4())
        settings["llm_profiles"].append(
            {
                "id": profile_id,
                "name": "Default Profile",
                "api_key": settings.get("api_key", ""),
                "base_url": settings.get("base_url", ""),
                "model": settings.get("model", "gpt-4o-mini"),
            }
        )
        settings["active_llm_profile_id"] = profile_id

    # Clean up legacy keys
    migrated: bool = False
    for k in LEGACY_SETTINGS_KEYS:
        if k in settings:
            del settings[k]
            migrated = True

    if migrated:
        save_settings(settings)
    elif not os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            logger.warning(
                "Failed to write default settings to %s: %s",
                SETTINGS_FILE,
                e,
                exc_info=True,
            )


def _sync_free_zen_profiles() -> None:
    """Add missing free Zen LLM profiles and remove stale ones."""
    profiles: list[dict[str, Any]] = settings.get("llm_profiles", [])
    free_models: set[str] = {m["model"] for m in FREE_ZEN_MODELS}
    changed: bool = False
    active_id: str = settings.get("active_llm_profile_id", "")

    # Remove stale Zen profiles
    cleaned: list[dict[str, Any]] = [
        p
        for p in profiles
        if not (
            p.get("base_url", "").rstrip("/") == ZEN_BASE_URL
            and p.get("model") not in free_models
        )
    ]
    if len(cleaned) != len(profiles):
        changed = True
        settings["llm_profiles"] = profiles = cleaned
        if active_id and active_id not in {p["id"] for p in profiles}:
            settings["active_llm_profile_id"] = profiles[0]["id"] if profiles else ""

    # Extract an API key from an existing profile
    api_key: str = next(
        (p["api_key"] for p in profiles if p.get("api_key")), ""
    )

    # Add missing free Zen models
    existing: set[tuple[str, str]] = {
        (p.get("base_url", "").rstrip("/"), p.get("model")) for p in profiles
    }
    for fm in FREE_ZEN_MODELS:
        if (ZEN_BASE_URL, fm["model"]) not in existing:
            profiles.append(
                {
                    "id": fm["id"],
                    "name": fm["name"],
                    "api_key": api_key,
                    "base_url": ZEN_BASE_URL,
                    "model": fm["model"],
                }
            )
            changed = True
            settings["llm_profiles"] = profiles

    if changed:
        save_settings(settings)


def _init_sentry() -> None:
    """Initialise Sentry SDK if a DSN is configured."""
    sentry_dsn: str | None = settings.get("sentry_dsn")
    if sentry_dsn:
        import multiprocessing

        if multiprocessing.current_process().name == "MainProcess":
            try:
                import sentry_sdk

                sentry_sdk.init(
                    dsn=sentry_dsn,
                    traces_sample_rate=1.0,
                    profiles_sample_rate=1.0,
                )
            except Exception as e:
                logger.error("Failed to initialise Sentry: %s", e)


def _preserve_llm_profiles(settings_dict: dict[str, Any]) -> None:
    """Ensure ``llm_profiles`` is not accidentally wiped when saving.

    If the incoming dict has no profiles but the in-memory settings
    (or disk) do, the existing profiles are preserved.

    Args:
        settings_dict: The settings dict being saved (mutated in-place).
    """
    incoming: list[Any] | None = settings_dict.get("llm_profiles")
    if not incoming:
        existing: list[dict[str, Any]] = settings.get("llm_profiles", [])
        if not existing:
            try:
                with open(SETTINGS_FILE) as f:
                    disk: dict[str, Any] = json.load(f)
                    existing = disk.get("llm_profiles", [])
            except Exception:
                pass
        if existing:
            settings_dict["llm_profiles"] = existing
            settings_dict["active_llm_profile_id"] = (
                settings_dict.get("active_llm_profile_id")
                or settings.get("active_llm_profile_id")
                or (existing[0].get("id") if existing else "")
            )

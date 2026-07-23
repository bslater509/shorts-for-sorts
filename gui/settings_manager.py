# Settings load/save — manages settings.json and free Zen LLM profiles

import json
import os
import uuid

from gui.config import SETTINGS_FILE, FREE_ZEN_MODELS, ZEN_BASE_URL, console, logger
from gui.state import settings


def load_settings():
    # Load defaults from the template file if it exists
    defaults = {}
    template_file = os.path.join(os.path.dirname(SETTINGS_FILE), "settings.json.template")
    if os.path.exists(template_file):
        try:
            with open(template_file) as f:
                defaults = json.load(f)
                if defaults.get("api_key") == "YOUR_API_KEY_HERE":
                    defaults["api_key"] = ""
        except Exception as e:
            logger.warning(
                f"Failed to load defaults from template {template_file}: {e}", exc_info=True
            )

    # Build new settings dict first, then atomically swap
    new = {}
    new.update(defaults)

    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                new_settings = json.load(f)
                new.update(new_settings)
        except Exception as e:
            logger.warning(f"Failed to load settings from {SETTINGS_FILE}: {e}", exc_info=True)

    settings.clear()
    settings.update(new)

    # Auto-migrate legacy LLM config
    if "llm_profiles" not in settings:
        settings["llm_profiles"] = []

    has_legacy_keys = any(k in settings for k in ["api_key", "base_url", "model"])
    if has_legacy_keys and not settings.get("llm_profiles"):
        profile_id = str(uuid.uuid4())
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
    migrated = False
    for k in ["api_key", "base_url", "model"]:
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
                f"Failed to write default settings to {SETTINGS_FILE}: {e}", exc_info=True
            )

    # --- Auto-populate / prune free Zen LLM profiles ---
    profiles = settings.get("llm_profiles", [])
    free_models = {m["model"] for m in FREE_ZEN_MODELS}
    changed = False
    active_id = settings.get("active_llm_profile_id", "")

    # Remove stale Zen profiles (model no longer in free list)
    cleaned = [
        p for p in profiles
        if not (p.get("base_url", "").rstrip("/") == ZEN_BASE_URL
                and p.get("model") not in free_models)
    ]
    if len(cleaned) != len(profiles):
        changed = True
        settings["llm_profiles"] = profiles = cleaned
        if active_id and active_id not in {p["id"] for p in profiles}:
            settings["active_llm_profile_id"] = profiles[0]["id"] if profiles else ""

    # Extract an API key from an existing profile (Go or first with a key)
    api_key = next((p["api_key"] for p in profiles if p.get("api_key")), "")

    # Add missing free Zen models
    existing = {(p.get("base_url", "").rstrip("/"), p.get("model")) for p in profiles}
    for fm in FREE_ZEN_MODELS:
        if (ZEN_BASE_URL, fm["model"]) not in existing:
            profiles.append({
                "id": fm["id"],
                "name": fm["name"],
                "api_key": api_key,
                "base_url": ZEN_BASE_URL,
                "model": fm["model"],
            })
            changed = True
            settings["llm_profiles"] = profiles

    if changed:
        save_settings(settings)

    import sentry_sdk

    sentry_dsn = settings.get("sentry_dsn")
    if sentry_dsn:
        import multiprocessing

        if multiprocessing.current_process().name == "MainProcess":
            try:
                sentry_sdk.init(dsn=sentry_dsn, traces_sample_rate=1.0, profiles_sample_rate=1.0)
            except Exception as e:
                logger.error(f"Failed to initialize Sentry: {e}")

    return settings


def save_settings(settings_dict):
    # Prevent accidentally wiping llm_profiles — if the incoming dict has no
    # profiles but the in-memory settings (or disk) do, preserve the existing ones.
    incoming = settings_dict.get("llm_profiles")
    if not incoming:
        existing = settings.get("llm_profiles", [])
        if not existing:
            try:
                with open(SETTINGS_FILE) as f:
                    disk = json.load(f)
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

    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings_dict, f, indent=2)
        if settings is not settings_dict:
            settings.clear()
            settings.update(settings_dict)
        return True
    except Exception as e:
        logger.warning(f"Failed to save settings to {SETTINGS_FILE}: {e}", exc_info=True)
        return False

"""Settings, presets, state, and voices routes."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, HTTPException

import gui.state as shared_state
from gui.config import (
    GUI_STATE_FILE,
    delete_custom_preset,
    load_presets,
    load_settings,
    logger,
    save_custom_preset,
    save_settings,
)
from gui.models import FetchModelsRequest, PresetModel, SettingsModel, StateModel

router: APIRouter = APIRouter()


@router.get("/api/settings")
def get_api_settings() -> dict[str, Any]:
    """Return the current application settings (reloaded from disk)."""
    load_settings()
    return shared_state.settings


@router.post("/api/settings")
def save_api_settings(data: SettingsModel) -> dict[str, str]:
    """Save application settings to disk.

    Args:
        data: The full settings payload.

    Returns:
        Status message on success or failure.
    """
    settings_dict: dict[str, Any] = data.model_dump()
    success: bool = save_settings(settings_dict)
    if success:
        return {"status": "success", "message": "Settings saved successfully."}
    raise HTTPException(status_code=500, detail="Failed to save settings to disk.")


@router.post("/api/llm/models")
def fetch_llm_models(data: FetchModelsRequest) -> dict[str, Any]:
    """Fetch available model IDs from an OpenAI-compatible API.

    Args:
        data: Request with optional ``api_key`` and ``base_url`` overrides.

    Returns:
        Sorted list of model IDs.

    Raises:
        HTTPException: If the API key is missing or the fetch fails.
    """
    api_key: str = (
        data.api_key.strip()
        if data.api_key
        else os.environ.get("OPENAI_API_KEY", "")
    )
    base_url: str = (
        data.base_url.strip()
        if data.base_url
        else os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )

    if not api_key:
        raise HTTPException(
            status_code=400, detail="API Key is required to fetch models."
        )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        models = client.models.list()
        model_ids: list[str] = sorted([m.id for m in models.data])
        return {"status": "success", "models": model_ids}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch models: {str(e)}"
        ) from e


@router.get("/api/presets")
def get_api_presets() -> dict[str, Any]:
    """Return all presets (built-in + custom) combined."""
    return load_presets()


@router.post("/api/presets")
def save_api_preset(data: PresetModel) -> dict[str, str]:
    """Save a custom preset.

    Args:
        data: The preset configuration (``name`` field is used as the key).

    Returns:
        Status message on success or failure.
    """
    preset_dict: dict[str, Any] = data.model_dump()
    name: str = preset_dict.pop("name")
    success = save_custom_preset(name, preset_dict)
    if success:
        return {
            "status": "success",
            "message": f"Preset '{name}' saved successfully.",
        }
    raise HTTPException(status_code=500, detail="Failed to save preset.")


@router.delete("/api/presets/{name}")
def delete_api_preset(name: str) -> dict[str, str]:
    """Delete a custom preset by name.

    Args:
        name: The display name of the preset to delete.

    Returns:
        Status message on success.
    """
    success = delete_custom_preset(name)
    if success:
        return {
            "status": "success",
            "message": f"Preset '{name}' deleted successfully.",
        }
    raise HTTPException(
        status_code=400,
        detail=f"Preset '{name}' could not be deleted "
        f"(might be builtin or not found).",
    )


@router.get("/api/state")
def get_api_state() -> dict[str, Any]:
    """Return the current session state."""
    return shared_state.state


@router.post("/api/state")
def save_api_state(data: StateModel) -> dict[str, Any]:
    """Update session state and persist to disk.

    Args:
        data: The state payload to merge into the current session state.

    Returns:
        Updated state with status.
    """
    for k, v in data.model_dump().items():
        shared_state.state[k] = v

    try:
        with open(GUI_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(shared_state.state, f, indent=2)
    except Exception as e:
        logger.error("Failed to save gui_state.json: %s", e)

    return {"status": "success", "data": shared_state.state}


@router.get("/api/voices")
def get_api_voices() -> list[dict[str, str]]:
    """Return available voice options.

    Returns:
        List of ``{"name": ..., "value": ...}`` dicts.
    """
    return [
        {"name": name, "value": val} for name, val in shared_state.VOICES
    ]

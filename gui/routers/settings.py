"""Settings, presets, state, and voices routes."""

import json
import os

from fastapi import APIRouter, HTTPException

import gui.state as shared_state
from gui.config import (
    BASE_DIR,
    GUI_STATE_FILE,
    delete_custom_preset,
    load_presets,
    load_settings,
    logger,
    save_custom_preset,
    save_settings,
)
from gui.models import FetchModelsRequest, PresetModel, SettingsModel, StateModel

router = APIRouter()


@router.get("/api/settings")
def get_api_settings():
    # reload settings from disk first
    load_settings()
    return shared_state.settings


@router.post("/api/settings")
def save_api_settings(data: SettingsModel):
    # Convert model to dict
    settings_dict = data.model_dump()

    success = save_settings(settings_dict)
    if success:
        return {"status": "success", "message": "Settings saved successfully."}
    else:
        raise HTTPException(status_code=500, detail="Failed to save settings to disk.")


@router.post("/api/llm/models")
def fetch_llm_models(data: FetchModelsRequest):
    api_key = data.api_key.strip() if data.api_key else os.environ.get("OPENAI_API_KEY", "")
    base_url = (
        data.base_url.strip()
        if data.base_url
        else os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )

    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required to fetch models.")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        models = client.models.list()
        # Sort models alphabetically
        model_ids = sorted([m.id for m in models.data])
        return {"status": "success", "models": model_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch models: {str(e)}")


@router.get("/api/presets")
def get_api_presets():
    # Combination of builtin and custom presets
    presets = load_presets()
    return presets


@router.post("/api/presets")
def save_api_preset(data: PresetModel):
    preset_dict = data.model_dump()
    name = preset_dict.pop("name")
    success = save_custom_preset(name, preset_dict)
    if success:
        return {"status": "success", "message": f"Preset '{name}' saved successfully."}
    else:
        raise HTTPException(status_code=500, detail="Failed to save preset.")


@router.delete("/api/presets/{name}")
def delete_api_preset(name: str):
    success = delete_custom_preset(name)
    if success:
        return {"status": "success", "message": f"Preset '{name}' deleted successfully."}
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Preset '{name}' could not be deleted (might be builtin or not found).",
        )


@router.get("/api/state")
def get_api_state():
    return shared_state.state


@router.post("/api/state")
def save_api_state(data: StateModel):
    # Update global shared state
    for k, v in data.model_dump().items():
        shared_state.state[k] = v

    # Persist gui state to disk
    try:
        with open(GUI_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(shared_state.state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save gui_state.json: {e}")

    return {"status": "success", "data": shared_state.state}


@router.get("/api/voices")
def get_api_voices():
    # Return mapping of friendly name and internal tag
    return [{"name": name, "value": val} for name, val in shared_state.VOICES]

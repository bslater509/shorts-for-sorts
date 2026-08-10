"""LLM debug record viewer — list and fetch raw generation sidecar files."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, HTTPException

from gui.config import LLM_DEBUG_DIR, logger

router: APIRouter = APIRouter()


# ---------------------------------------------------------------------------
# Summary keys extracted from each .llm.json record for the list endpoint.
# Large fields (raw_response, thinking_content, system_prompt, prompt) are
# excluded here to keep list payloads small.
# ---------------------------------------------------------------------------

_SUMMARY_KEYS: tuple[str, ...] = (
    "job_index",
    "model",
    "script_temp",
    "generated_at",
    "title",
    "hashtags",
    "output_filename",
    "diagnostics",
)


_LLM_JSON_SUFFIX: str = ".llm.json"


def _list_debug_files() -> list[str]:
    """Return base names (without ``.llm.json``) sorted by mtime newest first.

    Returns an empty list when the debug directory does not exist.
    """
    if not os.path.isdir(LLM_DEBUG_DIR):
        return []
    entries: list[tuple[str, float]] = []
    for f in os.listdir(LLM_DEBUG_DIR):
        if f.endswith(_LLM_JSON_SUFFIX):
            fp = os.path.join(LLM_DEBUG_DIR, f)
            base = f[: -len(_LLM_JSON_SUFFIX)]
            entries.append((base, os.path.getmtime(fp)))
    entries.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in entries]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/api/llm/debug")
def list_llm_debug_records() -> dict[str, list[dict[str, Any]]]:
    """List all LLM debug records with summary fields only.

    Returns:
        ``{"records": [...]}`` sorted by file modification time
        (newest first).  Each record contains a slimmed subset of the
        full sidecar — large fields such as ``raw_response`` and
        ``thinking_content`` are excluded from the list.  Use the detail
        endpoint to fetch the complete record.
    """
    records: list[dict[str, Any]] = []
    for base_name in _list_debug_files():
        path = os.path.join(LLM_DEBUG_DIR, f"{base_name}.llm.json")
        try:
            with open(path, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("[LLM-Debug] Failed to read %s: %s", path, e)
            continue
        summary = {k: data.get(k) for k in _SUMMARY_KEYS}
        summary["base_name"] = base_name
        records.append(summary)
    return {"records": records}


@router.get("/api/llm/debug/{base_name}")
def get_llm_debug_record(base_name: str) -> dict[str, Any]:
    """Return the complete LLM debug record for a given base name.

    Args:
        base_name: The filename stem of the sidecar file
            (e.g. ``cool_cats_20240808_5``).

    Returns:
        The full parsed JSON content of the ``.llm.json`` sidecar.

    Raises:
        HTTPException: 404 if the file does not exist.
    """
    # Basic path-traversal guard — reject names with slashes or dots.
    if "/" in base_name or "\\" in base_name or ".." in base_name:
        raise HTTPException(status_code=400, detail="Invalid base name")

    path = os.path.join(LLM_DEBUG_DIR, f"{base_name}.llm.json")
    real = os.path.realpath(path)
    if not real.startswith(os.path.realpath(LLM_DEBUG_DIR)):
        raise HTTPException(status_code=400, detail="Path traversal denied")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Record not found")

    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500, detail=f"Malformed JSON in sidecar: {e}"
        ) from e
    except OSError as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to read sidecar: {e}"
        ) from e


@router.delete("/api/llm/debug/{base_name}")
def delete_llm_debug_record(base_name: str) -> dict[str, str]:
    """Delete a single LLM debug record.

    Args:
        base_name: The filename stem of the sidecar to delete.

    Returns:
        ``{"status": "deleted"}`` on success.

    Raises:
        HTTPException: 404 if the file does not exist.
    """
    if "/" in base_name or "\\" in base_name or ".." in base_name:
        raise HTTPException(status_code=400, detail="Invalid base name")

    path = os.path.join(LLM_DEBUG_DIR, f"{base_name}.llm.json")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Record not found")
    os.remove(path)
    logger.info("[LLM-Debug] Deleted sidecar: %s", path)
    return {"status": "deleted"}

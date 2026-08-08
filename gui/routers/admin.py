"""Admin and utility routes: restart, batch stats, health check."""

from __future__ import annotations

import contextlib
import json
import os
import sys
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

import gui.state as shared_state
from gui.batch_engine import (
    DEFAULT_PHASE_WEIGHTS,
    _batch_state_lock,
    _save_phase_weights,
    batch_state,
)
from gui.config import BASE_DIR, BATCH_STATS_FILE, logger

router: APIRouter = APIRouter()


@router.post("/api/restart")
def restart_server(
    request: Request, background_tasks: BackgroundTasks
) -> dict[str, str]:
    """Rebuild frontend and restart the server process.

    Requires a valid ``X-Admin-Token`` header if ``admin_token`` is configured.

    Args:
        request: The incoming HTTP request (used for header extraction).
        background_tasks: FastAPI background task manager.

    Returns:
        Status response indicating restart has been scheduled.
    """
    admin_token: str | None = shared_state.settings.get("admin_token")
    if admin_token:
        req_token: str = request.headers.get("X-Admin-Token", "")
        if req_token != admin_token:
            raise HTTPException(status_code=403, detail="Invalid admin token")

    def _restart() -> None:
        """Cancel in-progress batch, shut down workers, and restart the server."""
        logger.info("Restarting server via run-gui.sh...")

        # Cancel any in-progress batch and shut down workers before
        # replacing the process so spawn children aren't orphaned.
        batch_state["should_cancel"] = True
        for _key in ("executor", "llm_executor"):
            _ex = batch_state.get(_key)
            if _ex is not None:
                with contextlib.suppress(Exception):
                    _ex.shutdown(wait=False, cancel_futures=True)
        import time
        time.sleep(0.5)  # brief window for spawned children to receive SIGTERM

        script: str = os.path.join(BASE_DIR, "run-gui.sh")
        os.execv("/bin/bash", ["bash", script] + sys.argv[1:])

    background_tasks.add_task(_restart)
    return {"status": "restarting"}


@router.get("/api/batch/stats")
def get_batch_stats() -> dict[str, Any]:
    """Return learned batch phase weights, duration averages, per-job stats, and rates.

    Returns:
        Dictionary with ``phase_ratios``, ``sample_count``,
        ``avg_llm_duration``, ``avg_video_duration``, ``per_job_stats``,
        and ``phase_rates``.
    """
    try:
        if os.path.exists(BATCH_STATS_FILE):
            with open(BATCH_STATS_FILE) as f:
                data: dict[str, Any] = json.load(f)
            # Safety net: derive sample_count from per_job_stats so they never diverge
            per_job_stats: list[Any] = data.get("per_job_stats", [])
            if data.get("sample_count", 0) != len(per_job_stats):
                data["sample_count"] = len(per_job_stats)
            return data
    except Exception:
        pass
    return {
        "phase_ratios": dict(DEFAULT_PHASE_WEIGHTS),
        "sample_count": 0,
        "avg_llm_duration": None,
        "avg_video_duration": None,
        "per_job_stats": [],
        "phase_rates": {},
    }


@router.post("/api/batch/stats/reset")
def reset_batch_stats() -> dict[str, Any]:
    """Reset learned batch analytics back to defaults.

    Refuses to run while a batch is in progress. Clears both the on-disk
    stats file and the in-memory cached stats so a later batch completion
    cannot re-persist stale data.

    Returns:
        The default stats payload (identical shape to ``get_batch_stats``).
    """
    if batch_state.get("in_progress"):
        raise HTTPException(
            status_code=409,
            detail="Cannot reset analytics while a batch is running",
        )
    defaults: dict[str, Any] = dict(DEFAULT_PHASE_WEIGHTS)
    _save_phase_weights(defaults, 0, None, None, [], {})
    with _batch_state_lock:
        batch_state["_per_job_stats"] = []
        batch_state["_phase_weights"] = None
        batch_state["_avg_llm_duration"] = None
        batch_state["_avg_video_duration"] = None
        batch_state["_phase_rates"] = {}
        batch_state["_job_features"] = {}
    return {
        "phase_ratios": defaults,
        "sample_count": 0,
        "avg_llm_duration": None,
        "avg_video_duration": None,
        "phase_rates": {},
        "per_job_stats": [],
    }


@router.post("/api/log")
def client_log(payload: dict[str, Any]) -> dict[str, str]:
    """Accept client-side error reports forwarded from the frontend console."""
    with contextlib.suppress(Exception):
        logger.warning(
            "Frontend %s: %s",
            payload.get("level", "error"),
            str(payload.get("message", ""))[:500],
        )
    return {"status": "ok"}


@router.get("/api/health")
def health_check() -> dict[str, str]:
    """Simple health check endpoint.

    Returns:
        ``{"status": "ok"}`` when the server is running.
    """
    return {"status": "ok"}

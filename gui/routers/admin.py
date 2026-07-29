"""Admin and utility routes: restart, batch stats, health check."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

import gui.state as shared_state
from gui.batch_engine import DEFAULT_PHASE_WEIGHTS
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
        """Rebuild frontend (if source exists) and exec the current process."""
        frontend_dir: str = os.path.join(BASE_DIR, "gui/frontend")
        package_json: str = os.path.join(frontend_dir, "package.json")
        if os.path.exists(package_json):
            logger.info("Rebuilding frontend...")
            npm: str = "npm.cmd" if sys.platform == "win32" else "npm"
            result = subprocess.run(
                [npm, "run", "build"],
                cwd=frontend_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                logger.error("Frontend rebuild failed: %s", result.stderr.strip())
                return
            logger.info("Frontend rebuilt successfully.")
        else:
            logger.info("No frontend source found — skipping rebuild.")
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    background_tasks.add_task(_restart)
    return {"status": "restarting"}


@router.get("/api/batch/stats")
def get_batch_stats() -> dict[str, Any]:
    """Return learned batch phase weights, duration averages, and per-job stats.

    Returns:
        Dictionary with ``phase_ratios``, ``sample_count``,
        ``avg_llm_duration``, ``avg_video_duration``, and ``per_job_stats``.
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
    }


@router.get("/api/health")
def health_check() -> dict[str, str]:
    """Simple health check endpoint.

    Returns:
        ``{"status": "ok"}`` when the server is running.
    """
    return {"status": "ok"}

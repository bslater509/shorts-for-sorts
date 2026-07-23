"""Admin and utility routes: restart, batch stats, health check."""

import json
import os
import subprocess
import sys
import time

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

import gui.state as shared_state
from gui.batch_engine import DEFAULT_PHASE_WEIGHTS
from gui.config import BATCH_STATS_FILE, BASE_DIR, logger

router = APIRouter()


@router.post("/api/restart")
def restart_server(request: Request, background_tasks: BackgroundTasks):
    admin_token = shared_state.settings.get("admin_token")
    if admin_token:
        req_token = request.headers.get("X-Admin-Token", "")
        if req_token != admin_token:
            raise HTTPException(status_code=403, detail="Invalid admin token")

    def restart():
        frontend_dir = os.path.join(BASE_DIR, "gui/frontend")
        package_json = os.path.join(frontend_dir, "package.json")
        if os.path.exists(package_json):
            logger.info("Rebuilding frontend...")
            npm = "npm.cmd" if sys.platform == "win32" else "npm"
            result = subprocess.run(
                [npm, "run", "build"], cwd=frontend_dir, capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                logger.error(f"Frontend rebuild failed: {result.stderr.strip()}")
                return
            logger.info("Frontend rebuilt successfully.")
        else:
            logger.info("No frontend source found — skipping rebuild.")
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    background_tasks.add_task(restart)
    return {"status": "restarting"}


@router.get("/api/batch/stats")
def get_batch_stats():
    try:
        if os.path.exists(BATCH_STATS_FILE):
            with open(BATCH_STATS_FILE, "r") as f:
                data = json.load(f)
            # Safety net: derive sample_count from per_job_stats so they never diverge
            per_job_stats = data.get("per_job_stats", [])
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
def health_check():
    return {"status": "ok"}

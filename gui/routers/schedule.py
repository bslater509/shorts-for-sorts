"""Scheduled batch generation REST API routes."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException

from gui.config import logger
from gui.models import ScheduleModel
from gui.scheduler import (
    compute_next_fire,
    delete_schedule,
    get_schedule,
    get_scheduler_status,
    load_schedules,
    run_schedule_now,
    upsert_schedule,
)

router: APIRouter = APIRouter()

# --- Constants ---

TIME_RE: re.Pattern = re.compile(r"^\d{2}:\d{2}$")
"""Regex matching a raw ``HH:MM`` time string."""

VALID_CADENCES: tuple[str, ...] = ("daily", "weekly", "interval")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_schedule(data: ScheduleModel) -> None:
    """Validate schedule fields, raising HTTP 400 on invalid input.

    Args:
        data: The schedule payload to validate.

    Raises:
        HTTPException: If any schedule field fails validation.
    """
    cadence: str = data.cadence
    if cadence not in VALID_CADENCES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cadence '{cadence}'. Must be one of "
            f"{', '.join(VALID_CADENCES)}.",
        )

    for t in data.times:
        if not _is_valid_hhmm(t):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid time '{t}'. Times must be in HH:MM format.",
            )

    # Interval window boundaries are also HH:MM time strings.
    for t in (data.interval_start, data.interval_end):
        if not _is_valid_hhmm(t):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid time '{t}'. Times must be in HH:MM format.",
            )

    for d in data.days:
        if not 1 <= d <= 7:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid day '{d}'. Days must be between 1 (Mon) and 7 (Sun).",
            )

    if data.jitter_minutes < 0:
        raise HTTPException(
            status_code=400,
            detail="jitter_minutes must be greater than or equal to 0.",
        )

    if data.stagger_enabled and data.stagger_min_minutes > data.stagger_max_minutes:
        raise HTTPException(
            status_code=400,
            detail="stagger_min_minutes must be less than or equal to "
            "stagger_max_minutes when stagger is enabled.",
        )

    if cadence == "interval" and data.interval_hours < 1:
        raise HTTPException(
            status_code=400,
            detail="interval_hours must be greater than or equal to 1 "
            "for interval cadence.",
        )


def _is_valid_hhmm(value: str) -> bool:
    """Return True if ``value`` is a valid ``HH:MM`` time string.

    Args:
        value: The time string to check.

    Returns:
        True if the string matches ``HH:MM`` with hour < 24 and minute < 60.
    """
    if not TIME_RE.match(value):
        return False
    try:
        hour: int = int(value[:2])
        minute: int = int(value[3:])
    except ValueError:
        return False
    return 0 <= hour <= 23 and 0 <= minute <= 59


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/api/schedules")
def list_schedules() -> dict[str, Any]:
    """Return all configured schedules with their next run times.

    The ``next_run`` value is taken from the persisted schedule when present,
    otherwise recomputed from the current time via ``compute_next_fire``.

    Returns:
        Dict with a ``schedules`` list and a ``count`` of total schedules.
    """
    schedules: list[dict[str, Any]] = load_schedules()
    scheduled_list: list[dict[str, Any]] = []
    for s in schedules:
        entry: dict[str, Any] = dict(s)
        persisted_next = entry.get("next_run")
        if persisted_next:
            entry["next_run"] = persisted_next
        else:
            next_fire = compute_next_fire(s)
            entry["next_run"] = next_fire.isoformat() if next_fire else None
        scheduled_list.append(entry)
    return {"schedules": scheduled_list, "count": len(scheduled_list)}


@router.post("/api/schedules")
def create_schedule(data: ScheduleModel) -> dict[str, Any]:
    """Create a new schedule.

    Args:
        data: The schedule payload.

    Returns:
        ``{"status": "created", "schedule": saved}`` on success.

    Raises:
        HTTPException: If the payload fails validation.
    """
    _validate_schedule(data)
    saved: dict[str, Any] = upsert_schedule(data.model_dump())
    logger.info("Created schedule '%s' (%s)", saved.get("id"), saved.get("name", ""))
    return {"status": "created", "schedule": saved}


@router.put("/api/schedules/{schedule_id}")
def update_schedule(schedule_id: str, data: ScheduleModel) -> dict[str, Any]:
    """Update an existing schedule.

    Args:
        schedule_id: The ID of the schedule to update.
        data: The schedule payload to apply.

    Returns:
        ``{"status": "updated", "schedule": saved}`` on success.

    Raises:
        HTTPException: If the schedule does not exist or the payload is invalid.
    """
    _validate_schedule(data)
    if get_schedule(schedule_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Schedule '{schedule_id}' not found."
        )
    data.id = schedule_id
    saved: dict[str, Any] = upsert_schedule(data.model_dump())
    logger.info("Updated schedule '%s'", schedule_id)
    return {"status": "updated", "schedule": saved}


@router.delete("/api/schedules/{schedule_id}")
def delete_schedule_endpoint(schedule_id: str) -> dict[str, str]:
    """Delete a schedule.

    Args:
        schedule_id: The ID of the schedule to delete.

    Returns:
        ``{"status": "deleted"}`` on success.

    Raises:
        HTTPException: If the schedule does not exist or deletion fails.
    """
    if get_schedule(schedule_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Schedule '{schedule_id}' not found."
        )
    if not delete_schedule(schedule_id):
        raise HTTPException(
            status_code=500, detail=f"Failed to delete schedule '{schedule_id}'."
        )
    logger.info("Deleted schedule '%s'", schedule_id)
    return {"status": "deleted"}


@router.post("/api/schedules/{schedule_id}/toggle")
def toggle_schedule(schedule_id: str) -> dict[str, Any]:
    """Toggle whether a schedule is enabled.

    Args:
        schedule_id: The ID of the schedule to toggle.

    Returns:
        The updated schedule with its ``enabled`` flag flipped.

    Raises:
        HTTPException: If the schedule does not exist.
    """
    schedule: dict[str, Any] | None = get_schedule(schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=404, detail=f"Schedule '{schedule_id}' not found."
        )
    schedule["enabled"] = not schedule.get("enabled", True)
    saved: dict[str, Any] = upsert_schedule(schedule)
    logger.info("Toggled schedule '%s' enabled=%s", schedule_id, saved.get("enabled"))
    return {"status": "toggled", "schedule": saved}


@router.post("/api/schedules/{schedule_id}/run")
def run_schedule_now_endpoint(schedule_id: str) -> dict[str, str]:
    """Trigger a schedule run immediately.

    Args:
        schedule_id: The ID of the schedule to run.

    Returns:
        Result dict from the scheduler (e.g. run status and message).

    Raises:
        HTTPException: If the schedule does not exist.
    """
    if get_schedule(schedule_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Schedule '{schedule_id}' not found."
        )
    return run_schedule_now(schedule_id)


@router.get("/api/schedules/status")
def get_schedule_status() -> dict[str, Any]:
    """Return scheduler status and the number of configured schedules.

    Returns:
        Scheduler status dict with an added ``schedules_count`` field.
    """
    status: dict[str, Any] = get_scheduler_status()
    status["schedules_count"] = len(load_schedules())
    return status

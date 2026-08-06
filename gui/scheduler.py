"""Automated batch scheduler — persistent schedules, staggered firing, and a daemon thread.

Provides schedule CRUD persistence (``config/schedules.json``), deterministic
next-fire computation for daily / weekly / interval cadences with jitter,
stagger-delay calculation for spaced TikTok posting, and a background daemon
thread that polls due schedules and launches batch generation runs.
"""

from __future__ import annotations

import datetime
import json
import os
import random
import threading
import time
import uuid
from typing import Any

from fastapi import HTTPException

from gui.config import SCHEDULES_FILE, logger
from gui.models import BatchStartRequest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEDULER_POLL_INTERVAL: int = 30
"""Seconds between scheduler daemon polls."""

SCHEDULER_GRACE_MINUTES: int = 5
"""Grace window (minutes) before ``next_run`` that still triggers a fire."""

_scheduler_running: threading.Event = threading.Event()
"""Set while the scheduler daemon thread is active."""

_scheduler_lock: threading.Lock = threading.Lock()
"""Guards scheduler thread start/stop against concurrent calls."""

_scheduler_thread: threading.Thread | None = None
"""Reference to the running scheduler daemon thread (if any)."""

_schedules_lock: threading.RLock = threading.RLock()
"""Guards schedules file read/write from concurrent threads."""

# ---------------------------------------------------------------------------
# Schedule persistence
# ---------------------------------------------------------------------------


def load_schedules() -> list[dict]:
    """Load persisted schedules from ``SCHEDULES_FILE``.

    Returns:
        List of schedule dicts, or an empty list on any failure.
    """
    with _schedules_lock:
        try:
            if os.path.exists(SCHEDULES_FILE):
                with open(SCHEDULES_FILE) as f:
                    data: Any = json.load(f)
                if isinstance(data, list):
                    return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load schedules: %s", e)
    return []


def save_schedules(schedules: list[dict]) -> None:
    """Persist the given schedules to ``SCHEDULES_FILE``.

    Args:
        schedules: List of schedule dicts to write.
    """
    with _schedules_lock:
        try:
            os.makedirs(os.path.dirname(SCHEDULES_FILE), exist_ok=True)
            with open(SCHEDULES_FILE, "w") as f:
                json.dump(schedules, f, indent=2)
        except OSError as e:
            logger.warning("Failed to save schedules: %s", e)


def get_schedule(schedule_id: str) -> dict | None:
    """Fetch a single schedule by id.

    Args:
        schedule_id: The schedule's id.

    Returns:
        The matching schedule dict, or ``None`` if not found.
    """
    for schedule in load_schedules():
        if str(schedule.get("id", "")) == schedule_id:
            return schedule
    return None


def upsert_schedule(schedule_data: dict) -> dict:
    """Insert or replace a schedule by id, then persist the list.

    Generates a ``uuid4`` hex id when missing and sets ``created_at`` for
    newly created schedules.  Existing schedules are replaced in place
    (``created_at`` is left untouched).

    Args:
        schedule_data: The schedule dict to upsert (mutated in place).

    Returns:
        The upserted schedule dict.
    """
    with _schedules_lock:
        schedules: list[dict] = load_schedules()
        schedule_id: str = str(schedule_data.get("id") or "").strip()
        replace_index: int | None = None
        for i, existing in enumerate(schedules):
            if schedule_id and str(existing.get("id", "")) == schedule_id:
                replace_index = i
                break
        if replace_index is not None:
            # Preserve the original creation time on updates, since the
            # schedule payload model does not carry a ``created_at`` field.
            if not schedule_data.get("created_at") and schedules[replace_index].get(
                "created_at"
            ):
                schedule_data["created_at"] = schedules[replace_index]["created_at"]
            schedules[replace_index] = schedule_data
        else:
            if not schedule_id:
                schedule_id = uuid.uuid4().hex
                schedule_data["id"] = schedule_id
            if not schedule_data.get("created_at"):
                schedule_data["created_at"] = datetime.datetime.now().isoformat()
            schedules.append(schedule_data)
        save_schedules(schedules)
    return schedule_data


def delete_schedule(schedule_id: str) -> bool:
    """Delete a schedule by id.

    Args:
        schedule_id: The schedule's id to remove.

    Returns:
        ``True`` if a schedule was found and deleted, ``False`` otherwise.
    """
    with _schedules_lock:
        schedules: list[dict] = load_schedules()
        filtered: list[dict] = [
            s for s in schedules if str(s.get("id", "")) != schedule_id
        ]
        if len(filtered) == len(schedules):
            return False
        save_schedules(filtered)
    return True


# ---------------------------------------------------------------------------
# Stagger delay computation
# ---------------------------------------------------------------------------


def compute_stagger_delays(
    num_shorts: int, min_minutes: int, max_minutes: int
) -> dict[int, float]:
    """Compute cumulative per-job TikTok post delays in seconds.

    Job 1 posts immediately (``0.0`` seconds); each subsequent job is delayed
    by its own random interval in ``[min_minutes, max_minutes]`` minutes on
    top of the previous job's delay, so posts are spread out over time.

    Args:
        num_shorts: Number of shorts in the batch (1-based job indices).
        min_minutes: Minimum random stagger interval in minutes.
        max_minutes: Maximum random stagger interval in minutes.

    Returns:
        Dict mapping job index to cumulative delay in seconds, or an empty
        dict when ``num_shorts < 2`` or ``min_minutes > max_minutes``.
    """
    if num_shorts < 2 or min_minutes > max_minutes:
        return {}
    delays: dict[int, float] = {1: 0.0}
    for i in range(2, num_shorts + 1):
        delays[i] = delays[i - 1] + random.uniform(min_minutes, max_minutes) * 60.0
    return delays


# ---------------------------------------------------------------------------
# Next-fire time computation
# ---------------------------------------------------------------------------


def _parse_time(t: str) -> tuple[int, int]:
    """Parse a ``"HH:MM"`` string into an ``(hour, minute)`` tuple.

    Args:
        t: Time string in ``HH:MM`` format.

    Returns:
        Tuple of ``(hour, minute)`` ints.  Falls back to ``(0, 0)`` for
        malformed input.
    """
    hour_str, _, minute_str = str(t).partition(":")
    try:
        return int(hour_str), int(minute_str)
    except (ValueError, TypeError):
        return 0, 0


def _seeded_slot_random(schedule: dict, day: datetime.date, slot_index: int) -> random.Random:
    """Create a deterministic RNG for a given schedule/day/slot.

    Seeding on the calendar date (not time-of-day) keeps jitter stable within
    a day while varying between days.

    Args:
        schedule: The schedule dict.
        day: The calendar day the slot belongs to.
        slot_index: Zero-based index of the slot within the day.

    Returns:
        A seeded ``random.Random`` instance.
    """
    schedule_id: str = str(schedule.get("id", ""))
    cadence: str = str(schedule.get("cadence", "daily"))
    seed: str = f"{schedule_id}|{cadence}|{day.isoformat()}|{slot_index}"
    return random.Random(seed)


def _slots_for_day(schedule: dict, day: datetime.date) -> list[datetime.datetime]:
    """Compute all jittered candidate slots for one calendar day (daily/weekly).

    Args:
        schedule: The schedule dict.
        day: The calendar day to generate slots for.

    Returns:
        List of candidate datetimes, one per entry in ``schedule["times"]``.
    """
    times: list[str] = schedule.get("times") or []
    jitter_minutes: int = int(schedule.get("jitter_minutes", 0) or 0)
    slots: list[datetime.datetime] = []
    for index, t in enumerate(times):
        hour, minute = _parse_time(t)
        base: datetime.datetime = datetime.datetime.combine(
            day, datetime.time(hour, minute)
        )
        rng: random.Random = _seeded_slot_random(schedule, day, index)
        offset: int = rng.randint(-jitter_minutes, jitter_minutes)
        slots.append(base + datetime.timedelta(minutes=offset))
    return slots


def _interval_slots(schedule: dict, day: datetime.date) -> list[datetime.datetime]:
    """Generate jittered interval-cadence slots for one calendar day.

    Slots begin at ``interval_start`` and repeat every ``interval_hours``,
    stopping before ``interval_end`` (end exclusive).

    Args:
        schedule: The schedule dict.
        day: The calendar day to generate slots for.

    Returns:
        List of candidate datetimes, or an empty list when the interval
        produces no slots.
    """
    interval_hours: int = max(1, int(schedule.get("interval_hours", 3) or 3))
    start_h, start_m = _parse_time(str(schedule.get("interval_start", "08:00")))
    end_h, end_m = _parse_time(str(schedule.get("interval_end", "23:00")))
    jitter_minutes: int = int(schedule.get("jitter_minutes", 0) or 0)

    start: datetime.datetime = datetime.datetime.combine(
        day, datetime.time(start_h, start_m)
    )
    end: datetime.datetime = datetime.datetime.combine(
        day, datetime.time(end_h, end_m)
    )
    slots: list[datetime.datetime] = []
    slot: datetime.datetime = start
    index: int = 0
    while slot < end:
        rng: random.Random = _seeded_slot_random(schedule, day, index)
        offset: int = rng.randint(-jitter_minutes, jitter_minutes)
        slots.append(slot + datetime.timedelta(minutes=offset))
        slot += datetime.timedelta(hours=interval_hours)
        index += 1
    return slots


def compute_next_fire(
    schedule: dict, now: datetime.datetime | None = None
) -> datetime.datetime | None:
    """Compute the next fire time for a schedule deterministically.

    For the same ``(schedule, now)`` inputs the result is always identical:
    per-slot jitter is seeded from ``schedule_id + cadence + date + slot`` so
    it is stable within a day but varies between days.

    Cadence behaviours:
        - **daily**: earliest future jittered slot among ``times``; if all
          today's slots have passed, the earliest slot tomorrow.
        - **weekly**: same as daily, but only on days in ``days``
          (1=Mon .. 7=Sun); scans day offsets 0..13.
        - **interval**: slots every ``interval_hours`` from ``interval_start``
          to ``interval_end`` (exclusive); earliest future slot today, or the
          first slot tomorrow if all today's have passed.

    Args:
        schedule: The schedule dict.
        now: Current time to compare against (defaults to ``datetime.now()``).

    Returns:
        The next fire ``datetime``, or ``None`` if no times/days are
        configured for the schedule's cadence.
    """
    now = now if now is not None else datetime.datetime.now()
    cadence: str = str(schedule.get("cadence", "daily"))
    today: datetime.date = now.date()

    if cadence == "interval":
        slots: list[datetime.datetime] = _interval_slots(schedule, today)
        future: list[datetime.datetime] = [s for s in slots if s > now]
        if future:
            return min(future)
        tomorrow_slots: list[datetime.datetime] = _interval_slots(
            schedule, today + datetime.timedelta(days=1)
        )
        return min(tomorrow_slots) if tomorrow_slots else None

    times: list[str] = schedule.get("times") or []

    if cadence == "weekly":
        days: list[int] = schedule.get("days") or []
        if not times or not days:
            return None
        for offset in range(14):
            day: datetime.date = today + datetime.timedelta(days=offset)
            if (day.weekday() + 1) not in days:
                continue
            day_slots: list[datetime.datetime] = _slots_for_day(schedule, day)
            day_future: list[datetime.datetime] = [s for s in day_slots if s > now]
            if day_future:
                return min(day_future)
        return None

    # daily cadence
    if not times:
        return None
    today_slots: list[datetime.datetime] = _slots_for_day(schedule, today)
    today_future: list[datetime.datetime] = [s for s in today_slots if s > now]
    if today_future:
        return min(today_future)
    next_day_slots: list[datetime.datetime] = _slots_for_day(
        schedule, today + datetime.timedelta(days=1)
    )
    return min(next_day_slots) if next_day_slots else None


# ---------------------------------------------------------------------------
# Scheduler daemon thread
# ---------------------------------------------------------------------------


def start_scheduler_thread() -> None:
    """Start the scheduler daemon thread if it is not already running.

    Thread-safe: a second call while the thread is alive is a no-op.
    """
    global _scheduler_thread
    with _scheduler_lock:
        if (
            _scheduler_running.is_set()
            and _scheduler_thread is not None
            and _scheduler_thread.is_alive()
        ):
            return
        _scheduler_running.set()
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop, daemon=True, name="scheduler-thread"
        )
        _scheduler_thread.start()


def stop_scheduler_thread() -> None:
    """Signal the scheduler daemon thread to stop.

    Clears the running event so the loop exits after its current tick.
    Called on application shutdown.
    """
    with _scheduler_lock:
        _scheduler_running.clear()


def _parse_next_run(value: Any) -> datetime.datetime | None:
    """Parse a stored ``next_run`` ISO string into a datetime.

    Args:
        value: The stored ``next_run`` value (may be ``None`` or invalid).

    Returns:
        The parsed datetime, or ``None`` when missing/invalid.
    """
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _scheduler_loop() -> None:
    """Background daemon loop that polls and fires due schedules.

    Every ``SCHEDULER_POLL_INTERVAL`` seconds:
        - Loads schedules and fires any enabled schedule whose ``next_run``
          has arrived (within a 5-minute grace window).
        - For schedules without a valid ``next_run``, computes and persists
          the next fire time.
    Sleeps in 0.5 s increments via ``_scheduler_running`` for clean
    shutdown within 0.5 s.
    """
    logger.info("[Scheduler] Scheduler thread started")
    grace: datetime.timedelta = datetime.timedelta(minutes=SCHEDULER_GRACE_MINUTES)
    while _scheduler_running.is_set():
        try:
            schedules: list[dict] = load_schedules()
            now: datetime.datetime = datetime.datetime.now()
            changed: bool = False
            for schedule in schedules:
                if not schedule.get("enabled", True):
                    continue
                next_run: datetime.datetime | None = _parse_next_run(
                    schedule.get("next_run")
                )
                if next_run is not None and now >= next_run - grace:
                    _fire_schedule(schedule)
                else:
                    if next_run is None or next_run < now:
                        next_fire: datetime.datetime | None = compute_next_fire(
                            schedule, now
                        )
                        schedule["next_run"] = (
                            next_fire.isoformat() if next_fire is not None else None
                        )
                        changed = True
            if changed:
                save_schedules(schedules)
        except Exception:
            logger.exception("[Scheduler] Unexpected error in scheduler loop")
        # Sleep in 0.5 s increments so shutdown remains responsive
        # (Event.wait(timeout) returns immediately when the event is already
        # set, so it doesn't actually block – looping with small sleeps
        # achieves true 30-second polls while still checking for shutdown).
        for _ in range(SCHEDULER_POLL_INTERVAL * 2):
            if not _scheduler_running.is_set():
                break
            time.sleep(0.5)
    logger.info("[Scheduler] Scheduler thread stopped")


def _fire_schedule(schedule: dict) -> None:
    """Launch a batch for the given schedule, updating its status.

    Skips (marks ``last_status="skipped"``) when a batch is already running.
    On success sets ``last_status="running"``, ``last_run``, and clears
    ``next_run`` so the next poll computes the subsequent fire time.

    Args:
        schedule: The schedule dict to fire (mutated in place).
    """
    from gui.batch_engine import batch_state
    from gui.routers.batch import _launch_batch
    from gui.ws_manager import notify_clients

    schedule_id: str = str(schedule.get("id", "unknown"))
    name: str = str(schedule.get("name") or schedule_id)
    now: datetime.datetime = datetime.datetime.now()

    if batch_state.get("in_progress"):
        schedule["last_status"] = "skipped"
        # Advance past the slot we are about to fire so that the next poll
        # does not retry the exact same slot (which would cause a skip loop
        # while the running batch hasn't finished).
        target = _parse_next_run(schedule.get("next_run")) or now
        next_fire = compute_next_fire(schedule, target + datetime.timedelta(seconds=1))
        schedule["next_run"] = next_fire.isoformat() if next_fire else None
        upsert_schedule(schedule)
        logger.warning(
            "[Scheduler] Schedule '%s' skipped — batch already running", name
        )
        notify_clients(
            "schedule",
            "skipped",
            f"Schedule '{name}' skipped — a batch is already running.",
            level="warning",
            metadata={"schedule_id": schedule_id},
        )
        return

    num_shorts: int = max(1, int(schedule.get("num_shorts", 1) or 1))

    # Build per-job stagger delays for spaced TikTok posting.
    delays: dict[int, float] = {}
    if schedule.get("stagger_enabled") and num_shorts > 1:
        delays = compute_stagger_delays(
            num_shorts,
            int(schedule.get("stagger_min_minutes", 60) or 60),
            int(schedule.get("stagger_max_minutes", 240) or 240),
        )

    data: BatchStartRequest = BatchStartRequest(
        num_shorts=num_shorts,
        prompts=list(schedule.get("prompts") or []),
        enable_emojis=schedule.get("enable_emojis"),
        enable_emoji_animation=schedule.get("enable_emoji_animation"),
        emoji_scale_factor=schedule.get("emoji_scale_factor"),
        emoji_hold_duration=schedule.get("emoji_hold_duration"),
        emoji_throw_max_count=schedule.get("emoji_throw_max_count"),
        emoji_styles=schedule.get("emoji_styles"),
        layout=schedule.get("layout"),
        voice_id=schedule.get("voice_id"),
        sub_animation_style=schedule.get("sub_animation_style"),
        words_per_screen=schedule.get("words_per_screen"),
        single_word_mode=schedule.get("single_word_mode"),
        bg_music_path=schedule.get("bg_music_path"),
        script_temp=schedule.get("script_temp"),
        meta_temp=schedule.get("meta_temp"),
        max_workers=schedule.get("max_workers"),
        llm_max_workers=schedule.get("llm_max_workers"),
        post_to_tiktok=bool(schedule.get("post_to_tiktok", True)),
    )

    try:
        _launch_batch(data, tiktok_delays=delays)
    except HTTPException as e:
        # 400 = already running (normally guarded above) — treat as skipped.
        schedule["last_status"] = "skipped"
        schedule["last_error"] = str(e.detail)
        target = _parse_next_run(schedule.get("next_run")) or now
        next_fire = compute_next_fire(schedule, target + datetime.timedelta(seconds=1))
        schedule["next_run"] = next_fire.isoformat() if next_fire else None
        upsert_schedule(schedule)
        logger.warning(
            "[Scheduler] Schedule '%s' could not fire: %s", name, e.detail
        )
        return
    except Exception as e:
        logger.exception("[Scheduler] Schedule '%s' fire failed: %s", name, e)
        schedule["last_status"] = "failed"
        schedule["last_error"] = str(e)
        target = _parse_next_run(schedule.get("next_run")) or now
        next_fire = compute_next_fire(schedule, target + datetime.timedelta(seconds=1))
        schedule["next_run"] = next_fire.isoformat() if next_fire else None
        upsert_schedule(schedule)
        notify_clients(
            "schedule",
            "error",
            f"Schedule '{name}' failed to start: {e}",
            level="error",
            metadata={"schedule_id": schedule_id},
        )
        return

    schedule["last_status"] = "running"
    schedule["last_run"] = now.isoformat()
    schedule["next_run"] = None
    upsert_schedule(schedule)
    logger.info(
        "[Scheduler] Schedule '%s' fired — batch of %d shorts started",
        name,
        num_shorts,
    )
    notify_clients(
        "schedule",
        "started",
        f"Schedule '{name}' fired a batch of {num_shorts} shorts.",
        level="info",
        metadata={"schedule_id": schedule_id},
    )


# ---------------------------------------------------------------------------
# Run-now helper
# ---------------------------------------------------------------------------


def run_schedule_now(schedule_id: str) -> dict[str, str]:
    """Manually fire a schedule immediately, bypassing its ``next_run``.

    Reuses :func:`_fire_schedule` (firing immediately unless a batch is
    already in progress) after ensuring stagger/posting fields are set.

    Args:
        schedule_id: The schedule's id to fire.

    Returns:
        ``{"status": "running", ...}`` on launch, ``{"status": "skipped",
        ...}`` when a batch is already running, or ``{"status": "error",
        ...}`` if the schedule is missing or failed to start.
    """
    schedule: dict | None = get_schedule(schedule_id)
    if schedule is None:
        return {"status": "error", "message": f"Schedule '{schedule_id}' not found."}

    schedule.setdefault("stagger_enabled", False)
    schedule.setdefault("post_to_tiktok", True)
    schedule.setdefault("stagger_min_minutes", 60)
    schedule.setdefault("stagger_max_minutes", 240)

    name: str = str(schedule.get("name") or schedule_id)
    _fire_schedule(schedule)

    last_status: str = str(schedule.get("last_status") or "running")
    if last_status == "skipped":
        return {
            "status": "skipped",
            "message": f"Schedule '{name}' skipped — a batch is already running.",
        }
    if last_status == "failed":
        return {
            "status": "error",
            "message": (
                f"Schedule '{name}' failed to start: "
                f"{schedule.get('last_error', 'unknown error')}"
            ),
        }
    return {
        "status": "running",
        "message": f"Schedule '{name}' fired — batch generation started.",
    }


# ---------------------------------------------------------------------------
# Scheduler status
# ---------------------------------------------------------------------------


def get_scheduler_status() -> dict:
    """Return whether the scheduler daemon is active and the current time.

    Returns:
        Dict with ``running`` (bool) and ``now`` (ISO timestamp) keys.
    """
    return {
        "running": _scheduler_running.is_set(),
        "now": datetime.datetime.now().isoformat(),
    }

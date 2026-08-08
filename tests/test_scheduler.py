import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import gui.scheduler as scheduler
from gui.batch_engine import batch_state
from gui.scheduler import (
    _interval_slots,
    compute_next_fire,
    compute_stagger_delays,
    delete_schedule,
    get_schedule,
    get_scheduler_status,
    load_schedules,
    run_schedule_now,
    save_schedules,
    start_scheduler_thread,
    stop_scheduler_thread,
    upsert_schedule,
)


class _ScheduleFileTestCase(unittest.TestCase):
    """Base case that redirects the scheduler's storage file to a temp file.

    ``setUp`` swaps ``gui.scheduler.SCHEDULES_FILE`` to an isolated temp path
    so tests never read or clobber the real ``config/schedules.json``;
    ``tearDown`` restores the original path and stops any running scheduler
    daemon thread.
    """

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_schedules_file = scheduler.SCHEDULES_FILE
        scheduler.SCHEDULES_FILE = os.path.join(
            self._tmpdir.name, "config", "schedules.json"
        )
        save_schedules([])

    def tearDown(self):
        stop_scheduler_thread()
        scheduler.SCHEDULES_FILE = self._orig_schedules_file
        self._tmpdir.cleanup()


class TestSchedulePersistence(_ScheduleFileTestCase):
    """Tests for schedule CRUD persistence via config/schedules.json."""

    def test_roundtrip_save_load(self):
        """Save 2 schedules, load them back, verify the same data round-trips."""
        schedules = [
            {"id": "s1", "name": "Morning", "cadence": "daily", "times": ["08:00"]},
            {
                "id": "s2",
                "name": "Night",
                "cadence": "daily",
                "times": ["20:00", "21:00"],
            },
        ]
        save_schedules(schedules)
        self.assertEqual(load_schedules(), schedules)

    def test_get_schedule_found(self):
        """A schedule upserted by id is retrievable via get_schedule."""
        upsert_schedule(
            {"id": "abc123", "name": "Found", "cadence": "daily", "times": ["10:00"]}
        )
        sched = get_schedule("abc123")
        if sched is None:
            self.fail("expected schedule 'abc123' to be found")
        self.assertEqual(sched["name"], "Found")
        self.assertEqual(sched["id"], "abc123")

    def test_get_schedule_not_found(self):
        """get_schedule returns None for an unknown id."""
        self.assertIsNone(get_schedule("no-such-id"))

    def test_upsert_insert_generates_id(self):
        """Inserting a schedule without an id generates a 32-hex id and ISO created_at."""
        sched = upsert_schedule(
            {"name": "No ID", "cadence": "daily", "times": ["10:00"]}
        )
        self.assertRegex(sched["id"], r"^[0-9a-f]{32}$")
        self.assertIsNotNone(datetime.datetime.fromisoformat(sched["created_at"]))
        # The generated id must also be persisted, not just present in memory.
        persisted = get_schedule(sched["id"])
        if persisted is None:
            self.fail("expected the upserted schedule to be persisted")
        self.assertEqual(persisted["id"], sched["id"])

    def test_upsert_update_preserves_id(self):
        """Re-upserting with the same id replaces in place without duplicating."""
        first = upsert_schedule(
            {"id": "abc", "name": "One", "cadence": "daily", "times": ["09:00"]}
        )
        second = upsert_schedule(
            {"id": "abc", "name": "Two", "cadence": "daily", "times": ["11:00"]}
        )
        self.assertEqual(first["id"], "abc")
        self.assertEqual(second["id"], "abc")
        loaded = load_schedules()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["name"], "Two")
        # created_at is preserved across the update.
        self.assertEqual(loaded[0]["created_at"], first["created_at"])

    def test_delete_schedule_returns_true(self):
        """Deleting an existing schedule returns True and removes it."""
        sched = upsert_schedule(
            {"id": "del-me", "name": "Delete", "cadence": "daily", "times": ["09:00"]}
        )
        self.assertTrue(delete_schedule(sched["id"]))
        self.assertIsNone(get_schedule(sched["id"]))
        self.assertEqual(load_schedules(), [])

    def test_delete_nonexistent_returns_false(self):
        """Deleting a schedule that does not exist returns False."""
        self.assertFalse(delete_schedule("no-such-id"))

    def test_upsert_sorts_times(self):
        """upsert_schedule normalises times into chronological order."""
        sched = upsert_schedule(
            {
                "id": "sort-test",
                "name": "Unsorted",
                "cadence": "daily",
                "times": ["22:00", "06:00", "14:00", "08:00"],
            }
        )
        self.assertEqual(sched["times"], ["06:00", "08:00", "14:00", "22:00"])
        # The persisted copy must also be sorted.
        persisted = get_schedule("sort-test")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted["times"], ["06:00", "08:00", "14:00", "22:00"])

    def test_upsert_no_times_unchanged(self):
        """Interval-cadence schedules (no times key) are left untouched."""
        sched = upsert_schedule(
            {
                "id": "no-times",
                "name": "Interval",
                "cadence": "interval",
                "interval_hours": 3,
            }
        )
        self.assertNotIn("times", sched)
        persisted = get_schedule("no-times")
        self.assertIsNotNone(persisted)
        self.assertNotIn("times", persisted)


class TestStaggerDelays(unittest.TestCase):
    """Tests for compute_stagger_delays() cumulative per-job delays."""

    def test_empty_for_single_job(self):
        """A single job has no stagger delay map at all."""
        self.assertEqual(compute_stagger_delays(1, 1, 10), {})

    def test_empty_when_min_gt_max(self):
        """An inverted range produces an empty delay map."""
        self.assertEqual(compute_stagger_delays(5, 10, 5), {})

    def test_cumulative_increasing(self):
        """Delays accumulate, so each job's delay is strictly greater than the last."""
        delays = compute_stagger_delays(5, 1, 5)
        self.assertEqual(len(delays), 5)
        for i in range(2, 6):
            self.assertGreater(delays[i], delays[i - 1])
        # The full sequence is non-decreasing.
        values = [delays[i] for i in sorted(delays)]
        self.assertEqual(values, sorted(values))

    def test_first_job_zero(self):
        """Job 1 always posts immediately (zero cumulative delay)."""
        delays = compute_stagger_delays(5, 1, 5)
        self.assertEqual(delays[1], 0.0)

    def test_within_bounds(self):
        """Each gap between consecutive delays stays inside [min, max] seconds."""
        min_m, max_m = 2, 7
        delays = compute_stagger_delays(8, min_m, max_m)
        min_s, max_s = min_m * 60.0, max_m * 60.0
        for i in range(2, 9):
            gap = delays[i] - delays[i - 1]
            self.assertGreaterEqual(gap, min_s - 1e-9)
            self.assertLessEqual(gap, max_s + 1e-9)

    def test_returns_seconds_not_minutes(self):
        """Values are in seconds: a fixed 1-minute gap yields exactly 60.0 s."""
        delays = compute_stagger_delays(4, 1, 1)
        self.assertEqual(delays[2], 60.0)
        self.assertEqual(delays[4], 180.0)
        # A wider range also stays within [min*60, max*60] per-minute scaling.
        delays2 = compute_stagger_delays(10, 2, 3)
        self.assertGreaterEqual(delays2[10], 9 * 2 * 60)
        self.assertLessEqual(delays2[10], 9 * 3 * 60)


class TestNextFireComputation(unittest.TestCase):
    """Tests for compute_next_fire() across daily/weekly/interval cadences."""

    @staticmethod
    def _daily_schedule(**overrides):
        base = {
            "id": "test-daily",
            "cadence": "daily",
            "times": ["23:59"],
            "jitter_minutes": 0,
        }
        base.update(overrides)
        return base

    def test_daily_future_today(self):
        """A future time today fires today (23:59 + 0 jitter)."""
        schedule = self._daily_schedule(times=["23:59"])
        now = datetime.datetime(2026, 1, 15, 12, 0, 0)
        expected = datetime.datetime(2026, 1, 15, 23, 59, 0)
        self.assertEqual(compute_next_fire(schedule, now), expected)

    def test_daily_all_passed_today(self):
        """When every time today has passed, the next fire is tomorrow."""
        schedule = self._daily_schedule(times=["01:00"])
        now = datetime.datetime(2026, 1, 15, 12, 0, 0)
        expected = datetime.datetime(2026, 1, 16, 1, 0, 0)
        self.assertEqual(compute_next_fire(schedule, now), expected)

    def test_weekly_respects_days(self):
        """From a Thursday, a Wednesday-only schedule fires next Wednesday."""
        schedule = {
            "id": "test-weekly",
            "cadence": "weekly",
            "days": [3],  # Wednesday (1=Mon .. 7=Sun)
            "times": ["12:00"],
            "jitter_minutes": 0,
        }
        now = datetime.datetime(2026, 1, 15, 12, 0, 0)  # Thursday
        result = compute_next_fire(schedule, now)
        self.assertEqual(result, datetime.datetime(2026, 1, 21, 12, 0, 0))
        if result is None:
            self.fail("expected a next-fire datetime for the weekly schedule")
        self.assertEqual(result.weekday(), 2)  # Wednesday

    def test_weekly_on_correct_day(self):
        """When today matches a scheduled day and the slot is still ahead, fire today."""
        schedule = {
            "id": "test-weekly",
            "cadence": "weekly",
            "days": [3],
            "times": ["12:00"],
            "jitter_minutes": 0,
        }
        now = datetime.datetime(2026, 1, 21, 8, 0, 0)  # Wednesday, before the slot
        expected = datetime.datetime(2026, 1, 21, 12, 0, 0)
        self.assertEqual(compute_next_fire(schedule, now), expected)

    def test_interval_within_window(self):
        """Interval cadence picks the first slot of the day (08:00 + 0 jitter)."""
        schedule = {
            "id": "test-interval",
            "cadence": "interval",
            "interval_hours": 3,
            "interval_start": "08:00",
            "interval_end": "20:00",
            "jitter_minutes": 0,
        }
        now = datetime.datetime(2026, 1, 15, 6, 0, 0)
        expected = datetime.datetime(2026, 1, 15, 8, 0, 0)
        self.assertEqual(compute_next_fire(schedule, now), expected)

    def test_interval_end_exclusive(self):
        """The interval end is exclusive: 08:00->14:00 at 3h yields 08:00, 11:00 only."""
        schedule = {
            "id": "test-interval",
            "cadence": "interval",
            "interval_hours": 3,
            "interval_start": "08:00",
            "interval_end": "14:00",
            "jitter_minutes": 0,
        }
        slots = _interval_slots(schedule, datetime.date(2026, 1, 15))
        self.assertEqual(
            slots,
            [
                datetime.datetime(2026, 1, 15, 8, 0, 0),
                datetime.datetime(2026, 1, 15, 11, 0, 0),
            ],
        )

    def test_interval_all_passed(self):
        """When all of today's slots have passed, the next fire is tomorrow's first slot."""
        schedule = {
            "id": "test-interval",
            "cadence": "interval",
            "interval_hours": 3,
            "interval_start": "08:00",
            "interval_end": "20:00",
            "jitter_minutes": 0,
        }
        now = datetime.datetime(2026, 1, 15, 21, 0, 0)
        expected = datetime.datetime(2026, 1, 16, 8, 0, 0)
        self.assertEqual(compute_next_fire(schedule, now), expected)

    def test_empty_times_returns_none(self):
        """A schedule with no times has no next fire (daily and weekly)."""
        schedule = self._daily_schedule(times=[])
        now = datetime.datetime(2026, 1, 15, 12, 0, 0)
        self.assertIsNone(compute_next_fire(schedule, now))
        weekly = {"id": "test-weekly", "cadence": "weekly", "days": [], "times": ["12:00"]}
        self.assertIsNone(compute_next_fire(weekly, now))

    def test_deterministic(self):
        """Identical inputs produce identical next-fire times, including jitter."""
        schedule = {
            "id": "test-deterministic",
            "cadence": "daily",
            "times": ["09:15", "14:30"],
            "jitter_minutes": 10,
        }
        now = datetime.datetime(2026, 1, 15, 8, 0, 0)
        self.assertEqual(
            compute_next_fire(schedule, now),
            compute_next_fire(schedule, now),
        )


class TestSchedulerStatusAndLifecycle(_ScheduleFileTestCase):
    """Tests for scheduler daemon start/stop and status reporting."""

    def test_initial_status_not_running(self):
        """Before start, get_scheduler_status reports running=False."""
        stop_scheduler_thread()
        status = get_scheduler_status()
        self.assertFalse(status["running"])
        self.assertIn("now", status)

    def test_start_stop_lifecycle(self):
        """Start flips running to True; stop flips it back to False."""
        start_scheduler_thread()
        try:
            self.assertTrue(get_scheduler_status()["running"])
        finally:
            stop_scheduler_thread()
        self.assertFalse(get_scheduler_status()["running"])

    def test_start_idempotent(self):
        """Calling start twice does not raise or corrupt state."""
        start_scheduler_thread()
        start_scheduler_thread()
        try:
            self.assertTrue(get_scheduler_status()["running"])
        finally:
            stop_scheduler_thread()


class TestRunScheduleNow(_ScheduleFileTestCase):
    """Tests for the manual run_schedule_now() helper."""

    def setUp(self):
        super().setUp()
        self._orig_in_progress = batch_state["in_progress"]

    def tearDown(self):
        batch_state["in_progress"] = self._orig_in_progress
        super().tearDown()

    def test_run_nonexistent_returns_error(self):
        """Firing a missing schedule id returns a status='error' dict."""
        result = run_schedule_now("does-not-exist")
        self.assertEqual(result["status"], "error")

    def test_run_in_progress_returns_skipped(self):
        """Firing while a batch is running returns status='skipped'."""
        sched = upsert_schedule(
            {"name": "skip-me", "cadence": "daily", "times": ["09:00"]}
        )
        batch_state["in_progress"] = True
        try:
            result = run_schedule_now(sched["id"])
        finally:
            batch_state["in_progress"] = self._orig_in_progress
        self.assertEqual(result["status"], "skipped")

    def test_skip_advances_next_run_past_current_slot(self):
        """When a schedule is skipped, next_run advances to the next slot.

        Regression for the grace-window spin bug: previously compute_next_fire
        would return the same upcoming slot (still > now but within grace),
        causing a retry loop.  Now it must advance past the skipped slot.
        """
        sched = upsert_schedule({
            "name": "skip-advance-test",
            "cadence": "daily",
            "times": ["09:00", "15:00"],
            "jitter_minutes": 0,
        })
        # Pin next_run to tomorrow's 09:00 so the test is date-independent.
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        target = datetime.datetime.combine(tomorrow, datetime.time(9, 0))
        sched["next_run"] = target.isoformat()
        upsert_schedule(sched)

        batch_state["in_progress"] = True
        try:
            result = run_schedule_now(sched["id"])
        finally:
            batch_state["in_progress"] = self._orig_in_progress

        self.assertEqual(result["status"], "skipped")

        # After the skip the schedule must be pointing at tomorrow's
        # 15:00 slot, *not* the original 09:00 slot.
        updated = get_schedule(sched["id"])
        if updated is None:
            self.fail("schedule not found after skip")
        new_next = datetime.datetime.fromisoformat(updated["next_run"])
        expected = datetime.datetime.combine(tomorrow, datetime.time(15, 0))
        self.assertEqual(new_next, expected)


if __name__ == "__main__":
    unittest.main()

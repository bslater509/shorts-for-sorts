import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gui.batch_engine import _batch_state_lock, batch_state
from gui.routers.admin import router as admin_router
from gui.routers.batch import build_batch_status
from gui.routers.batch import router as batch_router
from gui.routers.settings import router as settings_router

app = FastAPI()
app.include_router(admin_router)
app.include_router(settings_router)
app.include_router(batch_router)
client = TestClient(app)


# ===================================================================
# Admin routes
# ===================================================================
class TestAdminHealthRoute(unittest.TestCase):
    """Tests for GET /api/health."""

    def test_health_returns_ok(self):
        """GET /api/health should return 200 with {'status': 'ok'}."""
        resp = client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})


class TestAdminBatchStatsRoute(unittest.TestCase):
    """Tests for GET /api/batch/stats."""

    @patch("gui.routers.admin.BATCH_STATS_FILE", "/tmp/nonexistent_batch_stats_test.json")
    def test_batch_stats_default(self):
        """GET /api/batch/stats without a stats file should return default values."""
        resp = client.get("/api/batch/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("phase_ratios", data)
        self.assertIn("sample_count", data)
        self.assertIn("avg_llm_duration", data)
        self.assertIn("avg_video_duration", data)
        self.assertIn("per_job_stats", data)
        # Defaults
        self.assertEqual(data["sample_count"], 0)
        self.assertEqual(data["per_job_stats"], [])
        self.assertIsNone(data["avg_llm_duration"])
        self.assertIsNone(data["avg_video_duration"])
        # phase_ratios should be a non-empty dict
        self.assertIsInstance(data["phase_ratios"], dict)
        self.assertGreater(len(data["phase_ratios"]), 0)


class TestAdminBatchStatsResetRoute(unittest.TestCase):
    """Tests for POST /api/batch/stats/reset."""

    @patch("gui.batch_persistence.BATCH_STATS_FILE", "/tmp/reset_batch_stats_test.json")
    def test_reset_clears_stats(self):
        """Reset should wipe dirty stats to defaults, on disk and in memory."""
        import json

        dirty = {
            "phase_ratios": {"LLM": 0.9, "Voice": 0.05, "Transcribe": 0.02, "Render": 0.03},
            "sample_count": 42,
            "avg_llm_duration": 12.3,
            "avg_video_duration": 45.6,
            "phase_rates": {"llm_rate": 1.5},
            "per_job_stats": [{"word_count": 100, "llm_duration": 12.3}],
        }
        with open("/tmp/reset_batch_stats_test.json", "w") as f:
            json.dump(dirty, f)

        with _batch_state_lock:
            batch_state["_per_job_stats"] = [{"word_count": 100}]

        resp = client.post("/api/batch/stats/reset")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["sample_count"], 0)
        self.assertEqual(data["per_job_stats"], [])
        self.assertIsNone(data["avg_llm_duration"])
        self.assertIsNone(data["avg_video_duration"])
        self.assertEqual(data["phase_rates"], {})

        with open("/tmp/reset_batch_stats_test.json") as f:
            saved = json.load(f)
        self.assertEqual(saved["sample_count"], 0)
        self.assertEqual(saved["per_job_stats"], [])
        self.assertEqual(saved["phase_rates"], {})

        with _batch_state_lock:
            self.assertEqual(batch_state["_per_job_stats"], [])

    @patch("gui.batch_persistence.BATCH_STATS_FILE", "/tmp/reset_batch_stats_test.json")
    def test_reset_refuses_during_batch(self):
        """Reset should return 409 while a batch is in progress."""
        with _batch_state_lock:
            batch_state["in_progress"] = True
        try:
            resp = client.post("/api/batch/stats/reset")
            self.assertEqual(resp.status_code, 409)
        finally:
            with _batch_state_lock:
                batch_state["in_progress"] = False


# ===================================================================
# Settings routes
# ===================================================================
class TestSettingsVoicesRoute(unittest.TestCase):
    """Tests for GET /api/voices."""

    def test_voices_returns_list_of_dicts(self):
        """GET /api/voices should return 200 with name/value entries."""
        resp = client.get("/api/voices")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        for entry in data:
            self.assertIn("name", entry)
            self.assertIn("value", entry)
            self.assertIsInstance(entry["name"], str)
            self.assertIsInstance(entry["value"], str)
            self.assertGreater(len(entry["name"]), 0)
            self.assertGreater(len(entry["value"]), 0)


# ===================================================================
# Batch (prompts) routes
# ===================================================================
class TestBatchPromptsRoute(unittest.TestCase):
    """Tests for GET /api/prompts."""

    @patch("gui.config.PROMPTS_FILE", "/tmp/nonexistent_prompts_test.json")
    def test_prompts_returns_dict(self):
        """GET /api/prompts should return 200 with a dict of prompt templates."""
        resp = client.get("/api/prompts")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, dict)
        self.assertGreater(len(data), 0)
        # Verify structure: keys are strings, values are strings
        for key, value in data.items():
            self.assertIsInstance(key, str)
            self.assertIsInstance(value, str)
            self.assertGreater(len(key), 0)


# ===================================================================
# build_batch_status system stats
# ===================================================================
class TestBuildBatchStatusSystemStats(unittest.TestCase):
    """Tests for the system-resource fields returned by build_batch_status."""

    def _clear_net_counters(self):
        """Reset the stored network-counter snapshot for order-independent tests."""
        with _batch_state_lock:
            batch_state.pop("_net_counters", None)
            batch_state.pop("_net_time", None)

    @patch("gui.routers.batch.os.getloadavg", return_value=(1.5, 1.2, 1.0))
    @patch("gui.routers.batch.psutil.cpu_percent", return_value=42.0)
    @patch("gui.routers.batch.psutil.virtual_memory")
    @patch("gui.routers.batch.psutil.disk_usage")
    @patch("gui.routers.batch.psutil.net_io_counters")
    @patch("gui.routers.batch.psutil.swap_memory")
    @patch("gui.routers.batch.psutil.cpu_count", return_value=8)
    @patch("gui.routers.batch.psutil.Process")
    def test_system_stats_fields_populated(
        self,
        mock_proc,
        mock_cpu_count,
        mock_swap,
        mock_net,
        mock_disk,
        mock_vm,
        mock_cpu_percent,
        mock_load,
    ):
        """The status payload includes all new system stats with sane values."""
        self._clear_net_counters()
        mock_vm.return_value.percent = 55.5
        mock_disk.return_value.percent = 33.3
        mock_net.return_value.bytes_recv = 100 * 1024
        mock_net.return_value.bytes_sent = 50 * 1024
        mock_swap.return_value.percent = 12.3
        mock_proc.return_value.memory_info.return_value.rss = 256 * 1024 * 1024

        data = build_batch_status()

        self.assertEqual(data["cpu_percent"], 42.0)
        self.assertEqual(data["memory_percent"], 55.5)
        self.assertEqual(data["disk_percent"], 33.3)
        self.assertEqual(data["rss_mb"], 256.0)
        self.assertEqual(data["swap_percent"], 12.3)
        self.assertEqual(data["load_avg"], 1.5)
        self.assertEqual(data["cpu_count"], 8)
        # First sample has no prior counters -> zero throughput.
        self.assertEqual(data["net_recv_kbs"], 0.0)
        self.assertEqual(data["net_sent_kbs"], 0.0)

    @patch("gui.routers.batch.os.getloadavg", return_value=(0.5, 0.4, 0.3))
    @patch("gui.routers.batch.time.time", return_value=100.0)
    @patch("gui.routers.batch.psutil.cpu_percent", return_value=10.0)
    @patch("gui.routers.batch.psutil.virtual_memory")
    @patch("gui.routers.batch.psutil.disk_usage")
    @patch("gui.routers.batch.psutil.net_io_counters")
    @patch("gui.routers.batch.psutil.swap_memory")
    @patch("gui.routers.batch.psutil.cpu_count", return_value=4)
    @patch("gui.routers.batch.psutil.Process")
    def test_net_io_rate_uses_previous_counters(
        self,
        mock_proc,
        mock_cpu_count,
        mock_swap,
        mock_net,
        mock_disk,
        mock_vm,
        mock_cpu_percent,
        mock_time,
        mock_load,
    ):
        """Network rates are derived from the delta vs. the stored counters."""
        mock_vm.return_value.percent = 10.0
        mock_disk.return_value.percent = 10.0
        mock_swap.return_value.percent = 0.0
        mock_proc.return_value.memory_info.return_value.rss = 0
        # Previous snapshot: 10 seconds ago, zero bytes transferred.
        with _batch_state_lock:
            batch_state["_net_counters"] = (0, 0)
            batch_state["_net_time"] = 90.0
        mock_net.return_value.bytes_recv = 10240 * 1024  # 10 MB
        mock_net.return_value.bytes_sent = 2048 * 1024   # 2 MB

        data = build_batch_status()

        # 10 MB / 10 s = 1024 KB/s ; 2 MB / 10 s = 204.8 KB/s
        self.assertAlmostEqual(data["net_recv_kbs"], 1024.0, places=1)
        self.assertAlmostEqual(data["net_sent_kbs"], 204.8, places=1)

    @patch("gui.routers.batch.os.getloadavg", side_effect=OSError("unsupported"))
    @patch("gui.routers.batch.psutil.cpu_percent", side_effect=Exception("unsupported"))
    @patch("gui.routers.batch.psutil.virtual_memory", side_effect=Exception("unsupported"))
    @patch("gui.routers.batch.psutil.disk_usage", side_effect=Exception("unsupported"))
    @patch("gui.routers.batch.psutil.net_io_counters", side_effect=Exception("unsupported"))
    @patch("gui.routers.batch.psutil.swap_memory", side_effect=Exception("unsupported"))
    @patch("gui.routers.batch.psutil.cpu_count", side_effect=Exception("unsupported"))
    @patch("gui.routers.batch.psutil.Process", side_effect=Exception("unsupported"))
    def test_system_stats_degrades_on_unsupported_platform(
        self,
        mock_proc,
        mock_cpu_count,
        mock_swap,
        mock_net,
        mock_disk,
        mock_vm,
        mock_cpu_percent,
        mock_load,
    ):
        """Unsupported psutil/os APIs must not crash the status build."""
        data = build_batch_status()

        self.assertEqual(data["cpu_percent"], 0.0)
        self.assertEqual(data["memory_percent"], 0.0)
        self.assertEqual(data["disk_percent"], 0.0)
        self.assertEqual(data["rss_mb"], 0.0)
        self.assertEqual(data["swap_percent"], 0.0)
        self.assertEqual(data["load_avg"], 0.0)
        self.assertEqual(data["cpu_count"], 1)
        self.assertEqual(data["net_recv_kbs"], 0.0)
        self.assertEqual(data["net_sent_kbs"], 0.0)


if __name__ == "__main__":
    unittest.main()

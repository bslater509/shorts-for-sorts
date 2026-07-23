import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gui.routers.admin import router as admin_router
from gui.routers.settings import router as settings_router
from gui.routers.batch import router as batch_router

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


if __name__ == "__main__":
    unittest.main()

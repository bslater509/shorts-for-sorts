"""Tests for background thumbnail cache module and related routes."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gui.routers.assets import router as assets_router

app = FastAPI()
app.include_router(assets_router)
client = TestClient(app)


class ThumbnailCacheTestCase(unittest.TestCase):
    """Tests for gui.thumbnail_cache module functions."""

    @classmethod
    def setUpClass(cls):
        # Ensure the module is importable *before* individual patches
        pass

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="thumb_cache_test_")
        self.output_dir = os.path.join(self.tmpdir, "output")
        self.thumb_dir = os.path.join(self.tmpdir, "thumbnails")
        self.videos_dir = os.path.join(self.tmpdir, "videos")
        self.local_thumb_dir = os.path.join(self.tmpdir, "cache_thumbnails", "videos")
        for d in (
            self.output_dir,
            self.thumb_dir,
            self.videos_dir,
            self.local_thumb_dir,
        ):
            os.makedirs(d, exist_ok=True)

        # Patch dirs used by thumbnail_cache and assets
        self.patches = [
            patch("gui.thumbnail_cache.OUTPUT_DIR", self.output_dir),
            patch("gui.thumbnail_cache.THUMBNAIL_DIR", self.thumb_dir),
            patch("gui.thumbnail_cache.VIDEOS_DIR", self.videos_dir),
            patch("gui.thumbnail_cache.LOCAL_VIDEO_THUMBNAIL_DIR", self.local_thumb_dir),
            patch("gui.routers.assets.OUTPUT_DIR", self.output_dir),
            patch("gui.routers.assets.THUMBNAIL_DIR", self.thumb_dir),
            patch("gui.routers.assets.VIDEOS_DIR", self.videos_dir),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_video(self, name: str, directory: str | None = None) -> str:
        """Create a small fake video file."""
        d = directory or self.videos_dir
        fp = os.path.join(d, name)
        with open(fp, "wb") as f:
            f.write(b"fake video content")
        return fp

    def _make_file(self, path: str, content: bytes = b"jpeg") -> None:
        """Write a file at the given path."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)

    # ------------------------------------------------------------------
    # Cache key stability & invalidation
    # ------------------------------------------------------------------

    def test_key_is_deterministic(self):
        """Same path, size, mtime → same key."""
        from gui.thumbnail_cache import _stable_key, local_thumb_path

        fp = self._make_video("a.mp4")
        key1 = _stable_key(fp)
        key2 = _stable_key(fp)
        self.assertEqual(key1, key2)
        self.assertGreater(len(key1), 0)
        self.assertFalse(key1.endswith(".jpg"))

        tp = local_thumb_path(fp)
        self.assertTrue(tp.endswith(key1 + ".jpg"))
        self.assertTrue(tp.startswith(self.local_thumb_dir))

    def test_key_changes_when_size_changes(self):
        """Modifying file content → size change → different key."""
        from gui.thumbnail_cache import _stable_key

        fp = self._make_video("a.mp4")
        key1 = _stable_key(fp)
        # Append to file to change size
        import time

        time.sleep(0.01)  # ensure mtime ticks
        with open(fp, "ab") as f:
            f.write(b" more content")
        key2 = _stable_key(fp)
        self.assertNotEqual(key1, key2)

    def test_key_changes_when_mtime_changes(self):
        """Touching mtime → different key."""
        from gui.thumbnail_cache import _stable_key

        fp = self._make_video("a.mp4")
        key1 = _stable_key(fp)
        os.utime(fp, (os.stat(fp).st_atime, os.stat(fp).st_mtime + 10))
        key2 = _stable_key(fp)
        self.assertNotEqual(key1, key2)

    # ------------------------------------------------------------------
    # Enqueue deduplication
    # ------------------------------------------------------------------

    def test_enqueue_dedupe_same_thumb_path(self):
        """Enqueuing the same video+thumb twice only adds one queue item."""
        from gui.thumbnail_cache import enqueue, _queue, _in_progress, _in_progress_lock, stop_thumbnail_worker, _WORKER_POOL_SIZE
        # Start workers to drain the queue
        import gui.thumbnail_cache as tc

        tc._workers_started = False  # allow start in test
        tc.start_thumbnail_worker()
        # Drain any existing items
        while not _queue.empty():
            try:
                _queue.get_nowait()
            except Exception:
                break

        fp = self._make_video("a.mp4")
        thumb = os.path.join(self.thumb_dir, "a.jpg")
        enqueue(fp, thumb)
        self.assertEqual(_queue.qsize(), 1)
        with _in_progress_lock:
            self.assertIn(thumb, _in_progress)

        # Second enqueue with same thumb — no-op
        enqueue(fp, thumb)
        self.assertEqual(_queue.qsize(), 1)

        # Clean up: stop workers (sends sentinels to drain + exit)
        stop_thumbnail_worker()

    # ------------------------------------------------------------------
    # Precache scans
    # ------------------------------------------------------------------

    @patch("gui.thumbnail_cache.generate_video_thumbnail", return_value=True)
    def test_precache_output_enqueues_missing(self, _mock_gen):
        """precache_all enqueues output videos with missing thumbs."""
        from gui.thumbnail_cache import precache_all, _queue, _in_progress, _in_progress_lock

        # Don't start real workers — they'd consume items from the queue.
        # Just clear any residual state.
        while not _queue.empty():
            try:
                _queue.get_nowait()
            except Exception:
                break
        with _in_progress_lock:
            _in_progress.clear()

        self._make_video("has_thumb.mp4", self.output_dir)
        self._make_video("no_thumb.mp4", self.output_dir)
        # Pre-create one thumb
        self._make_file(os.path.join(self.thumb_dir, "has_thumb.jpg"))
        # no_thumb has no .jpg

        precache_all()
        self.assertGreaterEqual(_queue.qsize(), 1)
        # Verify the right one is queued
        items: list[tuple[str, str]] = []
        while not _queue.empty():
            try:
                item = _queue.get_nowait()
                if item is not None:
                    items.append(item)
            except Exception:
                break
        thumb_paths = {t[1] for t in items}
        self.assertIn(
            os.path.join(self.thumb_dir, "no_thumb.jpg"), thumb_paths
        )
        self.assertNotIn(
            os.path.join(self.thumb_dir, "has_thumb.jpg"), thumb_paths
        )

    @patch("gui.thumbnail_cache.generate_video_thumbnail", return_value=True)
    def test_precache_local_enqueues_missing(self, _mock_gen):
        """precache_all enqueues local videos with missing cached thumbs."""
        from gui.thumbnail_cache import precache_all, _queue, local_thumb_path, _in_progress, _in_progress_lock

        # Don't start real workers — they'd consume items from the queue.
        while not _queue.empty():
            try:
                _queue.get_nowait()
            except Exception:
                break
        with _in_progress_lock:
            _in_progress.clear()

        fp = self._make_video("video.mp4")
        tp = local_thumb_path(fp)
        self.assertFalse(os.path.exists(tp))

        precache_all()
        items: list[tuple[str, str]] = []
        while not _queue.empty():
            try:
                item = _queue.get_nowait()
                if item is not None:
                    items.append(item)
            except Exception:
                break
        thumb_paths = {t[1] for t in items}
        self.assertIn(tp, thumb_paths)

    # ------------------------------------------------------------------
    # Pruning
    # ------------------------------------------------------------------

    def test_prune_removes_stale_local_thumbs(self):
        """Cached thumbs for gone videos are cleaned up."""
        from gui.thumbnail_cache import _prune_local_thumbs, local_thumb_path

        fp = self._make_video("live.mp4")
        tp_live = local_thumb_path(fp)
        self._make_file(tp_live)

        # Create a stale thumb with a known key (no matching video)
        stale_tp = os.path.join(self.local_thumb_dir, "deadbeefdeadbeef.jpg")
        self._make_file(stale_tp)

        _prune_local_thumbs()
        self.assertTrue(os.path.exists(tp_live))
        self.assertFalse(os.path.exists(stale_tp))

    # ------------------------------------------------------------------
    # Route: local video thumbnail
    # ------------------------------------------------------------------

    def test_local_thumb_route_404_when_video_missing(self):
        """/api/assets/videos/thumbnail/nonexistent.mp4 → 404."""
        resp = client.get("/api/assets/videos/thumbnail/nonexistent.mp4")
        self.assertEqual(resp.status_code, 404)

    def test_local_thumb_route_404_when_thumb_missing(self):
        """Video exists but no cached thumb → 404 + enqueue."""
        self._make_video("fresh.mp4")
        # No cached thumb
        resp = client.get("/api/assets/videos/thumbnail/fresh.mp4")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Thumbnail not yet generated", resp.json()["detail"])

    def test_local_thumb_route_serves_cached(self):
        """Video + cached thumb → 200 JPEG."""
        from gui.thumbnail_cache import local_thumb_path

        fp = self._make_video("ready.mp4")
        tp = local_thumb_path(fp)
        self._make_file(tp, b"\xff\xd8\xff\xe0 fake jpeg")

        resp = client.get("/api/assets/videos/thumbnail/ready.mp4")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("image/jpeg", resp.headers["content-type"])

    # ------------------------------------------------------------------
    # Route: list_assets_videos includes thumbnail URL
    # ------------------------------------------------------------------

    def test_list_assets_videos_includes_thumbnail(self):
        """GET /api/assets/videos returns a thumbnail URL with cache-bust."""
        self._make_video("test.mp4")
        resp = client.get("/api/assets/videos")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(len(data), 1)
        self.assertIn("thumbnail", data[0])
        self.assertTrue(data[0]["thumbnail"].startswith("/api/assets/videos/thumbnail/"))
        self.assertIn("?v=", data[0]["thumbnail"])

    # ------------------------------------------------------------------
    # Route: gallery thumbnail (changed to background-only)
    # ------------------------------------------------------------------

    def test_gallery_thumb_route_404_when_missing(self):
        """Gallery thumb missing → 404 + enqueue (no sync generation)."""
        self._make_video("vid.mp4", self.output_dir)
        # No thumb
        resp = client.get("/api/gallery/thumbnail/vid.jpg")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Thumbnail not yet generated", resp.json()["detail"])

    def test_gallery_thumb_route_serves_cached(self):
        """Gallery thumb exists → 200 JPEG."""
        self._make_video("done.mp4", self.output_dir)
        thumb = os.path.join(self.thumb_dir, "done.jpg")
        self._make_file(thumb, b"\xff\xd8\xff\xe0 fake jpeg")

        resp = client.get("/api/gallery/thumbnail/done.jpg")
        self.assertEqual(resp.status_code, 200)

    def test_gallery_thumb_route_404_no_matching_video(self):
        """No video matching the requested thumb base → 404 'not found'."""
        resp = client.get("/api/gallery/thumbnail/orphan.jpg")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Thumbnail not found", resp.json()["detail"])


if __name__ == "__main__":
    unittest.main()

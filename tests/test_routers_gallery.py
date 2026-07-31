import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gui.routers.assets import (
    _backfill_duration,
    _probe_duration_cached,
    _prune_stale_thumbnails,
)
from gui.routers.assets import (
    router as assets_router,
)
from gui.video_compiler import _save_metadata_and_thumbnail

app = FastAPI()
app.include_router(assets_router)
client = TestClient(app)


class GalleryTestCase(unittest.TestCase):
    """Shared fixture: temp output + thumbnail dirs patched into the assets router."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="gallery_test_")
        self.output_dir = os.path.join(self.tmpdir, "output")
        self.thumb_dir = os.path.join(self.tmpdir, "thumbnails")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.thumb_dir, exist_ok=True)
        self.output_patcher = patch("gui.routers.assets.OUTPUT_DIR", self.output_dir)
        self.thumb_patcher = patch("gui.routers.assets.THUMBNAIL_DIR", self.thumb_dir)
        self.output_patcher.start()
        self.thumb_patcher.start()
        _probe_duration_cached.cache_clear()

    def tearDown(self):
        _probe_duration_cached.cache_clear()
        self.thumb_patcher.stop()
        self.output_patcher.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_video(self, name: str) -> str:
        """Create a (fake) video file in the temp output dir."""
        fp = os.path.join(self.output_dir, name)
        with open(fp, "wb") as f:
            f.write(b"fake video content")
        return fp

    def _write_txt(self, name: str, content: str) -> str:
        """Write a metadata sidecar for a video basename."""
        fp = os.path.join(self.output_dir, os.path.splitext(name)[0] + ".txt")
        with open(fp, "w", encoding="utf-8") as f:
            f.write(content)
        return fp

    def _make_thumbnail(self, name: str) -> str:
        """Create a thumbnail jpg in the temp thumbnail dir."""
        fp = os.path.join(self.thumb_dir, name)
        with open(fp, "wb") as f:
            f.write(b"fake thumbnail")
        return fp


class TestListGalleryVideos(GalleryTestCase):
    def test_duration_read_from_sidecar_without_probe(self):
        """Duration comes from the ``.txt`` sidecar; no ffprobe round-trip."""
        self._make_video("a.mp4")
        self._write_txt(
            "a.mp4",
            "My Title\n#tag\nDuration: 42.50\n\nScript:\nhello\n",
        )
        with patch(
            "gui.routers.assets.get_video_info",
            side_effect=AssertionError("should not probe"),
        ):
            resp = client.get("/api/gallery")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["duration"], 42.5)
        self.assertEqual(data[0]["title"], "My Title")
        self.assertEqual(data[0]["hashtags"], "#tag")

    def test_duration_regex_is_case_insensitive(self):
        """``duration: 12.34`` (lowercase) is still parsed."""
        self._make_video("a.mp4")
        self._write_txt("a.mp4", "Title\n#tag\nduration: 12.34\n\nScript:\nhello\n")
        with patch(
            "gui.routers.assets.get_video_info",
            side_effect=AssertionError("should not probe"),
        ):
            resp = client.get("/api/gallery")
        self.assertEqual(resp.json()[0]["duration"], 12.34)

    def test_duration_probed_and_backfilled_when_missing(self):
        """Missing sidecar duration is probed, returned, and backfilled."""
        self._make_video("a.mp4")
        self._write_txt("a.mp4", "Title\n#tag\n\nScript:\nhello\n")
        with patch(
            "gui.routers.assets.get_video_info",
            return_value={"width": 720, "height": 1280, "duration": 7.25},
        ):
            resp = client.get("/api/gallery")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["duration"], 7.25)
        # Backfill: the sidecar now carries the duration for future loads.
        txt_path = os.path.join(self.output_dir, "a.txt")
        with open(txt_path, encoding="utf-8") as f:
            self.assertIn("Duration: 7.25", f.read())

    def test_duration_stays_none_when_probe_fails(self):
        """A failed probe yields ``duration: null`` without backfill."""
        self._make_video("a.mp4")
        self._write_txt("a.mp4", "Title\n#tag\n")
        with patch(
            "gui.routers.assets.get_video_info",
            return_value={"width": 0, "height": 0, "duration": 0.0},
        ):
            resp = client.get("/api/gallery")
        data = resp.json()
        self.assertEqual(data[0]["duration"], None)
        txt_path = os.path.join(self.output_dir, "a.txt")
        with open(txt_path, encoding="utf-8") as f:
            self.assertNotIn("Duration:", f.read())

    def test_old_format_hashtags_still_parsed(self):
        """Legacy ``Hashtags:`` sidecars keep working alongside Duration."""
        self._make_video("a.mp4")
        self._write_txt("a.mp4", "Hashtags: #a #b\nDuration: 5.00\n\nScript:\nhello\n")
        with patch(
            "gui.routers.assets.get_video_info",
            side_effect=AssertionError("should not probe"),
        ):
            resp = client.get("/api/gallery")
        data = resp.json()
        self.assertEqual(data[0]["hashtags"], "#a #b")
        self.assertEqual(data[0]["duration"], 5.0)


class TestProbeDurationCached(GalleryTestCase):
    def test_returns_duration_from_info(self):
        """The cached probe delegates to ``get_video_info`` and returns duration."""
        fp = self._make_video("a.mp4")
        with patch(
            "gui.routers.assets.get_video_info",
            return_value={"width": 1, "height": 1, "duration": 9.5},
        ) as mock_info:
            result = _probe_duration_cached(fp, 10, 100.0)
            result2 = _probe_duration_cached(fp, 10, 100.0)
        self.assertEqual(result, 9.5)
        self.assertEqual(result2, 9.5)
        self.assertEqual(mock_info.call_count, 1)

    def test_returns_none_on_error(self):
        """A probing exception surfaces as ``None``."""
        fp = self._make_video("a.mp4")
        with patch(
            "gui.routers.assets.get_video_info",
            side_effect=RuntimeError("ffprobe unavailable"),
        ):
            self.assertIsNone(_probe_duration_cached(fp, 10, 100.0))


class TestPruneStaleThumbnails(GalleryTestCase):
    def test_removes_thumbnails_without_matching_video(self):
        """Thumbnails whose video is gone are deleted; live ones are kept."""
        self._make_video("keep.mp4")
        self._make_thumbnail("keep.jpg")
        self._make_thumbnail("stale.jpg")
        _prune_stale_thumbnails()
        self.assertTrue(os.path.exists(os.path.join(self.thumb_dir, "keep.jpg")))
        self.assertFalse(os.path.exists(os.path.join(self.thumb_dir, "stale.jpg")))

    def test_prune_runs_at_gallery_start(self):
        """GET /api/gallery prunes stale thumbnails automatically."""
        self._make_video("keep.mp4")
        self._make_thumbnail("keep.jpg")
        self._make_thumbnail("orphan.jpg")
        client.get("/api/gallery")
        self.assertFalse(os.path.exists(os.path.join(self.thumb_dir, "orphan.jpg")))
        self.assertTrue(os.path.exists(os.path.join(self.thumb_dir, "keep.jpg")))


class TestDeleteAllGalleryVideos(GalleryTestCase):
    def test_clears_output_and_thumbnails(self):
        """DELETE /api/gallery removes videos, sidecars, and thumbnails."""
        self._make_video("a.mp4")
        self._write_txt("a.mp4", "Title\n#tag\n")
        self._make_thumbnail("a.jpg")
        resp = client.delete("/api/gallery")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(os.listdir(self.output_dir), [])
        self.assertEqual(os.listdir(self.thumb_dir), [])

    def test_clears_thumbnails_only(self):
        """Even without output files, thumbnails are still cleared."""
        self._make_thumbnail("a.jpg")
        client.delete("/api/gallery")
        self.assertEqual(os.listdir(self.thumb_dir), [])


class TestBackfillDuration(GalleryTestCase):
    def test_appends_duration_to_existing_sidecar(self):
        """``_backfill_duration`` appends the Duration line to the sidecar."""
        self._make_video("a.mp4")
        self._write_txt("a.mp4", "Title\n#tag\n")
        _backfill_duration("a.mp4", 3.14159)
        with open(os.path.join(self.output_dir, "a.txt"), encoding="utf-8") as f:
            self.assertIn("Duration: 3.14", f.read())

    def test_noop_when_sidecar_missing(self):
        """No crash when there is no sidecar to backfill."""
        self._make_video("a.mp4")
        _backfill_duration("a.mp4", 3.14)  # should not raise


class TestSaveMetadataAndThumbnail(unittest.TestCase):
    """Tests for the compiler's metadata/thumbnail writer."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="meta_test_")
        self.output_dir = os.path.join(self.tmpdir, "output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.output_patcher = patch("gui.video_compiler.OUTPUT_DIR", self.output_dir)
        self.output_patcher.start()
        self.subprocess_patcher = patch(
            "gui.video_compiler.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0),
        )
        self.subprocess_patcher.start()

    def tearDown(self):
        self.subprocess_patcher.stop()
        self.output_patcher.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _content(self, name: str) -> str:
        with open(os.path.join(self.output_dir, name), encoding="utf-8") as f:
            return f.read()

    def test_writes_duration_line_when_provided(self):
        """A provided duration is written to the metadata sidecar."""
        _save_metadata_and_thumbnail(
            os.path.join(self.output_dir, "video.mp4"),
            "video.mp4",
            {"generated_title": "My Title", "generated_hashtags": "#tag"},
            "Hello world script",
            duration=12.34,
        )
        self.assertIn("Duration: 12.34", self._content("video.txt"))

    def test_omits_duration_line_when_none(self):
        """Without a duration, no Duration line is written."""
        _save_metadata_and_thumbnail(
            os.path.join(self.output_dir, "video.mp4"),
            "video.mp4",
            {"generated_title": "My Title", "generated_hashtags": "#tag"},
            "Hello world script",
        )
        self.assertNotIn("Duration:", self._content("video.txt"))

    def test_writes_title_and_hashtags(self):
        """Title and hashtags still land on the first two lines."""
        _save_metadata_and_thumbnail(
            os.path.join(self.output_dir, "video.mp4"),
            "video.mp4",
            {"generated_title": "My Title", "generated_hashtags": "#a #b"},
            "Hello world script",
            duration=1.0,
        )
        lines = self._content("video.txt").splitlines()
        self.assertEqual(lines[0], "My Title")
        self.assertEqual(lines[1], "#a #b")
        self.assertTrue(lines[2].startswith("Duration:"))


if __name__ == "__main__":
    unittest.main()

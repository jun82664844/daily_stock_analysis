from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.services.alphasift_screen_cache import inspect_snapshot_cache


class AlphaSiftScreenCacheV105TestCase(unittest.TestCase):
    def _write_cache(self, path: Path, *, created_at: str) -> None:
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "created_at": created_at,
                    "metadata": {"snapshot_source": "sina", "row_count": 1},
                    "frame": {
                        "columns": ["code", "price", "pe_ratio"],
                        "index": [0],
                        "data": [["600519", 1480.0, 24.5]],
                    },
                }
            ),
            encoding="utf-8",
        )

    def test_recent_cache_is_preferred_and_reports_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "snapshot.last_good.json"
            self._write_cache(path, created_at="2026-07-11T10:00:00+00:00")
            decision = inspect_snapshot_cache(
                path,
                now=datetime(2026, 7, 11, 10, 5, tzinfo=timezone.utc),
                max_age_seconds=600,
            )

        self.assertTrue(decision["available"])
        self.assertTrue(decision["use_cache"])
        self.assertEqual(decision["source"], "sina")
        self.assertEqual(decision["row_count"], 1)
        self.assertEqual(decision["age_seconds"], 300)

    def test_force_refresh_and_expired_cache_do_not_use_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "snapshot.last_good.json"
            self._write_cache(path, created_at="2026-07-11T08:00:00+00:00")
            now = datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc)
            expired = inspect_snapshot_cache(path, now=now, max_age_seconds=600)
            forced = inspect_snapshot_cache(path, now=now, max_age_seconds=10_000, force_refresh=True)

        self.assertFalse(expired["use_cache"])
        self.assertEqual(expired["reason"], "expired")
        self.assertFalse(forced["use_cache"])
        self.assertEqual(forced["reason"], "force_refresh")

    def test_environment_override_controls_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "snapshot.last_good.json"
            self._write_cache(path, created_at="2026-07-11T10:00:00+00:00")
            with patch.dict(os.environ, {"DSA_ALPHASIFT_SCREEN_CACHE_TTL_SECONDS": "120"}, clear=False):
                decision = inspect_snapshot_cache(
                    path,
                    now=datetime(2026, 7, 11, 10, 3, tzinfo=timezone.utc),
                )

        self.assertEqual(decision["max_age_seconds"], 120)
        self.assertFalse(decision["use_cache"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict


def _payload() -> Dict[str, Any]:
    return {
        "as_of": "2026-07-30T00:00:00+00:00",
        "items": [],
        "market_sources": [
            {
                "market": "cn",
                "status": "cached",
                "event_count": 1,
                "observed_at": "2026-07-29T00:00:00+00:00",
                "fetched_at": "2026-07-30T00:00:00+00:00",
                "warning_code": None,
            }
        ],
        "warnings": [],
        "cache": {
            "hit": False,
            "age_seconds": 0,
            "ttl_seconds": 900,
            "storage": "memory",
            "refreshing": False,
        },
        "ai_used": False,
        "informational_only": True,
    }


class PublicEventReactionSnapshotStoreV137TestCase(unittest.TestCase):
    def test_round_trip_survives_restart_and_marks_disk_origin(self) -> None:
        from src.services.public_event_reaction_cache import (
            PublicEventReactionSnapshotStore,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "event-reactions.json"
            now = [1_000.0]
            writer = PublicEventReactionSnapshotStore(
                path=path,
                wall_clock=lambda: now[0],
                stale_ttl_seconds=3_600,
            )
            self.assertTrue(writer.write(_payload()))

            now[0] += 12
            restarted = PublicEventReactionSnapshotStore(
                path=path,
                wall_clock=lambda: now[0],
                stale_ttl_seconds=3_600,
            )
            snapshot = restarted.read()

            self.assertIsNotNone(snapshot)
            assert snapshot is not None
            self.assertEqual(snapshot["payload"]["items"], [])
            self.assertEqual(snapshot["payload"]["market_sources"][0]["market"], "cn")
            self.assertFalse(snapshot["payload"]["ai_used"])
            self.assertTrue(snapshot["payload"]["informational_only"])
            self.assertEqual(snapshot["age_seconds"], 12)
            self.assertFalse(snapshot["stale"])
            self.assertEqual(snapshot["payload"]["cache"]["storage"], "disk")
            self.assertTrue(snapshot["payload"]["cache"]["hit"])
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_rejects_secrets_wrong_boundary_and_oversized_or_corrupt_files(self) -> None:
        from src.services.public_event_reaction_cache import (
            PublicEventReactionSnapshotStore,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "event-reactions.json"
            store = PublicEventReactionSnapshotStore(
                path=path,
                wall_clock=lambda: 2_000.0,
                max_bytes=1_024,
            )

            secret_payload = _payload()
            secret_payload["api_key"] = "sk-live-secret"
            self.assertFalse(store.write(secret_payload))
            self.assertFalse(path.exists())

            wrong_boundary = _payload()
            wrong_boundary["ai_used"] = True
            self.assertFalse(store.write(wrong_boundary))

            path.write_text("{not-json", encoding="utf-8")
            self.assertIsNone(store.read())

            path.write_text(
                json.dumps(
                    {
                        "version": 99,
                        "written_at": 2_000.0,
                        "payload": _payload(),
                    }
                ),
                encoding="utf-8",
            )
            self.assertIsNone(store.read())

            path.write_bytes(b"x" * 1_025)
            self.assertIsNone(store.read())

    def test_expired_snapshot_is_ignored_and_stale_snapshot_is_identified(self) -> None:
        from src.services.public_event_reaction_cache import (
            PublicEventReactionSnapshotStore,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "event-reactions.json"
            now = [5_000.0]
            store = PublicEventReactionSnapshotStore(
                path=path,
                wall_clock=lambda: now[0],
                cache_ttl_seconds=10,
                stale_ttl_seconds=60,
            )
            self.assertTrue(store.write(_payload()))

            now[0] += 11
            stale = store.read()
            self.assertIsNotNone(stale)
            assert stale is not None
            self.assertTrue(stale["stale"])

            now[0] += 50
            self.assertIsNone(store.read())


class PublicEventReactionCacheFirstServiceV137TestCase(unittest.TestCase):
    def test_all_market_failure_does_not_replace_last_good_snapshot(self) -> None:
        from src.services.public_event_reaction_cache import (
            PublicEventReactionSnapshotStore,
        )
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "event-reactions.json"
            store = PublicEventReactionSnapshotStore(path=path)
            last_good = _payload()
            last_good["items"] = [{"event_id": "last-good"}]
            self.assertTrue(store.write(last_good))

            service = PublicMarketEventReactionService(
                event_loader=lambda: {
                    "events": [],
                    "market_sources": [
                        {
                            "market": market,
                            "status": "unavailable",
                            "event_count": 0,
                            "observed_at": None,
                            "fetched_at": "2026-07-30T00:01:00+00:00",
                            "warning_code": "event_calendar_market_unavailable",
                        }
                        for market in ("cn", "hk", "us")
                    ],
                },
                snapshot_store=store,
                clock=lambda: "2026-07-30T00:01:00+00:00",
            )

            with self.assertRaises(RuntimeError):
                service._refresh_and_store()

            snapshot = store.read()
            self.assertIsNotNone(snapshot)
            assert snapshot is not None
            self.assertEqual(
                snapshot["payload"]["items"],
                [{"event_id": "last-good"}],
            )

    def test_cache_first_returns_immediately_and_only_starts_one_refresh(self) -> None:
        from src.services.public_event_reaction_cache import (
            PublicEventReactionSnapshotStore,
        )
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        release = threading.Event()
        started = threading.Event()
        calls = {"count": 0}

        def slow_event_loader() -> Dict[str, Any]:
            calls["count"] += 1
            started.set()
            release.wait(timeout=2)
            return {
                "events": [],
                "market_sources": [
                    {
                        "market": market,
                        "status": "fresh",
                        "event_count": 0,
                        "observed_at": "2026-07-30T00:00:00+00:00",
                        "fetched_at": "2026-07-30T00:00:00+00:00",
                        "warning_code": None,
                    }
                    for market in ("cn", "hk", "us")
                ],
            }

        with tempfile.TemporaryDirectory() as temp_dir, ThreadPoolExecutor(
            max_workers=1
        ) as executor:
            store = PublicEventReactionSnapshotStore(
                path=Path(temp_dir) / "event-reactions.json"
            )
            service = PublicMarketEventReactionService(
                event_loader=slow_event_loader,
                snapshot_store=store,
                refresh_executor=executor,
                clock=lambda: "2026-07-30T00:00:00+00:00",
            )

            first = service.build(cache_first=True)
            second = service.build(cache_first=True)

            self.assertTrue(started.wait(timeout=1))
            self.assertEqual(calls["count"], 1)
            self.assertTrue(first["cache"]["refreshing"])
            self.assertEqual(first["cache"]["storage"], "none")
            self.assertEqual(first["items"], [])
            self.assertTrue(second["cache"]["refreshing"])

            release.set()
            self.assertTrue(service.wait_for_refresh(timeout=2))
            completed = service.build(cache_first=True)
            self.assertFalse(completed["cache"]["refreshing"])
            self.assertTrue(
                completed["cache"]["storage"] in {"memory", "disk"}
            )

    def test_restarted_service_serves_disk_snapshot_while_refresh_runs(self) -> None:
        from src.services.public_event_reaction_cache import (
            PublicEventReactionSnapshotStore,
        )
        from src.services.public_market_event_reaction_service import (
            PublicMarketEventReactionService,
        )

        with tempfile.TemporaryDirectory() as temp_dir, ThreadPoolExecutor(
            max_workers=1
        ) as executor:
            path = Path(temp_dir) / "event-reactions.json"
            now = [10_000.0]
            store = PublicEventReactionSnapshotStore(
                path=path,
                wall_clock=lambda: now[0],
                cache_ttl_seconds=10,
                stale_ttl_seconds=3_600,
            )
            self.assertTrue(store.write(_payload()))
            now[0] += 11
            release = threading.Event()

            def refresh_loader() -> Dict[str, Any]:
                release.wait(timeout=2)
                return {
                    "events": [],
                    "market_sources": [
                        {
                            "market": market,
                            "status": "fresh",
                            "event_count": 0,
                            "observed_at": "2026-07-30T00:00:11+00:00",
                            "fetched_at": "2026-07-30T00:00:11+00:00",
                            "warning_code": None,
                        }
                        for market in ("cn", "hk", "us")
                    ],
                }

            service = PublicMarketEventReactionService(
                event_loader=refresh_loader,
                snapshot_store=store,
                refresh_executor=executor,
                clock=lambda: "2026-07-30T00:00:11+00:00",
            )

            cached = service.build(cache_first=True)
            self.assertTrue(cached["cache"]["hit"])
            self.assertEqual(cached["cache"]["storage"], "disk")
            self.assertTrue(cached["cache"]["refreshing"])
            self.assertIn("event_reaction_response_stale", cached["warnings"])

            release.set()
            self.assertTrue(service.wait_for_refresh(timeout=2))


if __name__ == "__main__":
    unittest.main()

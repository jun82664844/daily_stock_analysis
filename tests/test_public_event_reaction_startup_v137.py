from __future__ import annotations

import asyncio
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI


class PublicEventReactionStartupV137TestCase(unittest.TestCase):
    def test_prewarm_requires_all_local_feature_switches(self) -> None:
        from api.v1.endpoints.market_workspace import (
            prewarm_public_event_reactions,
        )

        enabled = {
            "PLATFORM_MARKET_WORKSPACE_V113_ENABLED": "true",
            "PLATFORM_PUBLIC_MARKET_HOME_V116_ENABLED": "true",
            "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_ENABLED": "true",
            "PLATFORM_PUBLIC_EVENT_REACTIONS_V137_CACHE_FIRST_ENABLED": "true",
        }
        with (
            patch.dict(os.environ, enabled, clear=False),
            patch(
                "api.v1.endpoints.market_workspace._public_event_reaction_service.prewarm",
                return_value=True,
            ) as prewarm,
        ):
            self.assertTrue(prewarm_public_event_reactions())
            prewarm.assert_called_once_with()

        disabled = {
            **enabled,
            "PLATFORM_PUBLIC_EVENT_REACTIONS_V137_CACHE_FIRST_ENABLED": "false",
        }
        with (
            patch.dict(os.environ, disabled, clear=False),
            patch(
                "api.v1.endpoints.market_workspace._public_event_reaction_service.prewarm",
                side_effect=AssertionError("disabled prewarm must not run"),
            ),
        ):
            self.assertFalse(prewarm_public_event_reactions())

    def test_fastapi_lifespan_schedules_public_prewarm_once(self) -> None:
        from api.app import app_lifespan

        app = FastAPI()

        async def exercise() -> None:
            with (
                patch("api.app.SystemConfigService", return_value=object()),
                patch("api.app._schedule_stock_index_background_refresh"),
                patch("api.app._schedule_public_event_reaction_prewarm") as schedule,
            ):
                async with app_lifespan(app):
                    schedule.assert_called_once_with()

        asyncio.run(exercise())

    def test_templates_keep_v137_cache_first_disabled(self) -> None:
        root = Path(__file__).resolve().parents[1]
        env_example = (root / ".env.example").read_text(encoding="utf-8")
        production = (
            root / "docs/superpowers/platform-production-env.example"
        ).read_text(encoding="utf-8")

        for content in (env_example, production):
            self.assertIn(
                "PLATFORM_PUBLIC_EVENT_REACTIONS_V137_CACHE_FIRST_ENABLED=false",
                content,
            )
            self.assertIn(
                "PLATFORM_PUBLIC_EVENT_REACTIONS_V137_DISK_STALE_TTL_SECONDS=86400",
                content,
            )
            self.assertIn(
                "PLATFORM_PUBLIC_EVENT_REACTIONS_V137_CACHE_PATH=local/public_event_reactions_v137.json",
                content,
            )


if __name__ == "__main__":
    unittest.main()

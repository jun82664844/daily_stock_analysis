from __future__ import annotations

import os
import subprocess
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]


class EventDrivenResearchV132VerifierTestCase(unittest.TestCase):
    def test_verifier_entrypoint_exists(self) -> None:
        self.assertTrue((REPO_ROOT / "scripts/verify_platform_event_driven_research_v132.py").is_file())

    def test_frontend_contract_requires_bilingual_research_and_causality_boundary(self) -> None:
        from scripts.verify_platform_event_driven_research_v132 import frontend_contract

        valid = """
data-testid="market-event-research-panel-v132"
data-testid="market-event-public-quote-v132"
data-testid="market-event-quote-unavailable-v132"
research: '研究事件'
research: 'Research event'
事件研究卡 · 未使用 AI
Event research card · No AI used
价格变化与事件同时呈现，不代表事件导致涨跌。
Price changes and the event are shown together; this does not mean the event caused the move.
仅提供公开资讯和数据，不构成投资建议。
Public information and data only. Not investment advice.
"""
        self.assertTrue(frontend_contract(valid).ok)
        self.assertFalse(frontend_contract(valid.replace("不代表事件导致涨跌", "直接导致涨跌")).ok)

    def test_privacy_contract_rejects_network_ai_and_user_tracking(self) -> None:
        from scripts.verify_platform_event_driven_research_v132 import privacy_cost_contract

        valid = "const symbol = event.symbol; const quote = marketItem?.currentPrice;"
        self.assertTrue(privacy_cost_contract(valid).ok)
        self.assertFalse(privacy_cost_contract(valid + " fetch('/api/v1/market')").ok)
        self.assertFalse(privacy_cost_contract(valid + " const model = 'ollama';").ok)

    def test_frontend_safety_contract_scans_panel_daily_center_and_home_wiring(self) -> None:
        from scripts.verify_platform_event_driven_research_v132 import frontend_safety_contract

        home = """
marketWorkspaceApi.getSymbol('existing-preview-call')
const marketItems = useMemo
home-safe
const selectedAlertItem
"""
        self.assertTrue(frontend_safety_contract("daily-safe", "panel-safe", home).ok)
        self.assertFalse(frontend_safety_contract("fetch('/events')", "panel-safe", home).ok)
        self.assertFalse(frontend_safety_contract(
            "daily-safe",
            "panel-safe",
            home.replace("home-safe", "const model = 'openai';"),
        ).ok)

    def test_regression_contract_requires_quote_and_degraded_paths(self) -> None:
        from scripts.verify_platform_event_driven_research_v132 import regression_tests_contract

        valid = """
opens a no-AI event research card with linked public market context
shows localized unavailable text when a linked quote field is missing
degrades honestly when linked quote context is unavailable and shows a research checklist
does not use a market index quote as linked-security research context
getByRole('button', { name: '研究 AAPL 关联事件' })
getByTestId('market-event-research-panel-v132')
getByTestId('market-event-quote-unavailable-v132')
"""
        self.assertTrue(regression_tests_contract(valid).ok)
        self.assertFalse(regression_tests_contract(valid.replace("degrades honestly", "hides missing data")).ok)
        self.assertFalse(regression_tests_contract(valid.replace(
            "does not use a market index quote as linked-security research context",
            "allows index quote collision",
        )).ok)

    def test_focused_vitest_check_uses_the_real_test_process_exit_code(self) -> None:
        from scripts.verify_platform_event_driven_research_v132 import focused_vitest_check

        with (
            patch(
                "scripts.verify_platform_event_driven_research_v132.shutil.which",
                return_value="npm.cmd",
            ),
            patch(
                "scripts.verify_platform_event_driven_research_v132.subprocess.run",
            ) as run,
        ):
            run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Tests 25 passed",
                stderr="",
            )
            result = focused_vitest_check(REPO_ROOT)
            self.assertTrue(result.ok)
            command = run.call_args.args[0]
            self.assertIn("DailyMarketEventCenterV126.test.tsx", " ".join(command))
            self.assertIn("PublicMarketHomeV116.test.tsx", " ".join(command))

            run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="Tests 1 failed",
                stderr="",
            )
            self.assertFalse(focused_vitest_check(REPO_ROOT).ok)

    def test_wiring_contract_rejects_market_indices_as_security_candidates(self) -> None:
        from scripts.verify_platform_event_driven_research_v132 import wiring_contract

        daily = """
marketItems?: MarketSecurityItem[]
const marketItemBySymbol = useMemo
normalizeMarketEventSymbol(item.symbol)
normalizeMarketEventSymbol(event.symbol)
<MarketEventResearchPanelV132
"""
        home = """
const marketItems = useMemo
marketItems={marketItems}
...section.attention,
...(section.mostActive ?? [])
...(section.gainers ?? [])
...(section.losers ?? [])
const selectedAlertItem
"""
        self.assertTrue(wiring_contract(daily, home).ok)
        self.assertFalse(wiring_contract(daily, home.replace(
            "...section.attention,",
            "...section.indices,\n...section.attention,",
        )).ok)

    def test_bundle_check_uses_the_homepage_chunk_referenced_by_current_entry(self) -> None:
        from scripts.verify_platform_event_driven_research_v132 import homepage_bundle_check

        with TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir) / "static"
            assets_dir = static_dir / "assets"
            assets_dir.mkdir(parents=True)
            (static_dir / "index.html").write_text(
                '<script type="module" src="/assets/index-current.js"></script>',
                encoding="utf-8",
            )
            (assets_dir / "index-current.js").write_text(
                'const home = "./HomePage-current.js";',
                encoding="utf-8",
            )
            current = assets_dir / "HomePage-current.js"
            current.write_text("current", encoding="utf-8")
            orphan = assets_dir / "HomePage-orphan.js"
            orphan.write_text("orphan", encoding="utf-8")
            orphan_mtime_ns = current.stat().st_mtime_ns + 1_000_000_000
            os.utime(orphan, ns=(orphan_mtime_ns, orphan_mtime_ns))

            result = homepage_bundle_check(assets_dir)

        self.assertTrue(result.ok)
        self.assertEqual(result.details["filename"], "HomePage-current.js")


if __name__ == "__main__":
    unittest.main()

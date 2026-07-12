from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_NAME = "src.services.financial_research_workflow_service"
MODULE_AVAILABLE = importlib.util.find_spec(MODULE_NAME) is not None


class FinancialResearchWorkflowServiceV106TestCase(unittest.TestCase):
    def test_service_module_exists(self) -> None:
        self.assertTrue(MODULE_AVAILABLE, "financial research workflow service is not implemented")

    @unittest.skipUnless(MODULE_AVAILABLE, "service is not implemented yet")
    def test_installed_source_reports_allowlist_without_enabling_connectors(self) -> None:
        from src.services.financial_research_workflow_service import (
            ACCEPTED_SOURCE_COMMIT,
            FinancialResearchWorkflowService,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_fake_source(root)

            diagnostics = FinancialResearchWorkflowService(source_root=root).source_diagnostics()

        self.assertTrue(diagnostics["installed"])
        self.assertEqual(diagnostics["source_name"], "anthropics/financial-services")
        self.assertEqual(diagnostics["license"], "Apache-2.0")
        self.assertEqual(diagnostics["commit"], ACCEPTED_SOURCE_COMMIT)
        self.assertTrue(diagnostics["commit_verified"])
        self.assertFalse(diagnostics["external_code_executed"])
        self.assertFalse(diagnostics["connectors_enabled"])
        self.assertEqual(
            [item["id"] for item in diagnostics["workflows"]],
            ["company_snapshot", "earnings_review", "sector_overview", "catalyst_calendar"],
        )
        self.assertTrue(all(item["available"] for item in diagnostics["workflows"]))

    @unittest.skipUnless(MODULE_AVAILABLE, "service is not implemented yet")
    def test_workflows_use_snapshot_facts_without_ai_or_advice(self) -> None:
        from src.services.financial_research_workflow_service import (
            ACCEPTED_SOURCE_COMMIT,
            FinancialResearchWorkflowService,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_fake_source(root)
            service = FinancialResearchWorkflowService(source_root=root)

            payload = service.build_research_workflows(self._snapshot())

        self.assertEqual(payload["stock_code"], "AAPL")
        self.assertEqual(payload["mode"], "deterministic_no_ai")
        self.assertFalse(payload["ai_used"])
        self.assertFalse(payload["public_search_used"])
        self.assertEqual(len(payload["workflows"]), 4)
        self.assertEqual(payload["source"]["commit"], ACCEPTED_SOURCE_COMMIT)
        facts_by_workflow = {
            item["id"]: {fact["code"] for fact in item["facts"]}
            for item in payload["workflows"]
        }
        self.assertIn("market_cap", facts_by_workflow["company_snapshot"])
        self.assertIn("revenue", facts_by_workflow["earnings_review"])
        self.assertIn("industry", facts_by_workflow["sector_overview"])
        self.assertIn("event:filing", facts_by_workflow["catalyst_calendar"])
        serialized = json.dumps(payload["workflows"], ensure_ascii=False).lower()
        for forbidden in ("buy", "sell", "target price", "expected return", "买入", "卖出", "目标价"):
            self.assertNotIn(forbidden, serialized)
        self.assertNotIn("target_price", payload)
        self.assertIn("仅提供资讯和数据", payload["boundary_zh"])

        company_facts = {fact["code"]: fact for fact in payload["workflows"][0]["facts"]}
        self.assertEqual(company_facts["current_price"]["currency"], "USD")
        self.assertEqual(company_facts["current_price"]["unit"], "currency")
        self.assertEqual(company_facts["volume"]["unit"], "shares")
        earnings_facts = {fact["code"]: fact for fact in payload["workflows"][1]["facts"]}
        self.assertEqual(earnings_facts["revenue_growth"]["unit"], "percent")

    @unittest.skipUnless(MODULE_AVAILABLE, "service is not implemented yet")
    def test_wrong_source_commit_is_not_reported_as_installed(self) -> None:
        from src.services.financial_research_workflow_service import FinancialResearchWorkflowService

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_fake_source(root, commit="f" * 40)
            diagnostics = FinancialResearchWorkflowService(source_root=root).source_diagnostics()

        self.assertFalse(diagnostics["installed"])
        self.assertFalse(diagnostics["commit_verified"])

    @unittest.skipUnless(MODULE_AVAILABLE, "service is not implemented yet")
    def test_placeholder_event_lanes_remain_partial_and_missing(self) -> None:
        from src.services.financial_research_workflow_service import FinancialResearchWorkflowService

        snapshot = self._snapshot()
        snapshot["intelligence"] = {
            "news_center": {
                "items": [
                    {
                        "category": "news",
                        "title": "Market-moving news lane",
                        "status": "degraded",
                        "source": "no_ai_news_center_rules",
                    },
                    {
                        "category": "financials",
                        "title": "Financial snapshot lane",
                        "status": "available",
                        "source": "a_share_realtime",
                    },
                ]
            }
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_fake_source(root)
            payload = FinancialResearchWorkflowService(source_root=root).build_research_workflows(snapshot)

        calendar = next(item for item in payload["workflows"] if item["id"] == "catalyst_calendar")
        self.assertEqual(calendar["status"], "partial")
        self.assertIn("events", calendar["missing_data"])
        self.assertEqual(calendar["facts"], [])

    @unittest.skipUnless(MODULE_AVAILABLE, "service is not implemented yet")
    def test_missing_facts_are_explicit_and_do_not_block_other_workflows(self) -> None:
        from src.services.financial_research_workflow_service import FinancialResearchWorkflowService

        snapshot = self._snapshot()
        snapshot["profile"] = None
        snapshot["intelligence"] = None

        with tempfile.TemporaryDirectory() as temp_dir:
            service = FinancialResearchWorkflowService(source_root=Path(temp_dir))
            payload = service.build_research_workflows(snapshot)

        self.assertFalse(payload["source"]["installed"])
        self.assertEqual(len(payload["workflows"]), 4)
        self.assertTrue(all(item["status"] == "partial" for item in payload["workflows"]))
        self.assertIn("market_cap", payload["workflows"][0]["missing_data"])
        self.assertIn("events", payload["workflows"][3]["missing_data"])

    @staticmethod
    def _write_fake_source(root: Path, *, commit: str | None = None) -> None:
        from src.services.financial_research_workflow_service import ACCEPTED_SOURCE_COMMIT

        paths = (
            "plugins/vertical-plugins/financial-analysis/skills/comps-analysis/SKILL.md",
            "plugins/vertical-plugins/equity-research/skills/earnings-analysis/SKILL.md",
            "plugins/vertical-plugins/equity-research/skills/sector-overview/SKILL.md",
            "plugins/vertical-plugins/equity-research/skills/catalyst-calendar/SKILL.md",
        )
        for relative in paths:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# reference\n", encoding="utf-8")
        (root / "LICENSE").write_text("Apache License Version 2.0", encoding="utf-8")
        (root / ".git" / "refs" / "heads").mkdir(parents=True, exist_ok=True)
        (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (root / ".git" / "refs" / "heads" / "main").write_text(
            f"{commit or ACCEPTED_SOURCE_COMMIT}\n",
            encoding="utf-8",
        )

    @staticmethod
    def _snapshot() -> dict:
        return {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "market": "us",
            "quote": {
                "current_price": 205.0,
                "change_percent": 1.25,
                "volume": 50_000_000,
                "amount": 10_000_000_000,
                "update_time": "2026-07-11T10:00:00Z",
                "source": "yahoo_chart",
                "freshness": "fresh",
            },
            "profile": {
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "market_cap": 3_100_000_000_000,
                "pe_ratio": 31.2,
                "pb_ratio": 48.0,
                "revenue": 410_000_000_000,
                "net_profit": 105_000_000_000,
                "revenue_growth": 0.06,
                "earnings_growth": 0.08,
                "source": "yfinance_profile",
                "freshness": "cached",
            },
            "intelligence": {
                "news_center": {
                    "items": [
                        {
                            "category": "filing",
                            "title": "Quarterly filing available",
                            "summary": "Review the disclosed operating figures.",
                            "status": "available",
                            "source": "company_filing",
                            "updated_at": "2026-07-10T08:00:00Z",
                        }
                    ]
                }
            },
            "ai_used": False,
        }


if __name__ == "__main__":
    unittest.main()

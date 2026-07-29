from __future__ import annotations

import unittest
from pathlib import Path


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

    def test_regression_contract_requires_quote_and_degraded_paths(self) -> None:
        from scripts.verify_platform_event_driven_research_v132 import regression_tests_contract

        valid = """
opens a no-AI event research card with linked public market context
degrades honestly when linked quote context is unavailable and shows a research checklist
getByRole('button', { name: '研究 AAPL 关联事件' })
getByTestId('market-event-research-panel-v132')
getByTestId('market-event-quote-unavailable-v132')
"""
        self.assertTrue(regression_tests_contract(valid).ok)
        self.assertFalse(regression_tests_contract(valid.replace("degrades honestly", "hides missing data")).ok)

    def test_bundle_check_function_is_part_of_the_gate(self) -> None:
        from scripts import verify_platform_event_driven_research_v132 as verifier

        self.assertTrue(hasattr(verifier, "homepage_bundle_check"))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest


class MarketEventRelevanceV127VerifierTestCase(unittest.TestCase):
    def test_backend_contract_requires_noise_filter_scoring_and_global_dedupe(self) -> None:
        from scripts.verify_platform_market_event_relevance_v127 import backend_relevance_contract

        valid = """
FINANCE_SIGNAL_KEYWORDS = ('stock', 'market')
PROMOTIONAL_NOISE_KEYWORDS = ('sponsored content',)
CATEGORY_REASONS = {'macro': 'macro_event'}
events_by_title = {}
existing = events_by_title.get(title_key)
if existing is not None:
    continue
if category == 'market' and not symbol and not has_market_signal:
    continue
relevance_score, relevance_reasons = self._relevance()
importance = self._importance(relevance_score)
promotional = self._is_promotional_noise(title)
"""
        self.assertTrue(backend_relevance_contract(valid).ok)
        self.assertFalse(backend_relevance_contract(valid.replace("events_by_title = {}", "events_by_title = []")).ok)
        self.assertFalse(backend_relevance_contract(valid.replace("not has_market_signal", "has_market_signal")).ok)
        self.assertFalse(backend_relevance_contract(valid + "\nimport httpx").ok)

    def test_api_contract_requires_safe_defaults_in_both_layers(self) -> None:
        from scripts.verify_platform_market_event_relevance_v127 import api_contract

        schema = """
relevance_score: int = Field(0, ge=0, le=100)
importance: MarketEventImportance = 'low'
relevance_reasons: List[str] = Field(default_factory=list)
"""
        frontend = """
relevanceScore: number;
importance: 'high' | 'medium' | 'low';
relevanceReasons: string[];
relevanceScore: Number.isFinite(event.relevanceScore) ? event.relevanceScore : 0
importance: event.importance ?? 'low'
relevanceReasons: Array.isArray(event.relevanceReasons) ? event.relevanceReasons : []
"""
        self.assertTrue(api_contract(schema, frontend).ok)
        self.assertFalse(api_contract(schema.replace("ge=0, le=100", ""), frontend).ok)
        self.assertFalse(api_contract(schema, frontend.replace("event.importance ?? 'low'", "event.importance")).ok)

    def test_frontend_contract_requires_market_filters_watchlist_priority_and_bilingual_safety(self) -> None:
        from scripts.verify_platform_market_event_relevance_v127 import frontend_contract

        valid = """
const MARKET_FILTERS = ['all', 'cn', 'hk', 'us'];
setMarketFilter(item)
event.market === marketFilter
watchlist.has(normalizeSymbol(event.symbol))
event.relevanceScore
event.importance
event.relevanceReasons
全部市场 A股 港股 美股 高重要度 中重要度 重点事件 关联证券
All markets China Hong Kong US High importance Medium importance Priority events Linked security
仅提供公开资讯和数据，不构成投资建议。
Public information and data only. Not investment advice.
"""
        self.assertTrue(frontend_contract(valid).ok)
        self.assertFalse(frontend_contract(valid.replace("watchlist.has", "watchlist.ignores")).ok)
        self.assertFalse(frontend_contract(valid + "\n目标价").ok)

    def test_frontend_contract_accepts_v130_delegated_watchlist_and_relevance_sorting(self) -> None:
        from scripts.verify_platform_market_event_relevance_v127 import frontend_contract

        component = """
const MARKET_FILTERS = ['all', 'cn', 'hk', 'us'];
setMarketFilter(item)
event.market === marketFilter
event.importance event.relevanceReasons
全部市场 A股 港股 美股 高重要度 中重要度 重点事件 关联证券
All markets China Hong Kong US High importance Medium importance Priority events Linked security
仅提供公开资讯和数据，不构成投资建议。
Public information and data only. Not investment advice.
"""
        helper = """
symbols.has(normalizeMarketEventSymbol(event.symbol))
left.event.relevanceScore !== right.event.relevanceScore
"""
        self.assertTrue(frontend_contract(component, helper).ok)
        self.assertFalse(frontend_contract(component, helper.replace("symbols.has", "symbols.ignores")).ok)


if __name__ == "__main__":
    unittest.main()

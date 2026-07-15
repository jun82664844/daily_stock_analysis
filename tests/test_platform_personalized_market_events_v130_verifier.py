from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class PersonalizedMarketEventsV130VerifierTestCase(unittest.TestCase):
    def test_backend_contract_retains_sector_without_user_or_network_lookup(self) -> None:
        from scripts.verify_platform_personalized_market_events_v130 import backend_sector_contract

        valid = """
linked_symbol, linked_name, linked_sector = self._linked_security(title, securities)
"sector": sector,
"sector": str(item.get("sector") or "").strip(),
return symbol, name or None, security.get("sector") or None
"""
        self.assertTrue(backend_sector_contract(valid).ok)
        self.assertFalse(backend_sector_contract(valid + "\nimport httpx").ok)
        self.assertFalse(backend_sector_contract(valid + "\nplatform_user_id = 'leak'").ok)

    def test_personalization_contract_requires_complete_stable_priority_order(self) -> None:
        from scripts.verify_platform_personalized_market_events_v130 import personalization_contract

        valid = """
export function personalizeMarketEvents()
const priority = { watchlist: 3, sector: 2, market: 1 };
if (personalized) {
  const priorityDifference = (right.match ? priority[right.match] : 0) - (left.match ? priority[left.match] : 0);
}
return left.index - right.index;
export function deriveWatchlistSectors()
if (/^[A-Z0-9]{2,12}-(?:USD|USDT|USDC|BTC|ETH)$/.test(raw)) return null;
"""
        self.assertTrue(personalization_contract(valid).ok)
        self.assertFalse(personalization_contract(valid.replace("watchlist: 3, sector: 2, market: 1", "watchlist: 1")).ok)
        self.assertFalse(personalization_contract(valid.replace("left.index - right.index", "0")).ok)

    def test_frontend_contract_requires_bilingual_controls_and_visitor_boundary(self) -> None:
        from scripts.verify_platform_personalized_market_events_v130 import frontend_contract

        valid = """
const hasWatchlist = watchlist.size > 0;
const focusActive = hasWatchlist && (viewMode === 'auto' || viewMode === 'focus');
personalizeMarketEvents(
{hasWatchlist || unseenEventIds.size > 0 || unreadActive ? (<div aria-label={t.eventViewLabel}>{hasWatchlist ? (<button>focus</button>) : null}</div>) : null}
focusFirst: '为我优先', allEvents: '全部事件', matchLabels: { watchlist: '自选相关', sector: '相关行业', market: '关注市场' },
focusFirst: 'For me first', allEvents: 'All events', matchLabels: { watchlist: 'Watchlist match', sector: 'Related industry', market: 'Followed market' },
仅提供公开资讯和数据，不构成投资建议。
Public information and data only. Not investment advice.
"""
        self.assertTrue(frontend_contract(valid).ok)
        self.assertFalse(frontend_contract(valid.replace("const focusActive = hasWatchlist", "const focusActive = true")).ok)
        self.assertFalse(frontend_contract(valid.replace("allEvents: '全部事件'", "")).ok)

    def test_bundle_must_be_fresh_and_under_homepage_limit(self) -> None:
        from scripts.verify_platform_personalized_market_events_v130 import homepage_bundle_check

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assets = root / "static" / "assets"
            assets.mkdir(parents=True)
            chunk = assets / "HomePage-test.js"
            source = root / "DailyMarketEventCenterV126.tsx"
            chunk.write_text("export default {};", encoding="utf-8")
            source.write_text("export default function Component() {}", encoding="utf-8")

            source_mtime = source.stat().st_mtime_ns
            stale_mtime = source_mtime - 2_000_000_000
            os.utime(chunk, ns=(stale_mtime, stale_mtime))
            self.assertFalse(homepage_bundle_check(assets, source_paths=[source]).ok)

            fresh_mtime = source_mtime + 2_000_000_000
            os.utime(chunk, ns=(fresh_mtime, fresh_mtime))
            self.assertTrue(homepage_bundle_check(assets, source_paths=[source]).ok)


if __name__ == "__main__":
    unittest.main()

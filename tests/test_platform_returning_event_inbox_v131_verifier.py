from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class ReturningEventInboxV131VerifierTestCase(unittest.TestCase):
    def test_frontend_contract_requires_bilingual_new_only_inbox(self) -> None:
        from scripts.verify_platform_returning_event_inbox_v131 import frontend_contract

        valid = """
type ViewMode = 'auto' | 'focus' | 'unread' | 'all';
const unreadActive = viewMode === 'unread';
data-testid="market-event-inbox-summary-v131"
newOnly: '只看新增', noNewEvents: '当前没有新增市场事件', viewAllEvents: '查看全部事件',
newOnly: 'New only', noNewEvents: 'No new market events', viewAllEvents: 'View all events',
aria-pressed={unreadActive}
onClick={() => setViewMode('unread')}
onClick={() => setViewMode('all')}
"""
        self.assertTrue(frontend_contract(valid).ok)
        self.assertFalse(frontend_contract(valid.replace("'unread'", "'recent'", 1)).ok)
        self.assertFalse(frontend_contract(valid.replace("newOnly: 'New only'", "")).ok)

    def test_filter_contract_keeps_read_state_separate_from_viewing(self) -> None:
        from scripts.verify_platform_returning_event_inbox_v131 import filter_contract

        valid = """
const filtered = useMemo(() => personalizedEvents
  .filter(({ event }) => (filter === 'all' || event.category === filter)
    && (marketFilter === 'all' || event.market === marketFilter)
    && (!unreadActive || unseenEventIds.has(event.eventId)))
  .slice(0, 12), [filter, marketFilter, personalizedEvents, unreadActive, unseenEventIds]);
"""
        self.assertTrue(filter_contract(valid).ok)
        self.assertFalse(filter_contract(valid.replace("unseenEventIds.has(event.eventId)", "true")).ok)
        self.assertFalse(filter_contract(valid + "\nmarkEventsSeen(events)").ok)

    def test_regression_contract_requires_returning_visitor_and_empty_state_tests(self) -> None:
        from scripts.verify_platform_returning_event_inbox_v131 import regression_tests_contract

        valid = """
lets returning visitors read only new events without changing read state
shows an honest new-event empty state and can return to all events
MARKET_EVENT_SEEN_STORAGE_KEY
getByRole('button', { name: '只看新增' })
getByRole('button', { name: '查看全部事件' })
"""
        self.assertTrue(regression_tests_contract(valid).ok)
        self.assertFalse(regression_tests_contract(valid.replace("without changing read state", "")).ok)

    def test_bundle_must_be_fresh_and_under_homepage_limit(self) -> None:
        from scripts.verify_platform_returning_event_inbox_v131 import homepage_bundle_check

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

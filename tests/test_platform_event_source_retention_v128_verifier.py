from __future__ import annotations

import unittest


class EventSourceRetentionV128VerifierTestCase(unittest.TestCase):
    def test_backend_contract_requires_bounded_distinct_source_aggregation(self) -> None:
        from scripts.verify_platform_event_source_retention_v128 import backend_source_contract

        valid = """
events_by_title = {}
source_refs_by_title = {}
existing = events_by_title.get(title_key)
if existing is not None:
    source_refs = source_refs_by_title[title_key]
    if source_ref not in source_refs and len(source_refs) < 20:
        existing['source_count'] = len(source_refs)
        if source_publisher not in publishers and len(publishers) < 8:
            publishers.append(source_publisher)
source_ref, source_publisher = self._source_reference(headline, source_state)
'source_publishers': [source_publisher]
"""
        self.assertTrue(backend_source_contract(valid).ok)
        self.assertFalse(backend_source_contract(valid.replace("len(source_refs) < 20", "True")).ok)
        self.assertFalse(backend_source_contract(valid + "\nimport httpx").ok)

    def test_api_contract_requires_safe_source_defaults(self) -> None:
        from scripts.verify_platform_event_source_retention_v128 import api_source_contract

        schema = """
source_count: int = Field(1, ge=1, le=20)
source_publishers: List[str] = Field(default_factory=list, max_length=8)
"""
        frontend = """
sourceCount: number;
sourcePublishers: string[];
Number.isFinite(event.sourceCount)
Array.isArray(event.sourcePublishers)
[event.publisher]
"""
        self.assertTrue(api_source_contract(schema, frontend).ok)
        self.assertFalse(api_source_contract(schema.replace("le=20", "le=200"), frontend).ok)
        self.assertFalse(api_source_contract(schema, frontend.replace("[event.publisher]", "[]")).ok)

    def test_local_storage_contract_is_bounded_and_non_sensitive(self) -> None:
        from scripts.verify_platform_event_source_retention_v128 import read_state_contract

        valid = """
MARKET_EVENT_SEEN_STORAGE_KEY = 'dsa.marketEvents.seen.v1'
const MAX_SEEN_EVENT_IDS = 200;
return typeof window === 'undefined' ? null : window.localStorage;
JSON.parse(raw)
JSON.stringify(normalized)
getUnseenMarketEventIds
mergeSeenMarketEventIds
"""
        self.assertTrue(read_state_contract(valid).ok)
        self.assertFalse(read_state_contract(valid.replace("200", "2000")).ok)
        self.assertFalse(read_state_contract(valid + "\nemail apiKey title url").ok)

    def test_frontend_contract_requires_bilingual_new_and_source_copy(self) -> None:
        from scripts.verify_platform_event_source_retention_v128 import frontend_retention_contract

        valid = """
loadSeenMarketEventIds getUnseenMarketEventIds mergeSeenMarketEventIds saveSeenMarketEventIds
sourceCount sourcePublishers markAllRead unseenEventIds
新事件 新增 全部标为已读 条公开来源记录 多条来源记录不代表事实已独立证实。
New event new Mark all as read public source record Multiple source records do not mean the facts were independently verified.
仅提供公开资讯和数据，不构成投资建议。
Public information and data only. Not investment advice.
"""
        self.assertTrue(frontend_retention_contract(valid).ok)
        self.assertFalse(frontend_retention_contract(valid.replace("全部标为已读", "")).ok)
        self.assertFalse(frontend_retention_contract(valid + "\n目标价").ok)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class EventSourceEvidenceV129VerifierTestCase(unittest.TestCase):
    def test_backend_contract_requires_bounded_safe_source_records_without_network_or_ai(self) -> None:
        from scripts.verify_platform_event_source_evidence_v129 import backend_source_record_contract

        valid = """
source_record = self._source_record(headline, source_state, as_of)
source_records = existing["source_records"]
if len(source_records) < 8:
    source_records.append(source_record)
"source_records": [source_record]
def _safe_http_url(value):
    parsed = urlparse(url)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        return None
def _source_record(headline, source_state, as_of):
    return {"publisher": publisher, "source": source, "url": cls._safe_http_url(headline.get("url")), "event_time": published_at or as_of, "time_kind": "published"}
"""
        self.assertTrue(backend_source_record_contract(valid).ok)
        self.assertFalse(backend_source_record_contract(valid.replace("len(source_records) < 8", "True")).ok)
        self.assertFalse(backend_source_record_contract(valid + "\nimport httpx").ok)

    def test_api_contract_requires_bounded_defaults_safe_urls_and_legacy_mapping(self) -> None:
        from scripts.verify_platform_event_source_evidence_v129 import api_source_record_contract

        schema = """
class PublicMarketEventSourceRecord(StrictModel):
    publisher: str
    source: str
    url: Optional[str] = None
    event_time: str
    time_kind: MarketEventTimeKind
source_records: List[PublicMarketEventSourceRecord] = Field(default_factory=list, max_length=8)
"""
        frontend = """
sourceRecords: PublicMarketEventSourceRecord[];
function safeHttpUrl(value: unknown)
function normalizeEventSourceRecords(event: PublicMarketEvent)
Array.isArray(event.sourceRecords)
publisher: event.publisher ?? event.sourceState?.source
url: safeHttpUrl(event.url)
if (records.length >= 8) break;
"""
        self.assertTrue(api_source_record_contract(schema, frontend).ok)
        self.assertFalse(api_source_record_contract(schema.replace("max_length=8", "max_length=80"), frontend).ok)
        self.assertFalse(api_source_record_contract(schema, frontend.replace("safeHttpUrl(event.url)", "event.url")).ok)

    def test_frontend_contract_requires_bilingual_disclosure_and_careful_claims(self) -> None:
        from scripts.verify_platform_event_source_evidence_v129 import frontend_source_evidence_contract

        valid = """
expandedEventId aria-expanded aria-controls sourceRecords safeSourceLink
查看来源 收起来源 已显示 原文链接不可用 多条来源记录不代表事实已独立证实。
View sources Hide sources Showing Original link unavailable
Multiple source records do not mean the facts were independently verified.
仅提供公开资讯和数据，不构成投资建议。
Public information and data only. Not investment advice.
"""
        self.assertTrue(frontend_source_evidence_contract(valid).ok)
        self.assertFalse(frontend_source_evidence_contract(valid.replace("aria-expanded", "")).ok)
        self.assertFalse(frontend_source_evidence_contract(valid + "\n目标价").ok)

    def test_homepage_bundle_must_be_newer_than_v129_sources(self) -> None:
        from scripts.verify_platform_event_source_evidence_v129 import homepage_bundle_check

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

    def test_regression_contract_requires_unsafe_link_scoring_assertion(self) -> None:
        from scripts.verify_platform_event_source_evidence_v129 import regression_tests_contract

        backend = """
test_source_records_remove_non_http_links
events[0]["source_records"]
self.assertNotIn("source_link", events[0]["relevance_reasons"])
"""
        api = "sourceRecords javascript:alert(document.domain)"
        component = """
expands source evidence on demand with bilingual safe links
已显示 2 / 共 2 条公开来源记录
Showing 2 of 2 public source records
"""
        self.assertTrue(regression_tests_contract(backend, api, component).ok)
        self.assertFalse(
            regression_tests_contract(
                backend.replace('self.assertNotIn("source_link", events[0]["relevance_reasons"])', ""),
                api,
                component,
            ).ok,
        )


if __name__ == "__main__":
    unittest.main()

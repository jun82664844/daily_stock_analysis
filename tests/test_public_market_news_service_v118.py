# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from unittest.mock import patch


class PublicMarketNewsServiceV118TestCase(unittest.TestCase):
    def test_default_fetch_uses_browser_compatible_header(self) -> None:
        from src.services.public_market_news_service import PublicMarketNewsService

        class Response:
            status_code = 200

            @staticmethod
            def raise_for_status() -> None:
                return None

            @staticmethod
            def iter_content(chunk_size: int):
                del chunk_size
                yield b'{"items":[{"title":"Public headline"}]}'

            @staticmethod
            def close() -> None:
                return None

        with patch("src.services.public_market_news_service.requests.get", return_value=Response()) as request:
            payload = PublicMarketNewsService()._fetch_newsnow("cls-hot")

        self.assertEqual(payload["items"][0]["title"], "Public headline")
        headers = request.call_args.kwargs["headers"]
        self.assertIn("Mozilla/5.0", headers["User-Agent"])

    def test_loads_allowlisted_public_feed_without_model_fields(self) -> None:
        from src.services.public_market_news_service import PublicMarketNewsService

        calls: list[str] = []

        def fetch(source_id: str) -> dict:
            calls.append(source_id)
            return {
                "items": [
                    {
                        "title": "  Market update  ",
                        "url": "https://example.com/story",
                        "pubDate": "2026-07-13T02:00:00Z",
                        "extra": {"info": " Objective public information. "},
                    }
                ]
            }

        service = PublicMarketNewsService(fetcher=fetch, cache_ttl_seconds=300)
        items = service.load("cn")

        self.assertEqual(calls, ["cls-hot"])
        self.assertEqual(items[0]["title"], "Market update")
        self.assertEqual(items[0]["summary"], "Objective public information.")
        self.assertEqual(items[0]["publisher"], "财联社")
        self.assertEqual(items[0]["source"], "public_newsnow_cls_hot")
        self.assertEqual(items[0]["published_at"], "2026-07-13T02:00:00Z")
        self.assertNotIn("ai_used", items[0])
        self.assertNotIn("api_key", items[0])

    def test_market_sources_are_separate_and_results_are_cached(self) -> None:
        from src.services.public_market_news_service import PublicMarketNewsService

        calls: list[str] = []

        def fetch(source_id: str) -> dict:
            calls.append(source_id)
            return {"items": [{"title": source_id, "url": "https://example.com/news"}]}

        service = PublicMarketNewsService(fetcher=fetch, cache_ttl_seconds=300)
        self.assertEqual(service.load("hk")[0]["publisher"], "格隆汇")
        self.assertEqual(service.load("us")[0]["publisher"], "金十数据")
        service.load("hk")

        self.assertEqual(calls, ["gelonghui", "jin10"])

    def test_normalizes_millisecond_publication_timestamp(self) -> None:
        from src.services.public_market_news_service import PublicMarketNewsService

        service = PublicMarketNewsService(fetcher=lambda _source_id: {
            "items": [{"title": "Timed", "url": "https://example.com/timed", "pubDate": "1783952514000"}]
        })

        published_at = service.load("us")[0]["published_at"]
        self.assertEqual(published_at, "2026-07-13T14:21:54+00:00")

    def test_failure_or_unsupported_market_degrades_to_empty_list(self) -> None:
        from src.services.public_market_news_service import PublicMarketNewsService

        service = PublicMarketNewsService(fetcher=lambda _source_id: (_ for _ in ()).throw(RuntimeError("offline")))

        self.assertEqual(service.load("cn"), [])
        self.assertEqual(service.load("crypto"), [])

    def test_rejects_non_http_story_links_and_duplicate_titles(self) -> None:
        from src.services.public_market_news_service import PublicMarketNewsService

        service = PublicMarketNewsService(fetcher=lambda _source_id: {
            "items": [
                {"title": "One", "url": "javascript:alert(1)"},
                {"title": "One", "url": "https://example.com/duplicate"},
                {"title": "Two", "url": "https://example.com/two"},
            ]
        })

        items = service.load("us")
        self.assertEqual([item["title"] for item in items], ["One", "Two"])
        self.assertIsNone(items[0]["url"])


if __name__ == "__main__":
    unittest.main()

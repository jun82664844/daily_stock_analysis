# -*- coding: utf-8 -*-
import unittest

from scripts.verify_platform_local_history_detail_v30 import evaluate_history_detail_v30_summary


class PlatformLocalHistoryDetailV30VerifierTestCase(unittest.TestCase):
    def test_evaluate_history_detail_v30_summary_accepts_complete_shape(self) -> None:
        summary = {
            "backend": {
                "owner_scoped_list": True,
                "existing_list_reuse": True,
                "no_new_endpoint": True,
                "no_ai": True,
            },
            "frontend": {
                "detail_search": True,
                "search_navigation": True,
                "section_jumps": True,
                "section_anchors": True,
                "same_stock_timeline": True,
                "no_ai_guard": True,
                "frontend_test": True,
            },
            "docs": {
                "local_only": True,
                "no_real_payment": True,
                "no_real_api_key": True,
                "no_delete_data": True,
                "not_investment_advice": True,
            },
        }

        self.assertEqual(evaluate_history_detail_v30_summary(summary), [])

    def test_evaluate_history_detail_v30_summary_rejects_missing_boundaries(self) -> None:
        summary = {
            "backend": {
                "owner_scoped_list": False,
                "existing_list_reuse": False,
                "no_new_endpoint": False,
                "no_ai": False,
            },
            "frontend": {
                "detail_search": False,
                "search_navigation": False,
                "section_jumps": False,
                "section_anchors": False,
                "same_stock_timeline": False,
                "no_ai_guard": False,
                "frontend_test": False,
            },
            "docs": {
                "local_only": True,
                "no_real_payment": True,
                "no_real_api_key": False,
                "no_delete_data": False,
                "not_investment_advice": True,
            },
        }

        problems = evaluate_history_detail_v30_summary(summary)
        self.assertIn("backend:owner_scoped_list_missing", problems)
        self.assertIn("backend:existing_list_reuse_missing", problems)
        self.assertIn("backend:no_new_endpoint_missing", problems)
        self.assertIn("backend:no_ai_missing", problems)
        self.assertIn("frontend:detail_search_missing", problems)
        self.assertIn("frontend:search_navigation_missing", problems)
        self.assertIn("frontend:section_jumps_missing", problems)
        self.assertIn("frontend:section_anchors_missing", problems)
        self.assertIn("frontend:same_stock_timeline_missing", problems)
        self.assertIn("frontend:no_ai_guard_missing", problems)
        self.assertIn("frontend:test_missing", problems)
        self.assertIn("docs:no_real_api_key_missing", problems)
        self.assertIn("docs:no_delete_data_missing", problems)


if __name__ == "__main__":
    unittest.main()

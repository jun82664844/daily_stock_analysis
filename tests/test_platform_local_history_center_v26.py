import unittest

from scripts.verify_platform_local_history_center_v26 import evaluate_history_center_v26_summary


class LocalHistoryCenterV26VerifierTestCase(unittest.TestCase):
    def test_evaluate_accepts_filter_persistence_and_total_summary(self):
        summary = {
            "frontend": {
                "storage_key": True,
                "safe_storage_read": True,
                "safe_storage_write": True,
                "restored_filters_applied": True,
                "backend_total_in_store": True,
                "history_list_total_count": True,
                "frontend_test": True,
            },
            "docs": {
                "local_only": True,
                "no_real_payment": True,
                "not_investment_advice": True,
            },
        }

        self.assertEqual(evaluate_history_center_v26_summary(summary), [])

    def test_evaluate_reports_missing_total_count_wiring(self):
        summary = {
            "frontend": {
                "storage_key": True,
                "safe_storage_read": True,
                "safe_storage_write": True,
                "restored_filters_applied": True,
                "backend_total_in_store": True,
                "history_list_total_count": False,
                "frontend_test": True,
            },
            "docs": {
                "local_only": True,
                "no_real_payment": True,
                "not_investment_advice": True,
            },
        }

        self.assertIn(
            "frontend:history_list_total_count_missing",
            evaluate_history_center_v26_summary(summary),
        )


if __name__ == "__main__":
    unittest.main()

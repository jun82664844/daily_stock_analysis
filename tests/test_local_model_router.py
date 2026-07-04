import unittest

from src.llm.local_model_router import LocalModelRouter


class LocalModelRouterTestCase(unittest.TestCase):
    def test_router_rejects_when_concurrency_is_full(self):
        router = LocalModelRouter(
            enabled=True,
            max_concurrent=1,
            base_url="http://127.0.0.1:11434/v1",
        )

        first = router.try_acquire()
        second = router.try_acquire()

        self.assertTrue(first.acquired)
        self.assertFalse(second.acquired)
        self.assertEqual(second.reason, "local_model_busy")
        first.release()

    def test_router_disabled_returns_clear_reason(self):
        router = LocalModelRouter(enabled=False, max_concurrent=1, base_url="")

        ticket = router.try_acquire()

        self.assertFalse(ticket.acquired)
        self.assertEqual(ticket.reason, "local_model_disabled")

    def test_router_missing_base_url_returns_clear_reason(self):
        router = LocalModelRouter(enabled=True, max_concurrent=1, base_url="")

        ticket = router.try_acquire()

        self.assertFalse(ticket.acquired)
        self.assertEqual(ticket.reason, "local_model_missing_base_url")

import unittest
from types import SimpleNamespace


class OllamaRuntimeServiceV107TestCase(unittest.TestCase):
    def test_disabled_runtime_reports_disabled_without_network_probe(self) -> None:
        from src.services.ollama_runtime_service import OllamaRuntimeService

        calls = []
        service = OllamaRuntimeService(
            environ={"LOCAL_LLM_ENABLED": "false"},
            json_getter=lambda *_args, **_kwargs: calls.append(True),
        )

        status = service.get_status()

        self.assertFalse(status["enabled"])
        self.assertFalse(status["ready"])
        self.assertEqual(status["reason"], "local_model_disabled")
        self.assertEqual(calls, [])

    def test_ready_runtime_reports_configured_models_without_exposing_base_url(self) -> None:
        from src.services.ollama_runtime_service import OllamaRuntimeService

        def fake_get(url: str, _timeout: float):
            if url.endswith("/api/version"):
                return {"version": "test"}
            if url.endswith("/api/tags"):
                return {"models": [{"name": "quick-model:latest"}, {"name": "deep-model:latest"}]}
            raise AssertionError(url)

        service = OllamaRuntimeService(
            environ={
                "LOCAL_LLM_ENABLED": "true",
                "LOCAL_LLM_BASE_URL": "http://127.0.0.1:11434/v1",
                "LOCAL_LLM_QUICK_MODEL": "quick-model:latest",
                "LOCAL_LLM_DEEP_MODEL": "deep-model:latest",
                "LOCAL_LLM_MAX_CONCURRENT": "1",
            },
            json_getter=fake_get,
        )

        status = service.get_status()

        self.assertTrue(status["enabled"])
        self.assertTrue(status["reachable"])
        self.assertTrue(status["ready"])
        self.assertEqual(status["reason"], "ready")
        self.assertEqual(status["quick_model"], "quick-model:latest")
        self.assertEqual(status["deep_model"], "deep-model:latest")
        self.assertNotIn("base_url", status)
        self.assertNotIn("11434", str(status))

    def test_missing_deep_model_is_reported_without_disabling_quick_lane(self) -> None:
        from src.services.ollama_runtime_service import OllamaRuntimeService

        service = OllamaRuntimeService(
            environ={
                "LOCAL_LLM_ENABLED": "true",
                "LOCAL_LLM_BASE_URL": "http://127.0.0.1:11434/v1",
                "LOCAL_LLM_QUICK_MODEL": "quick-model",
                "LOCAL_LLM_DEEP_MODEL": "deep-model",
            },
            json_getter=lambda url, _timeout: (
                {"version": "test"}
                if url.endswith("/api/version")
                else {"models": [{"name": "quick-model:latest"}]}
            ),
        )

        status = service.get_status()

        self.assertTrue(status["quick_model_available"])
        self.assertFalse(status["deep_model_available"])
        self.assertTrue(status["quick_ready"])
        self.assertFalse(status["deep_ready"])
        self.assertEqual(status["reason"], "local_model_missing_deep_model")

    def test_configure_analysis_isolates_ollama_from_remote_fallbacks(self) -> None:
        from src.services.ollama_runtime_service import OllamaRuntimeService

        service = OllamaRuntimeService(
            environ={
                "LOCAL_LLM_ENABLED": "true",
                "LOCAL_LLM_BASE_URL": "http://127.0.0.1:11434/v1",
                "LOCAL_LLM_QUICK_MODEL": "quick-model",
                "LOCAL_LLM_DEEP_MODEL": "deep-model",
            },
        )
        original = SimpleNamespace(
            litellm_model="remote/model",
            litellm_fallback_models=["remote/fallback"],
            llm_model_list=[],
            agent_litellm_model="remote/agent",
        )

        quick = service.configure_analysis(original, analysis_depth="fast")
        deep = service.configure_analysis(original, analysis_depth="deep")

        self.assertEqual(quick.litellm_model, "ollama/quick-model")
        self.assertEqual(deep.litellm_model, "ollama/deep-model")
        self.assertEqual(quick.litellm_fallback_models, [])
        self.assertEqual(quick.agent_litellm_model, "ollama/quick-model")
        self.assertEqual(quick.llm_model_list[0]["litellm_params"]["model"], "ollama/quick-model")
        self.assertTrue(quick.informational_only_mode)
        self.assertEqual(original.litellm_model, "remote/model")


if __name__ == "__main__":
    unittest.main()

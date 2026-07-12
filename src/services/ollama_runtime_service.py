# -*- coding: utf-8 -*-
"""Safe runtime configuration and diagnostics for the optional Ollama lane."""

from __future__ import annotations

import copy
import json
import os
from threading import RLock
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


_TRUE_VALUES = {"1", "true", "yes", "on"}
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _env_bool(environ: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE_VALUES


def _env_int(environ: Mapping[str, str], name: str, default: int, minimum: int = 1) -> int:
    try:
        value = int(environ.get(name, str(default)) or str(default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _env_float(environ: Mapping[str, str], name: str, default: float, minimum: float = 0.1) -> float:
    try:
        value = float(environ.get(name, str(default)) or str(default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _ollama_model_name(value: str) -> str:
    model = (value or "").strip()
    return model[7:] if model.lower().startswith("ollama/") else model


def _wire_model(value: str) -> str:
    model = _ollama_model_name(value)
    return f"ollama/{model}" if model else ""


def _canonical_tag(value: str) -> str:
    model = _ollama_model_name(value).strip().lower()
    return model[:-7] if model.endswith(":latest") else model


class OllamaRuntimeService:
    """Resolve one local Ollama runtime without leaking connection details."""

    def __init__(
        self,
        *,
        environ: Mapping[str, str] | None = None,
        json_getter: Callable[[str, float], Any] | None = None,
    ) -> None:
        self.environ = environ if environ is not None else os.environ
        self._json_getter = json_getter or self._get_json
        self.enabled = _env_bool(self.environ, "LOCAL_LLM_ENABLED", False)
        self.base_url = (self.environ.get("LOCAL_LLM_BASE_URL") or "").strip().rstrip("/")
        legacy_model = (self.environ.get("LOCAL_LLM_MODEL") or "").strip()
        self.quick_model = _ollama_model_name(
            self.environ.get("LOCAL_LLM_QUICK_MODEL") or legacy_model
        )
        self.deep_model = _ollama_model_name(
            self.environ.get("LOCAL_LLM_DEEP_MODEL") or self.quick_model
        )
        self.max_concurrent = _env_int(self.environ, "LOCAL_LLM_MAX_CONCURRENT", 1)
        self.timeout_sec = _env_float(self.environ, "LOCAL_LLM_TIMEOUT_SEC", 90.0)
        self.probe_timeout_sec = _env_float(self.environ, "LOCAL_LLM_PROBE_TIMEOUT_SEC", 2.0)
        self.allow_remote = _env_bool(self.environ, "LOCAL_LLM_ALLOW_REMOTE", False)

    @staticmethod
    def _get_json(url: str, timeout: float) -> Any:
        request = Request(url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _native_origin(self) -> str:
        parsed = urlsplit(self.base_url)
        path = parsed.path.rstrip("/")
        if path.endswith("/v1"):
            path = path[:-3]
        return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")

    def _base_url_is_allowed(self) -> bool:
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        return self.allow_remote or parsed.hostname.lower() in _LOOPBACK_HOSTS

    def model_for_depth(self, analysis_depth: str) -> str:
        is_deep = (analysis_depth or "fast").strip().lower() == "deep"
        return self.deep_model if is_deep else self.quick_model

    def get_status(self) -> dict[str, Any]:
        base = {
            "enabled": self.enabled,
            "reachable": False,
            "ready": False,
            "quick_ready": False,
            "deep_ready": False,
            "reason": "local_model_disabled",
            "runtime": "ollama",
            "quick_model": self.quick_model or None,
            "deep_model": self.deep_model or None,
            "quick_model_available": False,
            "deep_model_available": False,
            "max_concurrent": self.max_concurrent,
        }
        if not self.enabled:
            return base
        if not self.base_url:
            return {**base, "reason": "local_model_missing_base_url"}
        if not self._base_url_is_allowed():
            return {**base, "reason": "local_model_unsafe_base_url"}
        if not self.quick_model:
            return {**base, "reason": "local_model_missing_quick_model"}
        if not self.deep_model:
            return {**base, "reason": "local_model_missing_deep_model"}

        origin = self._native_origin()
        try:
            self._json_getter(f"{origin}/api/version", self.probe_timeout_sec)
            tags_payload = self._json_getter(f"{origin}/api/tags", self.probe_timeout_sec)
        except Exception:
            return {**base, "reason": "local_model_unreachable"}

        models = tags_payload.get("models", []) if isinstance(tags_payload, dict) else []
        available = {
            _canonical_tag(str(item.get("name") or item.get("model") or ""))
            for item in models
            if isinstance(item, dict)
        }
        quick_available = _canonical_tag(self.quick_model) in available
        deep_available = _canonical_tag(self.deep_model) in available
        if not quick_available:
            reason = "local_model_missing_quick_model"
        elif not deep_available:
            reason = "local_model_missing_deep_model"
        else:
            reason = "ready"
        return {
            **base,
            "reachable": True,
            "ready": quick_available and deep_available,
            "quick_ready": quick_available,
            "deep_ready": deep_available,
            "reason": reason,
            "quick_model_available": quick_available,
            "deep_model_available": deep_available,
        }

    def readiness_reason(self, analysis_depth: str, *, status: dict[str, Any] | None = None) -> str:
        runtime_status = status or self.get_status()
        is_deep = (analysis_depth or "fast").strip().lower() == "deep"
        lane = "deep_ready" if is_deep else "quick_ready"
        return "ready" if runtime_status.get(lane) else str(
            runtime_status.get("reason") or "local_model_unavailable"
        )

    def configure_analysis(self, config: Any, *, analysis_depth: str) -> Any:
        """Return an isolated Ollama-only config for one request."""
        scoped = copy.copy(config)
        model = _wire_model(self.model_for_depth(analysis_depth))
        if not model:
            raise ValueError("local_model_missing_model")
        scoped.litellm_model = model
        scoped.agent_litellm_model = model
        scoped.litellm_fallback_models = []
        scoped.llm_channels = []
        scoped.llm_channel_names = ["ollama"]
        scoped.llm_models_source = "local_ollama"
        scoped.llm_model_list = [
            {
                "model_name": model,
                "litellm_params": {
                    "model": model,
                    "api_base": self._native_origin(),
                    "timeout": self.timeout_sec,
                },
            }
        ]
        scoped.gemini_request_delay = 0.0
        scoped.informational_only_mode = True
        return scoped


_DEFAULT_SERVICE: OllamaRuntimeService | None = None
_DEFAULT_SERVICE_SIGNATURE: tuple[str, ...] | None = None
_DEFAULT_SERVICE_LOCK = RLock()


def get_ollama_runtime_service() -> OllamaRuntimeService:
    names = (
        "LOCAL_LLM_ENABLED",
        "LOCAL_LLM_BASE_URL",
        "LOCAL_LLM_MODEL",
        "LOCAL_LLM_QUICK_MODEL",
        "LOCAL_LLM_DEEP_MODEL",
        "LOCAL_LLM_MAX_CONCURRENT",
        "LOCAL_LLM_TIMEOUT_SEC",
        "LOCAL_LLM_PROBE_TIMEOUT_SEC",
        "LOCAL_LLM_ALLOW_REMOTE",
    )
    signature = tuple(os.getenv(name, "") for name in names)
    global _DEFAULT_SERVICE, _DEFAULT_SERVICE_SIGNATURE
    with _DEFAULT_SERVICE_LOCK:
        if _DEFAULT_SERVICE is None or _DEFAULT_SERVICE_SIGNATURE != signature:
            _DEFAULT_SERVICE = OllamaRuntimeService()
            _DEFAULT_SERVICE_SIGNATURE = signature
        return _DEFAULT_SERVICE

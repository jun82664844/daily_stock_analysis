# -*- coding: utf-8 -*-
"""Concurrency gate for optional local OpenAI-compatible LLM servers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from threading import BoundedSemaphore, RLock


@dataclass
class LocalModelTicket:
    acquired: bool
    reason: str = ""
    _semaphore: BoundedSemaphore | None = None

    def release(self) -> None:
        if self.acquired and self._semaphore is not None:
            self._semaphore.release()
            self.acquired = False


class LocalModelRouter:
    def __init__(self, *, enabled: bool, max_concurrent: int, base_url: str):
        self.enabled = bool(enabled)
        self.base_url = (base_url or "").strip()
        self._semaphore = BoundedSemaphore(max(1, int(max_concurrent or 1)))

    def try_acquire(self) -> LocalModelTicket:
        if not self.enabled:
            return LocalModelTicket(False, "local_model_disabled")
        if not self.base_url:
            return LocalModelTicket(False, "local_model_missing_base_url")
        if not self._semaphore.acquire(blocking=False):
            return LocalModelTicket(False, "local_model_busy")
        return LocalModelTicket(True, "", self._semaphore)


_DEFAULT_ROUTER: LocalModelRouter | None = None
_DEFAULT_ROUTER_CONFIG: tuple[bool, int, str] | None = None
_DEFAULT_ROUTER_LOCK = RLock()


def get_default_local_model_router() -> LocalModelRouter:
    enabled = os.getenv("LOCAL_LLM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1").strip()
    try:
        max_concurrent = int(os.getenv("LOCAL_LLM_MAX_CONCURRENT", "4") or "4")
    except ValueError:
        max_concurrent = 4
    config = (enabled, max(1, max_concurrent), base_url)
    global _DEFAULT_ROUTER, _DEFAULT_ROUTER_CONFIG
    with _DEFAULT_ROUTER_LOCK:
        if _DEFAULT_ROUTER is None or _DEFAULT_ROUTER_CONFIG != config:
            _DEFAULT_ROUTER = LocalModelRouter(
                enabled=enabled,
                max_concurrent=max_concurrent,
                base_url=base_url,
            )
            _DEFAULT_ROUTER_CONFIG = config
        return _DEFAULT_ROUTER

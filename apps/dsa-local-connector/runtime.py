from __future__ import annotations

import os
import platform
from typing import Any
from urllib.parse import urlparse

from client import ConnectorClient
from ollama import OllamaClient


SERVICE_NAME = "DSA Local Connector"
TOKEN_ACCOUNT = "device-token"


def configured_server_url() -> str:
    value = os.getenv("DSA_CONNECTOR_SERVER_URL", "http://127.0.0.1:8018").strip().rstrip("/")
    parsed = urlparse(value)
    is_loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme == "https" and parsed.hostname:
        return value
    if parsed.scheme == "http" and is_loopback:
        return value
    raise ValueError("connector_https_or_loopback_required")


class CredentialStore:
    def __init__(self, keyring_module: Any | None = None) -> None:
        if keyring_module is None:
            import keyring as keyring_module
        self.keyring = keyring_module

    def save_token(self, token: str) -> None:
        self.keyring.set_password(SERVICE_NAME, TOKEN_ACCOUNT, token)

    def load_token(self) -> str | None:
        return self.keyring.get_password(SERVICE_NAME, TOKEN_ACCOUNT)

    def clear_token(self) -> None:
        try:
            self.keyring.delete_password(SERVICE_NAME, TOKEN_ACCOUNT)
        except Exception:
            pass


class ConnectorRuntime:
    def __init__(
        self,
        *,
        client: ConnectorClient | None = None,
        ollama: OllamaClient | None = None,
        credential_store: CredentialStore | None = None,
        base_url: str | None = None,
    ) -> None:
        self.base_url = base_url or configured_server_url()
        self.credentials = credential_store
        self.ollama = ollama or OllamaClient()
        self.client = client

    @staticmethod
    def device_name() -> str:
        return f"{platform.system()} {platform.machine()}"[:128]

    def pair(self, pairing_code: str) -> dict:
        payload = ConnectorClient.claim(self.base_url, pairing_code, self.device_name())
        token = str(payload["device_token"])
        if self.credentials is None:
            self.credentials = CredentialStore()
        self.credentials.save_token(token)
        self.client = ConnectorClient(self.base_url, token)
        return {"connector_id": int(payload["connector_id"]), "status": payload["status"]}

    def restore(self) -> bool:
        if self.credentials is None:
            self.credentials = CredentialStore()
        token = self.credentials.load_token()
        if not token:
            return False
        self.client = ConnectorClient(self.base_url, token)
        return True

    def process_once(self) -> dict[str, Any]:
        if self.client is None:
            return {"status": "disconnected", "model_count": 0, "processed_job": False}
        models = self.ollama.discover_models()
        if not models:
            return {"status": "ollama_unavailable", "model_count": 0, "processed_job": False}
        self.client.heartbeat(models)
        job = self.client.next_job()
        processed = False
        if job:
            try:
                response = self.ollama.generate(
                    str(job["model"]),
                    str((job.get("request") or {}).get("prompt") or ""),
                )
                diagnostics = {
                    key: response[key]
                    for key in ("done_reason", "total_duration_ms", "eval_count", "eval_duration_ms")
                    if key in response
                }
                self.client.complete(
                    str(job["job_id"]),
                    {
                        "text": str(response.get("response") or ""),
                        "diagnostics": diagnostics,
                    },
                )
            except Exception:
                self.client.complete(
                    str(job["job_id"]),
                    {"text": "", "diagnostics": {}, "error": "ollama_generation_failed"},
                )
            processed = True
        return {"status": "connected", "model_count": len(models), "processed_job": processed}

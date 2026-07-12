from __future__ import annotations

import time
import requests


class ConnectorClient:
    BACKOFF_SECONDS = (1, 2, 5, 10, 30)

    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    @classmethod
    def claim(cls, base_url: str, pairing_code: str, device_name: str) -> dict:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/v1/local-connector/claim",
            json={"pairing_code": pairing_code, "device_name": device_name},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def heartbeat(self, models: list[str]) -> dict:
        response = requests.post(f"{self.base_url}/api/v1/local-connector/heartbeat", json={"models": models}, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def next_job(self) -> dict | None:
        response = requests.get(f"{self.base_url}/api/v1/local-connector/jobs/next", params={"wait_seconds": 25}, headers=self.headers, timeout=35)
        response.raise_for_status()
        return response.json() or None

    def complete(self, job_id: str, result: dict) -> None:
        response = requests.post(f"{self.base_url}/api/v1/local-connector/jobs/{job_id}/complete", json={"result": result}, headers=self.headers, timeout=20)
        response.raise_for_status()

    @classmethod
    def sleep_for_attempt(cls, attempt: int) -> None:
        time.sleep(cls.BACKOFF_SECONDS[min(max(0, attempt), len(cls.BACKOFF_SECONDS) - 1)])

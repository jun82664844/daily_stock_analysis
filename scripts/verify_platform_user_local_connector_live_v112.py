from __future__ import annotations

import argparse
import sys
import threading
import time
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
CONNECTOR_ROOT = ROOT / "apps" / "dsa-local-connector"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8018")
    parser.add_argument("--stock-code", default="AAPL")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(CONNECTOR_ROOT))
    from ollama import OllamaClient
    from runtime import ConnectorRuntime
    from src.platform_accounts import PlatformAccountService

    base_url = args.base_url.rstrip("/")
    session = requests.Session()
    email = f"e2e+v112-live-{uuid.uuid4().hex[:10]}@example.com"
    password = f"V112-{uuid.uuid4().hex}!"
    registered = session.post(
        f"{base_url}/api/v1/platform/register",
        json={"email": email, "password": password},
        timeout=15,
    )
    registered.raise_for_status()
    user_id = int(registered.json()["user"]["id"])
    PlatformAccountService().set_user_plan(user_id, "plus")

    csrf = session.cookies.get("dsa_csrf_token")
    if not csrf:
        raise RuntimeError("csrf_cookie_missing")
    headers = {"X-DSA-CSRF": csrf}
    pairing = session.post(
        f"{base_url}/api/v1/platform/local-connectors/pairing-code",
        headers=headers,
        timeout=15,
    )
    pairing.raise_for_status()

    class MemoryCredentials:
        token: str | None = None

        def save_token(self, token: str) -> None:
            self.token = token

        def load_token(self) -> str | None:
            return self.token

        def clear_token(self) -> None:
            self.token = None

    runtime = ConnectorRuntime(
        base_url=base_url,
        credential_store=MemoryCredentials(),
        ollama=OllamaClient(),
    )
    claim = runtime.pair(pairing.json()["code"])
    models = runtime.ollama.discover_models()
    runtime.client.heartbeat(models)

    options_response = session.get(f"{base_url}/api/v1/platform/model-options", timeout=15)
    options_response.raise_for_status()
    local_options = [
        item for item in options_response.json()["options"] if item["source"] == "user_local"
    ]
    if not local_options:
        raise RuntimeError("user_local_option_missing")

    account_before = session.get(f"{base_url}/api/v1/platform/account", timeout=15).json()
    local_before = next(
        item for item in account_before["quota_buckets"] if item["quota_bucket"] == "ai_local"
    )["remaining"]
    stop = threading.Event()
    worker_errors: list[str] = []

    def worker() -> None:
        while not stop.is_set():
            try:
                state = runtime.process_once()
                if state.get("processed_job"):
                    return
            except Exception as exc:  # pragma: no cover - reported by live verifier
                worker_errors.append(type(exc).__name__)
                time.sleep(0.5)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    started = time.perf_counter()
    try:
        analysis = session.post(
            f"{base_url}/api/v1/analysis/analyze",
            headers=headers,
            json={
                "stock_code": args.stock_code,
                "async_mode": False,
                "analysis_depth": "fast",
                "api_key_mode": "user_local",
                "modelOptionId": local_options[0]["option_id"],
                "report_language": "zh",
                "notify": False,
            },
            timeout=180,
        )
    finally:
        stop.set()
        thread.join(timeout=2)
    elapsed = time.perf_counter() - started
    analysis.raise_for_status()
    summary = analysis.json()["report"]["summary"]
    serialized = str(summary)
    for forbidden in ("买入", "卖出", "目标价", "止损", "止盈"):
        if forbidden in serialized:
            raise RuntimeError(f"prohibited_output:{forbidden}")

    account_after = session.get(f"{base_url}/api/v1/platform/account", timeout=15).json()
    local_after = next(
        item for item in account_after["quota_buckets"] if item["quota_bucket"] == "ai_local"
    )["remaining"]
    if local_before is not None and local_after != local_before - 1:
        raise RuntimeError(f"local_quota_mismatch:{local_before}->{local_after}")
    if worker_errors:
        raise RuntimeError(f"connector_worker_errors:{','.join(worker_errors)}")

    print(
        "LIVE_USER_LOCAL_CONNECTOR_V112_OK "
        f"user_id={user_id} connector_id={claim['connector_id']} "
        f"models={len(models)} options={len(local_options)} http={analysis.status_code} "
        f"elapsed_sec={elapsed:.2f} quota={local_before}->{local_after} "
        f"boundary={summary.get('operation_advice')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

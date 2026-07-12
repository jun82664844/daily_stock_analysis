from __future__ import annotations

import json
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("ollama_loopback_required")
        self.base_url = base_url.rstrip("/")

    def discover_models(self) -> list[str]:
        with urlopen(f"{self.base_url}/api/tags", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return [str(item.get("name")) for item in payload.get("models", []) if item.get("name")]

    def generate(self, model: str, prompt: str) -> dict:
        body = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.2, "num_predict": 512},
        }).encode("utf-8")
        request = Request(f"{self.base_url}/api/generate", data=body, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))

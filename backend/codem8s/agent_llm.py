from __future__ import annotations
import json, os, urllib.request
from typing import Any

def chat_json(system: str, user: str, temperature: float = 0.2) -> dict[str, Any] | None:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
            return json.loads(data["choices"][0]["message"]["content"])
    except Exception:
        return None

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("codem8s.agent_llm")


def chat_json(system: str, user: str, temperature: float = 0.2) -> dict[str, Any] | None:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not key:
        logger.warning("OpenAI generation skipped: OPENAI_API_KEY is not set")
        return None

    payload = {
        "model": model,
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
        with urllib.request.urlopen(req, timeout=90) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:4000]
        logger.error("OpenAI HTTP error model=%s status=%s body=%s", model, exc.code, body)
        return None
    except json.JSONDecodeError as exc:
        logger.error("OpenAI JSON parse error model=%s error=%s", model, exc)
        return None
    except Exception as exc:
        logger.exception("OpenAI generation failed model=%s error=%s", model, exc)
        return None

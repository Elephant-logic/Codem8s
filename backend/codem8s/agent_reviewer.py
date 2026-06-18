from __future__ import annotations

import json
from typing import Any

from .agent_llm import chat_json
from .agent_blueprint import blueprint_from_spec
from .models import ProjectSpec


def review_project_files(spec: ProjectSpec, files: dict[str, str]) -> dict[str, Any] | None:
    blueprint = blueprint_from_spec(spec)
    compact_files = {path: content[:3000] for path, content in files.items()}
    system = """
You are Codem8s Reviewer. Review generated project quality.
Return JSON only:
{
  "ok": boolean,
  "summary": "string",
  "weak_files": [{"path": "string", "reason": "string"}],
  "missing_files": ["string"]
}
Reject basic demos, placeholders, missing game logic, missing pages, weak styling.
"""
    return chat_json(system, json.dumps({"blueprint": blueprint, "files": compact_files}, indent=2), temperature=0.1)

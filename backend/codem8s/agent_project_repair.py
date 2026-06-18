from __future__ import annotations

import json
import re
from typing import Any

from .agent_llm import chat_json
from .agent_blueprint import blueprint_from_spec
from .models import ProjectSpec


BAD_PROJECT_PHRASES = [
    "handle enemy destruction",
    "add score or reward logic",
    "todo",
    "placeholder",
    "your code here",
    "future updates",
    "plan for future",
]


def project_review(spec: ProjectSpec, files: dict[str, str]) -> dict[str, Any] | None:
    blueprint = blueprint_from_spec(spec)
    compact = {path: content[:5000] for path, content in files.items()}
    system = """
You are Codem8s Whole Project Reviewer.
Return JSON only:
{
  "ok": boolean,
  "problems": [{"path": "string", "reason": "string"}],
  "missing_files": ["string"],
  "summary": "string"
}

Check the whole generated app, not files alone.
Reject if:
- files duplicate main logic instead of working together
- imports do not match
- a file calls functions not defined/imported
- comments say TODO/handle this/add later/future updates
- game logic is split badly or incomplete
- React app cannot run
- style is too basic for the requested app
"""
    return chat_json(system, json.dumps({"blueprint": blueprint, "files": compact}, indent=2), temperature=0.1)


def repair_project_file(spec: ProjectSpec, path: str, files: dict[str, str], reason: str) -> str | None:
    blueprint = blueprint_from_spec(spec)
    compact = {p: c[:5000] for p, c in files.items()}
    system = """
You are Codem8s Whole Project Repair.
Return JSON only: {"content": "full replacement file contents"}

Repair exactly the requested file so the whole project works together.

Rules:
- No markdown.
- No placeholders.
- No TODO comments.
- No "handle this later".
- No fake functions/classes.
- Keep language correct for file extension.
- Make imports match existing files.
- If game, implement real game state and gameplay, not skeleton comments.
- If React, produce valid React/Vite code.
"""
    payload = {
        "blueprint": blueprint,
        "target_path": path,
        "repair_reason": reason,
        "all_files": compact,
    }
    data = chat_json(system, json.dumps(payload, indent=2), temperature=0.2)
    if data and isinstance(data.get("content"), str):
        return clean(data["content"])
    return None


def clean(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z0-9_+-]*\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip() + "\n"


def has_bad_project_phrase(content: str) -> bool:
    low = content.lower()
    return any(phrase in low for phrase in BAD_PROJECT_PHRASES)


def repair_project(spec: ProjectSpec, files: dict[str, str]) -> dict[str, str]:
    changed = dict(files)

    # Local fast rejection first.
    local_problems = []
    for path, content in changed.items():
        if path.endswith((".js", ".jsx", ".py", ".css")) and has_bad_project_phrase(content):
            local_problems.append({"path": path, "reason": "contains placeholder/future-work/commented incomplete logic"})

    review = project_review(spec, changed)
    problems = local_problems
    if review and isinstance(review.get("problems"), list):
        problems.extend(review["problems"])

    seen = set()
    for problem in problems[:6]:
        path = problem.get("path")
        reason = problem.get("reason", "whole project coherence problem")
        if not path or path in seen or path not in changed:
            continue
        seen.add(path)
        repaired = repair_project_file(spec, path, changed, reason)
        if repaired:
            changed[path] = repaired

    return changed

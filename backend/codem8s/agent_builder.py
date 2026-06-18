from __future__ import annotations

import json
import re
from typing import Any

from .agent_llm import chat_json
from .agent_blueprint import blueprint_from_spec
from .models import ProjectSpec


BASIC_BANNED = [
    "todo", "placeholder", "your code here", "sample only", "demo only",
    "basic example", "square demo", "coming soon", "lorem ipsum",
]


def is_weak_code(path: str, code: str) -> bool:
    low = code.lower()
    if len(code.strip()) < 240 and path.endswith((".jsx", ".js", ".py", ".css")):
        return True
    return any(term in low for term in BASIC_BANNED)


def sanitize_code(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z0-9_+-]*\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip() + "\n"


def build_file_with_api(path: str, spec: ProjectSpec, previous_errors: list[str] | None = None) -> str | None:
    blueprint = blueprint_from_spec(spec)

    system = """
You are Codem8s Builder. Generate ONE complete production-quality file.
Return JSON only with this exact shape:
{"content": "full file contents"}

Rules:
- No markdown.
- No placeholders.
- No TODO comments.
- No "your code here".
- No tiny demo unless the user requested a tiny demo.
- If building a game, implement real gameplay: state, loop, controls, scoring, collision, restart/game-over.
- If building a frontend app, make it visually polished and responsive.
- If building backend, implement working routes and persistence.
- Use only files likely available in the generated project.
- The file must match the requested path exactly.
"""
    user = json.dumps(
        {
            "path": path,
            "blueprint": blueprint,
            "previous_errors": previous_errors or [],
            "quality_bar": "high-end complete app code, not CRUD unless app is actually CRUD",
        },
        indent=2,
    )

    data = chat_json(system, user, temperature=0.25)
    if not data or not isinstance(data.get("content"), str):
        return None

    code = sanitize_code(data["content"])
    if is_weak_code(path, code):
        review_system = """
You are Codem8s Repair. The previous file was too weak/basic.
Return JSON only: {"content": "improved full file contents"}.
Make it complete, specific to the blueprint, and non-placeholder.
"""
        repaired = chat_json(review_system, user + "\nPrevious weak content:\n" + code, temperature=0.25)
        if repaired and isinstance(repaired.get("content"), str):
            code = sanitize_code(repaired["content"])

    return code

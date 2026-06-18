from __future__ import annotations

import json
import posixpath
import re
from typing import Any

from .agent_llm import chat_json
from .agent_blueprint import blueprint_from_spec
from .models import ProjectSpec


BAD_PROJECT_PHRASES = [
    "todo",
    "placeholder",
    "your code here",
    "handle enemy destruction",
    "handle enemy defeat",
    "handle defeat",
    "add score or reward logic",
    "future updates",
    "plan for future",
    "coming soon",
    "demo only",
    "basic example",
]


def clean(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z0-9_+-]*\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip() + "\n"


def has_bad_phrase(content: str) -> bool:
    low = content.lower()
    return any(p in low for p in BAD_PROJECT_PHRASES)


def visible_code_size(files: dict[str, str]) -> int:
    return sum(len(c.strip()) for p, c in files.items() if p.endswith((".js", ".jsx", ".py", ".css")))


def resolve_local_import(from_path: str, import_path: str) -> list[str]:
    base = posixpath.dirname(from_path)
    joined = posixpath.normpath(posixpath.join(base, import_path))
    return [
        joined,
        joined + ".js",
        joined + ".jsx",
        joined + ".css",
        posixpath.join(joined, "index.js"),
        posixpath.join(joined, "index.jsx"),
    ]


def missing_import_problems(files: dict[str, str]) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    existing = set(files.keys())

    for path, content in files.items():
        if not path.endswith((".js", ".jsx")):
            continue

        imports = re.findall(r"from\s+['\"](\.[^'\"]+)['\"]", content)
        imports += re.findall(r"import\s*\(\s*['\"](\.[^'\"]+)['\"]\s*\)", content)

        for imp in imports:
            candidates = resolve_local_import(path, imp)
            if not any(candidate in existing for candidate in candidates):
                problems.append({
                    "path": path,
                    "reason": f"imports missing local file {imp}; existing files do not include any of {candidates}",
                })

    return problems


def local_quality_problems(spec: ProjectSpec, files: dict[str, str]) -> list[dict[str, str]]:
    bp = blueprint_from_spec(spec)
    problems: list[dict[str, str]] = []
    kind = str(bp.get("kind", "")).lower()
    goal = str(bp.get("goal", spec.goal)).lower()
    spec_text = json.dumps(bp).lower()

    problems.extend(missing_import_problems(files))

    for path, content in files.items():
        if path.endswith((".js", ".jsx", ".py", ".css")) and has_bad_phrase(content):
            problems.append({"path": path, "reason": "contains placeholder/basic/future-work wording"})

    size = visible_code_size(files)
    if kind == "game" and size < 9000:
        target = "frontend/src/game/GameCanvas.jsx" if "frontend/src/game/GameCanvas.jsx" in files else "frontend/src/App.jsx"
        problems.append({"path": target, "reason": f"game implementation too small for blueprint ({size} chars); expand real gameplay"})

    combined = "\n".join(files.values()).lower()

    if "tower defense" in goal:
        required_terms = ["wave", "tower", "enemy", "upgrade", "path", "score"]
        missing = [term for term in required_terms if term not in combined]
        if missing:
            problems.append({"path": "frontend/src/game/GameCanvas.jsx", "reason": "tower defense missing required mechanics: " + ", ".join(missing)})

        if "pathfinding" in spec_text and "path" not in combined:
            problems.append({"path": "frontend/src/game/GameCanvas.jsx", "reason": "blueprint asks for pathfinding/path movement but code lacks path logic"})

        if "upgrade" in spec_text and "upgrade" not in combined:
            problems.append({"path": "frontend/src/game/GameCanvas.jsx", "reason": "blueprint asks for upgrades but code lacks upgrade logic"})

        if "spawnenemies" in combined and "setinterval" in combined and "wave" not in combined:
            problems.append({"path": "frontend/src/game/GameCanvas.jsx", "reason": "enemy spawning appears uncontrolled; implement wave-based spawning instead of flooding enemies forever"})

    if "snake" in goal:
        combined_snake = combined.replace("game over", "gameover")
        required_terms = ["food", "score", "collision", "restart", "gameover"]
        missing = [term for term in required_terms if term not in combined_snake]
        if missing:
            problems.append({"path": "frontend/src/game/GameCanvas.jsx", "reason": "snake game missing required mechanics: " + ", ".join(missing)})

    if "frontend/src/styles.css" in files:
        css = files["frontend/src/styles.css"].lower()
        if len(css) < 1800 or ("arial" in css and "linear-gradient" not in css and "box-shadow" not in css):
            problems.append({"path": "frontend/src/styles.css", "reason": "visual design is too basic; create polished responsive app styling"})

    return problems


def project_review(spec: ProjectSpec, files: dict[str, str]) -> dict[str, Any] | None:
    blueprint = blueprint_from_spec(spec)
    compact = {path: content[:7000] for path, content in files.items()}
    system = """
You are Codem8s Whole Project Reviewer.
Return JSON only:
{
  "ok": boolean,
  "problems": [{"path": "string", "reason": "string"}],
  "missing_files": ["string"],
  "summary": "string"
}

Be strict. Valid syntax is not enough.
Reject if:
- any local import points to a file that is not generated
- implementation is much smaller/weaker than blueprint
- spec promises mechanics/pages/features that code does not implement
- CSS is boring/basic
- code contains TODO/handle this/add later/future updates
- game logic is duplicated/disconnected
- React app cannot run as exported
"""
    return chat_json(system, json.dumps({"blueprint": blueprint, "files": compact}, indent=2), temperature=0.1)


def repair_project_file(spec: ProjectSpec, path: str, files: dict[str, str], reason: str) -> str | None:
    blueprint = blueprint_from_spec(spec)
    compact = {p: c[:7000] for p, c in files.items()}
    existing_paths = list(files.keys())

    system = """
You are Codem8s Whole Project Repair.
Return JSON only: {"content": "full replacement file contents"}

Repair exactly the requested file so the whole project matches the blueprint.

Rules:
- No markdown.
- No placeholders.
- No TODO comments.
- No future-work notes.
- No fake functions/classes.
- Keep language correct for file extension.
- Only import local files that exist in existing_paths.
- If a helper file is missing, do not import it; define the helper locally instead.
- If game, implement complete playable mechanics promised in the blueprint.
- If tower defense, include wave spawning, enemies following a path, towers firing, upgrades, scoring/currency, lives, win/loss/restart.
- If React, produce valid React/Vite code.
- If CSS, make the design polished, responsive, modern.
"""
    payload = {
        "blueprint": blueprint,
        "target_path": path,
        "repair_reason": reason,
        "existing_paths": existing_paths,
        "all_files": compact,
    }
    data = chat_json(system, json.dumps(payload, indent=2), temperature=0.22)
    if data and isinstance(data.get("content"), str):
        return clean(data["content"])
    return None


def repair_project(spec: ProjectSpec, files: dict[str, str]) -> dict[str, str]:
    changed = dict(files)

    for pass_index in range(2):
        problems = local_quality_problems(spec, changed)

        review = project_review(spec, changed)
        if review and isinstance(review.get("problems"), list):
            problems.extend(review["problems"])

        if not problems:
            break

        seen: set[str] = set()
        for problem in problems[:12]:
            path = problem.get("path")
            reason = problem.get("reason", "whole project quality problem")
            if not path or path in seen or path not in changed:
                continue
            seen.add(path)
            repaired = repair_project_file(spec, path, changed, reason)
            if repaired:
                changed[path] = repaired

    return changed

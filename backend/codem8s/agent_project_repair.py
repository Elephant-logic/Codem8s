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

QUALITY_THRESHOLD = 8


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
    combined = "\n".join(files.values()).lower()

    problems.extend(missing_import_problems(files))

    for path, content in files.items():
        if path.endswith((".js", ".jsx", ".py", ".css")) and has_bad_phrase(content):
            problems.append({"path": path, "reason": "contains placeholder/basic/future-work wording"})

    size = visible_code_size(files)
    if kind == "game" and size < 14000:
        target = "frontend/src/game/GameCanvas.jsx" if "frontend/src/game/GameCanvas.jsx" in files else "frontend/src/App.jsx"
        problems.append({"path": target, "reason": f"game implementation too small for blueprint ({size} chars); rebuild fuller gameplay"})

    if "tower defense" in goal:
        required_terms = ["wave", "tower", "enemy", "upgrade", "path", "score", "currency", "lives", "range"]
        missing = [term for term in required_terms if term not in combined]
        if missing:
            problems.append({"path": "frontend/src/game/GameCanvas.jsx", "reason": "tower defense missing required mechanics: " + ", ".join(missing)})

        if "pathfinding" in spec_text and not any(term in combined for term in ["pathindex", "waypoint", "pathpoint"]):
            problems.append({"path": "frontend/src/game/GameCanvas.jsx", "reason": "blueprint asks for pathfinding/path movement but code lacks waypoint/pathIndex logic"})

        if "upgrade" in spec_text and not any(term in combined for term in ["upgradeTower", "upgrade", "level"]):
            problems.append({"path": "frontend/src/game/GameCanvas.jsx", "reason": "blueprint asks for upgrades but code lacks upgrade system"})

        if "onclick" not in combined and "addEventListener('click" not in combined and "pointer" not in combined:
            problems.append({"path": "frontend/src/game/GameCanvas.jsx", "reason": "tower defense lacks click/pointer tower placement"})

        if "usegameloop" in combined and "usegameloop(" not in combined.replace("function usegameloop", ""):
            problems.append({"path": "frontend/src/game/GameCanvas.jsx", "reason": "game loop file exists but is not integrated into the game canvas"})

    if "snake" in goal:
        combined_snake = combined.replace("game over", "gameover")
        required_terms = ["food", "score", "collision", "restart", "gameover"]
        missing = [term for term in required_terms if term not in combined_snake]
        if missing:
            problems.append({"path": "frontend/src/game/GameCanvas.jsx", "reason": "snake game missing required mechanics: " + ", ".join(missing)})

    if "frontend/src/styles.css" in files:
        css = files["frontend/src/styles.css"].lower()
        if len(css) < 2200 or ("linear-gradient" not in css and "box-shadow" not in css):
            problems.append({"path": "frontend/src/styles.css", "reason": "visual design is too basic; create polished responsive game/app styling"})

    return problems


def project_score(spec: ProjectSpec, files: dict[str, str]) -> dict[str, Any]:
    blueprint = blueprint_from_spec(spec)
    compact = {path: content[:9000] for path, content in files.items()}
    system = """
You are Codem8s Quality Scorer.
Return JSON only:
{
  "score": 1-10,
  "verdict": "string",
  "weak_files": [{"path": "string", "reason": "string"}],
  "must_rebuild": boolean
}

Be brutally strict. Score below 8 if the project is only a minimal implementation.
For games, require complete playable mechanics, UI state, polished styling, coherent imports, and feature depth.
For tower defense, require:
- path or waypoint movement
- wave management
- enemies
- towers
- shooting/projectiles or damage logic
- placement interaction
- upgrades
- currency/score/lives
- restart/win/loss
- code that works together
"""
    data = chat_json(system, json.dumps({"blueprint": blueprint, "files": compact}, indent=2), temperature=0.05)
    if not data:
        return {"score": 5, "verdict": "No scorer response", "weak_files": [], "must_rebuild": True}
    return data


def rebuild_file(spec: ProjectSpec, path: str, files: dict[str, str], reason: str, mode: str = "repair") -> str | None:
    blueprint = blueprint_from_spec(spec)
    compact = {p: c[:9000] for p, c in files.items()}
    existing_paths = list(files.keys())

    system = f"""
You are Codem8s Senior Builder.
Return JSON only: {{"content": "full replacement file contents"}}

MODE: {mode}
Target file: {path}

Do not patch tiny bits. Rebuild the file so the whole project deserves at least 8/10.

Rules:
- No markdown.
- No placeholders.
- No TODO/future-work comments.
- No fake imports.
- Only import local files that exist in existing_paths.
- If a helper is missing, define it in this file.
- Keep language correct for file extension.
- Make imports match.
- Make the file coherent with all other files.

If this is tower defense:
- Implement waypoint/path movement.
- Implement wave spawning with timers/counts.
- Implement enemy health/speed/reward.
- Implement tower placement by click/pointer.
- Implement tower range, cooldown, targeting, damage/projectiles or direct damage.
- Implement upgrades with cost and level.
- Implement score/currency/lives/wave/game-over/restart.
- Do not leave important logic as comments.
"""
    payload = {
        "blueprint": blueprint,
        "target_path": path,
        "reason": reason,
        "existing_paths": existing_paths,
        "all_files": compact,
    }
    data = chat_json(system, json.dumps(payload, indent=2), temperature=0.24)
    if data and isinstance(data.get("content"), str):
        return clean(data["content"])
    return None


def repair_project(spec: ProjectSpec, files: dict[str, str]) -> dict[str, str]:
    changed = dict(files)

    # First fix obvious local problems.
    for _ in range(2):
        problems = local_quality_problems(spec, changed)
        if not problems:
            break
        seen: set[str] = set()
        for problem in problems[:12]:
            path = problem.get("path")
            reason = problem.get("reason", "quality problem")
            if not path or path in seen or path not in changed:
                continue
            seen.add(path)
            rebuilt = rebuild_file(spec, path, changed, reason, mode="targeted repair")
            if rebuilt:
                changed[path] = rebuilt

    # Then score the whole project. If it is still weak, rebuild the main experience files.
    score = project_score(spec, changed)
    try:
        value = int(score.get("score", 0))
    except Exception:
        value = 0

    weak_files = score.get("weak_files") if isinstance(score.get("weak_files"), list) else []
    must_rebuild = bool(score.get("must_rebuild")) or value < QUALITY_THRESHOLD

    if must_rebuild:
        candidate_paths = []
        for weak in weak_files:
            p = weak.get("path") if isinstance(weak, dict) else None
            if p in changed:
                candidate_paths.append(p)

        # Force main files for games. These are the ones that determine whether it feels high-end.
        if "frontend/src/game/GameCanvas.jsx" in changed:
            candidate_paths.insert(0, "frontend/src/game/GameCanvas.jsx")
        if "frontend/src/App.jsx" in changed:
            candidate_paths.append("frontend/src/App.jsx")
        if "frontend/src/styles.css" in changed:
            candidate_paths.append("frontend/src/styles.css")

        seen = set()
        for path in candidate_paths[:8]:
            if path in seen or path not in changed:
                continue
            seen.add(path)
            reason = f"Project quality score {value}/10: {score.get('verdict', 'below threshold')}"
            rebuilt = rebuild_file(spec, path, changed, reason, mode="full quality rebuild")
            if rebuilt:
                changed[path] = rebuilt

    # Final import/comment pass.
    for _ in range(1):
        problems = local_quality_problems(spec, changed)
        seen = set()
        for problem in problems[:8]:
            path = problem.get("path")
            reason = problem.get("reason", "final coherence issue")
            if not path or path in seen or path not in changed:
                continue
            seen.add(path)
            rebuilt = rebuild_file(spec, path, changed, reason, mode="final coherence repair")
            if rebuilt:
                changed[path] = rebuilt

    return changed

from __future__ import annotations

import json
import re
from typing import Any

from .agent_llm import chat_json
from .agent_blueprint import blueprint_from_spec
from .models import ProjectSpec


BASIC_BANNED = [
    "todo",
    "placeholder",
    "your code here",
    "sample only",
    "demo only",
    "basic example",
    "square demo",
    "coming soon",
    "lorem ipsum",
    "add score or reward logic here",
]

CSHARP_MARKERS = [
    "using UnityEngine",
    "MonoBehaviour",
    "GameObject",
    "Vector3",
    "public class",
    "void Start()",
    "void Update()",
    "GetComponent<",
    "Collider",
    "Raycast",
]

DANGEROUS_UNDEFINED_GAME_CALLS = [
    ".getPosition(",
    ".attack(",
    ".isAlive(",
    ".takeDamage(",
    ".getRange(",
    ".getDamage(",
    ".moveAlongPath(",
    ".findPath(",
    ".spawnEnemy(",
    ".upgradeTower(",
]


JS_REQUIRED_HINT = """
The requested file is JavaScript/React.
Use valid JavaScript or JSX only.
Do not output Unity C#.
Do not use MonoBehaviour, GameObject, Vector3, public class, void Start, void Update, or using UnityEngine.

Important self-contained rule:
Do not call made-up object methods like tower.getPosition(), tower.attack(enemy), enemy.isAlive(), enemy.takeDamage().
Use plain object properties and local functions instead, for example tower.x, tower.y, tower.range, enemy.health.
If you need a helper, define it in this file or import it from a generated file that exists.
"""

PY_REQUIRED_HINT = """
The requested file is Python.
Use valid Python only.
Do not output JavaScript, JSX, TypeScript, Unity or C#.
"""

CSS_REQUIRED_HINT = """
The requested file is CSS.
Use valid CSS only.
Do not output JavaScript, Python, Unity or C#.
"""


def expected_language(path: str) -> str:
    if path.endswith(".jsx"):
        return "jsx"
    if path.endswith(".js"):
        return "javascript"
    if path.endswith(".py"):
        return "python"
    if path.endswith(".css"):
        return "css"
    if path.endswith(".json"):
        return "json"
    if path.endswith(".html"):
        return "html"
    return "text"


def wrong_language_reason(path: str, code: str) -> str | None:
    lang = expected_language(path)
    low = code.lower()

    if lang in {"javascript", "jsx"}:
        for marker in CSHARP_MARKERS:
            if marker.lower() in low:
                return f"{path} must be JavaScript/React, but contains Unity/C# marker: {marker}"
        if "```" in code:
            return f"{path} contains markdown fences"
        return None

    if lang == "python":
        if "import React" in code or "export default" in code or "function " in code:
            return f"{path} must be Python, but contains JavaScript/React"
        for marker in CSHARP_MARKERS:
            if marker.lower() in low:
                return f"{path} must be Python, but contains Unity/C# marker: {marker}"
        return None

    if lang == "css":
        for marker in CSHARP_MARKERS:
            if marker.lower() in low:
                return f"{path} must be CSS, but contains Unity/C# marker: {marker}"
        if "import " in code or "export default" in code or "function " in code:
            return f"{path} must be CSS, but contains code syntax"
        return None

    return None


def undefined_reference_reason(path: str, code: str) -> str | None:
    if not path.endswith((".js", ".jsx")):
        return None

    for call in DANGEROUS_UNDEFINED_GAME_CALLS:
        if call in code:
            return f"{path} uses likely undefined game method {call}. Use plain object fields or define/import the method."

    imported_files = re.findall(r"from ['\"](\./[^'\"]+)['\"]", code)
    if path.endswith(".jsx") or path.endswith(".js"):
        for imp in imported_files:
            if imp.startswith("./game/"):
                continue
            if imp.startswith("./components/"):
                continue
            if imp in {"./App.jsx", "./styles.css"}:
                continue

    return None


def is_weak_code(path: str, code: str) -> bool:
    low = code.lower()
    if len(code.strip()) < 240 and path.endswith((".jsx", ".js", ".py", ".css")):
        return True
    if wrong_language_reason(path, code):
        return True
    if undefined_reference_reason(path, code):
        return True
    return any(term in low for term in BASIC_BANNED)


def sanitize_code(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z0-9_+-]*\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip() + "\n"


def language_instruction(path: str) -> str:
    lang = expected_language(path)
    if lang in {"javascript", "jsx"}:
        return JS_REQUIRED_HINT
    if lang == "python":
        return PY_REQUIRED_HINT
    if lang == "css":
        return CSS_REQUIRED_HINT
    return "Use the correct syntax for the requested file extension."


def repair_once(path: str, user: str, code: str, reason: str) -> str | None:
    repair_system = f"""
You are Codem8s Repair. The previous generated file was rejected.
Return JSON only with this exact shape:
{{"content": "improved full file contents"}}

REJECTION REASON:
{reason}

Critical rules:
{language_instruction(path)}

Reference rule:
Every function, method, class, variable, and import used in the file must either:
1. be defined in this file,
2. be a normal browser/React API,
3. or be imported from a file that exists in the project blueprint.

Do not call invented methods on plain objects.
For games, represent enemies/towers/player as plain objects with properties and update them with local helper functions.
"""
    repaired = chat_json(repair_system, user + "\nRejected content:\n" + code[:7000], temperature=0.2)
    if repaired and isinstance(repaired.get("content"), str):
        return sanitize_code(repaired["content"])
    return None


def build_file_with_api(path: str, spec: ProjectSpec, previous_errors: list[str] | None = None) -> str | None:
    blueprint = blueprint_from_spec(spec)

    system = f"""
You are Codem8s Builder. Generate ONE complete production-quality file.
Return JSON only with this exact shape:
{{"content": "full file contents"}}

Critical language rule:
{language_instruction(path)}

Reference rule:
Every function, method, class, variable, and import used in the file must either:
1. be defined in this file,
2. be a normal browser/React API,
3. or be imported from a file that exists in the project blueprint.

Do not call invented methods on plain objects.
For games, use plain objects like:
tower = {{x, y, range, damage, fireRate, cooldown}}
enemy = {{x, y, health, speed, pathIndex}}
Then use local helper functions like distance(a,b), updateEnemies(), updateTowers().

Rules:
- No markdown.
- No placeholders.
- No TODO comments.
- No "your code here".
- No tiny demo unless the user requested a tiny demo.
- If building a game in React/Vite, implement it in JavaScript/React/canvas, not Unity.
- If the blueprint mentions Unity but the file path is .js or .jsx, convert the idea into JavaScript/React implementation.
- If building a game, implement real gameplay: state, loop, controls, scoring, collision, restart/game-over.
- If building a frontend app, make it visually polished and responsive.
- If building backend, implement working routes and persistence.
- Use only files likely available in the generated project.
- The file must match the requested path exactly.
"""
    user = json.dumps(
        {
            "path": path,
            "expected_language": expected_language(path),
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

    for _ in range(2):
        reason = (
            wrong_language_reason(path, code)
            or undefined_reference_reason(path, code)
            or ("File was too weak/basic." if is_weak_code(path, code) else None)
        )
        if not reason:
            return code
        repaired = repair_once(path, user, code, reason)
        if not repaired:
            return None
        code = repaired

    final_reason = wrong_language_reason(path, code) or undefined_reference_reason(path, code)
    if final_reason:
        return None

    return code

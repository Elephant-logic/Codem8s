from __future__ import annotations

import json
import re
from typing import Any

from .agent_llm import chat_json
from .agent_blueprint import blueprint_from_spec
from .models import ProjectSpec

BASIC_BANNED = ["todo", "placeholder", "your code here", "sample only", "demo only", "basic example", "coming soon", "lorem ipsum"]
CSHARP_MARKERS = ["using UnityEngine", "MonoBehaviour", "GameObject", "Vector3", "public class", "void Start()", "void Update()"]


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


def js_has_jsx(code: str) -> bool:
    patterns = [r"return\s*\(?\s*<\s*[A-Za-z]", r"=>\s*\(?\s*<\s*[A-Za-z]", r"^\s*<\s*[A-Za-z]", r"<>\s*<"]
    return any(re.search(pattern, code, re.MULTILINE) for pattern in patterns)


def language_instruction(path: str) -> str:
    lang = expected_language(path)
    if lang == "jsx":
        return "React JSX component file. JSX markup is allowed. Export the component named in the topology when provided."
    if lang == "javascript":
        return "Plain JavaScript module file. JSX markup is forbidden. Export only functions, constants, classes, data, or hooks."
    if lang == "python":
        return "Python file. Use valid Python only."
    if lang == "css":
        return "CSS file. Use valid CSS only."
    return "Use valid syntax for the file extension."


def topology_for(path: str, blueprint: dict[str, Any]) -> dict[str, Any]:
    topo = blueprint.get("dependency_topology") or {}
    data = topo.get(path) if isinstance(topo, dict) else None
    return data if isinstance(data, dict) else {"imports": [], "exports": [], "role": "generated file"}


def topology_text(path: str, blueprint: dict[str, Any]) -> str:
    data = topology_for(path, blueprint)
    return json.dumps(
        {
            "role": data.get("role", "generated file"),
            "allowed_import_files": data.get("imports", []),
            "required_exports": data.get("exports", []),
            "rule": "Only import from allowed_import_files. Use required_exports exactly. Think leaf-to-root like a circuit map.",
        },
        indent=2,
    )


def wrong_language_reason(path: str, code: str) -> str | None:
    lang = expected_language(path)
    low = code.lower()
    if "```" in code:
        return f"{path} contains markdown fences"
    if lang in {"javascript", "jsx"}:
        for marker in CSHARP_MARKERS:
            if marker.lower() in low:
                return f"{path} contains wrong-language marker: {marker}"
        if lang == "javascript" and js_has_jsx(code):
            return f"{path} is .js and must not contain JSX"
    if lang == "python" and ("import React" in code or "export default" in code):
        return f"{path} must be Python, but contains frontend syntax"
    if lang == "css" and ("export default" in code or "function " in code):
        return f"{path} must be CSS, but contains code syntax"
    return None


def is_weak_code(path: str, code: str) -> bool:
    if len(code.strip()) < 160 and path.endswith((".jsx", ".js", ".py", ".css")):
        return True
    return any(term in code.lower() for term in BASIC_BANNED)


def sanitize_code(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z0-9_+-]*\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip() + "\n"


def repair_once(path: str, user: str, code: str, reason: str, blueprint: dict[str, Any]) -> str | None:
    system = f"""
You are Codem8s Repair. Return JSON only: {{"content":"full replacement file contents"}}

Rejected because: {reason}
File rule: {language_instruction(path)}
Dependency topology for this file:
{topology_text(path, blueprint)}

No markdown. No placeholders. Use only allowed local imports. Required exports must exist.
"""
    data = chat_json(system, user + "\nRejected file:\n" + code[:7000], temperature=0.16)
    if data and isinstance(data.get("content"), str):
        return sanitize_code(data["content"])
    return None


def build_file_with_api(path: str, spec: ProjectSpec, previous_errors: list[str] | None = None) -> str | None:
    blueprint = blueprint_from_spec(spec)
    system = f"""
You are Codem8s Builder. Generate ONE complete production-quality file.
Return JSON only: {{"content":"full file contents"}}

File rule: {language_instruction(path)}
Dependency topology for this file:
{topology_text(path, blueprint)}

Build like a circuit map:
- data/utils/entities feed systems
- systems feed game modules
- game modules feed UI/scenes
- scenes feed App
- do not import upward
- do not invent local imports
- make required exports exist

No markdown. No placeholders. No TODO comments. The file must match the requested path exactly.
"""
    user = json.dumps(
        {
            "path": path,
            "expected_language": expected_language(path),
            "topology_for_this_file": topology_for(path, blueprint),
            "previous_errors": previous_errors or [],
            "blueprint_summary": {"app_name": blueprint.get("app_name"), "goal": blueprint.get("goal"), "kind": blueprint.get("kind")},
        },
        indent=2,
    )
    data = chat_json(system, user, temperature=0.16)
    if not data or not isinstance(data.get("content"), str):
        return None
    code = sanitize_code(data["content"])
    for _ in range(4):
        reason = wrong_language_reason(path, code) or ("File was too weak/basic" if is_weak_code(path, code) else None)
        if not reason:
            return code
        repaired = repair_once(path, user, code, reason, blueprint)
        if not repaired:
            return None
        code = repaired
    return None if wrong_language_reason(path, code) else code

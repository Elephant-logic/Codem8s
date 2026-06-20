from __future__ import annotations

import json
import py_compile
import re
import subprocess
import tempfile
from pathlib import Path

from .agent_llm import chat_json
from .agent_blueprint import blueprint_from_spec
from .models import ProjectSpec

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text or "")


def clean(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z0-9_+-]*\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip() + "\n"


def write_project(root: Path, files: dict[str, str]) -> None:
    for path, content in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def run_cmd(cmd: list[str], cwd: Path, timeout: int = 90) -> tuple[bool, str]:
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=timeout)
        output = strip_ansi((proc.stdout or "") + "\n" + (proc.stderr or ""))
        return proc.returncode == 0, output[-16000:]
    except subprocess.TimeoutExpired as exc:
        return False, f"Command timed out: {' '.join(cmd)}\n{exc}"
    except Exception as exc:
        return False, f"Command failed: {' '.join(cmd)}\n{exc}"


def check_python(root: Path) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    for file in root.rglob("*.py"):
        try:
            py_compile.compile(str(file), doraise=True)
        except Exception as exc:
            problems.append({"path": file.relative_to(root).as_posix(), "error": str(exc)})
    return problems


def normalize_src_path(path: str) -> str:
    path = path.strip().strip('"\'')
    if path.startswith("/src/"):
        path = path[1:]
    if path.startswith("src/"):
        return "frontend/" + path
    if path.startswith("frontend/"):
        return path
    return path


def extract_missing_export_problems(output: str) -> list[dict[str, str]]:
    text = strip_ansi(output)
    problems: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    patterns = [
        r'\[MISSING_EXPORT\]\s+"(?P<name>[^"]+)"\s+is not exported by\s+"(?P<path>[^"]+)"',
        r'"(?P<name>[^"]+)"\s+is not exported by\s+"(?P<path>[^"]+)"',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            name = match.group("name")
            path = normalize_src_path(match.group("path"))
            key = (path, name)
            if key in seen:
                continue
            seen.add(key)
            problems.append({
                "path": path,
                "error": f"Missing export: {name} is not exported by {path}. Add this export or change importing files to use the file's actual export. Full build output:\n{text[-12000:]}",
                "missing_export": name,
            })
    return problems


def guess_frontend_error_file(output: str) -> str:
    text = strip_ansi(output)
    for pattern in [r"frontend/src/[A-Za-z0-9_./-]+\.(?:jsx|js|css)", r"src/[A-Za-z0-9_./-]+\.(?:jsx|js|css)"]:
        match = re.search(pattern, text)
        if match:
            return normalize_src_path(match.group(0))
    if "App.jsx" in text:
        return "frontend/src/App.jsx"
    return "frontend/src/App.jsx"


def check_frontend(root: Path) -> list[dict[str, str]]:
    frontend = root / "frontend"
    if not frontend.exists() or not (frontend / "package.json").exists():
        return []
    ok, out = run_cmd(["npm", "install", "--silent"], frontend, timeout=180)
    if not ok:
        return [{"path": "frontend/package.json", "error": "npm install failed\n" + out}]
    ok, out = run_cmd(["npm", "run", "build"], frontend, timeout=180)
    if ok:
        return []
    missing = extract_missing_export_problems(out)
    if missing:
        return missing
    return [{"path": guess_frontend_error_file(out), "error": "npm build failed\n" + out}]


def expected_file_rule(path: str) -> str:
    if path.endswith(".jsx"):
        return "React JSX component file. JSX is allowed. If default is required, include export default. If named exports are required, include them."
    if path.endswith(".js"):
        return "Plain JavaScript module file. JSX is forbidden. Export functions/classes/constants/data only. If default is required, include export default. If named exports are required, include them."
    if path.endswith(".css"):
        return "CSS only."
    if path.endswith(".py"):
        return "Python only."
    return "Correct syntax for the file extension."


def topology_for(path: str, blueprint: dict) -> dict:
    topo = blueprint.get("dependency_topology") or {}
    meta = topo.get(path) if isinstance(topo, dict) else None
    return meta if isinstance(meta, dict) else {}


def connected_group(path: str, blueprint: dict, files: dict[str, str]) -> dict:
    topo = blueprint.get("dependency_topology") or {}
    if not isinstance(topo, dict):
        topo = {}
    meta = topology_for(path, blueprint)
    imports = [p for p in meta.get("imports", []) if p in files]
    dependents = []
    for candidate, candidate_meta in topo.items():
        if isinstance(candidate_meta, dict) and path in candidate_meta.get("imports", []) and candidate in files:
            dependents.append(candidate)
    # Also infer dependents from raw source text when blueprint is stale.
    stem = path.split("/")[-1].rsplit(".", 1)[0]
    for candidate, content in files.items():
        if candidate == path or candidate in dependents:
            continue
        if stem in content and "import" in content[:2500]:
            dependents.append(candidate)
    group = []
    for item in [path, *imports, *dependents]:
        if item in files and item not in group:
            group.append(item)
    return {
        "target": path,
        "imports": imports,
        "dependents": dependents,
        "files": {p: files[p][:12000] for p in group[:12]},
        "topology": {p: topology_for(p, blueprint) for p in group[:12]},
    }


def repair_file_against_error(spec: ProjectSpec, path: str, files: dict[str, str], error: str, missing_export: str | None = None) -> str | None:
    blueprint = blueprint_from_spec(spec)
    existing_paths = list(files.keys())
    compact_files = {p: c[:3000] for p, c in files.items()}
    current = files.get(path, "")
    topology = topology_for(path, blueprint)
    group = connected_group(path, blueprint, files)

    system = f"""
You are Codem8s Dependency-Aware Build Repair.
Return JSON only: {{"content": "full replacement file contents"}}

Repair the TARGET FILE against the REAL Vite/Python build error, using its connected dependency group.

Target file: {path}
Target file rule: {expected_file_rule(path)}
Target topology contract: {json.dumps(topology, indent=2)}
Missing export to satisfy: {missing_export or "none"}

Dependency-aware rules:
- Treat the connected files as one circuit: target imports, target dependents, and topology contracts must agree.
- If a dependent imports a named/default export from the target, the target must export exactly that name/default.
- If the target imports from a neighbour, do not invent imports that neighbour does not export.
- Prefer stable named exports for app modules unless the import explicitly needs default.
- Make the smallest target-file change that makes the circuit consistent.

General rules:
- Fix the actual error, not a guess.
- No markdown.
- No placeholders.
- No TODO/future-work comments.
- Keep language correct for file extension.
- Only import files listed in existing_paths.
- Do not remove working functionality just to make the build pass.
- React/Vite files must compile.
- Python files must compile.
"""
    payload = {
        "target_path": path,
        "missing_export": missing_export,
        "existing_paths": existing_paths,
        "build_error": strip_ansi(error),
        "current_file": current[:14000],
        "connected_dependency_group": group,
        "all_files_compact_index": compact_files,
        "blueprint_summary": {"app_name": blueprint.get("app_name"), "goal": blueprint.get("goal"), "kind": blueprint.get("kind")},
    }
    data = chat_json(system, json.dumps(payload, indent=2), temperature=0.08)
    if data and isinstance(data.get("content"), str):
        return clean(data["content"])
    return None


def real_build_repair_project(spec: ProjectSpec, files: dict[str, str], max_rounds: int = 6) -> tuple[dict[str, str], list[str], bool]:
    changed = dict(files)
    logs: list[str] = []
    for round_number in range(1, max_rounds + 1):
        with tempfile.TemporaryDirectory(prefix="codem8s_build_") as tmp:
            root = Path(tmp)
            write_project(root, changed)
            problems = check_python(root)
            problems.extend(check_frontend(root))
        if not problems:
            logs.append(f"Real build check passed on round {round_number}")
            return changed, logs, True
        logs.append(f"Real build check found {len(problems)} problem(s) on round {round_number}")
        repaired_any = False
        for problem in problems[:10]:
            path = problem.get("path") or ""
            error = problem.get("error") or ""
            missing_export = problem.get("missing_export")
            if path not in changed:
                if path.startswith("frontend/") and "frontend/src/App.jsx" in changed:
                    path = "frontend/src/App.jsx"
                else:
                    logs.append(f"Could not repair missing target: {problem.get('path')}")
                    continue
            repaired = repair_file_against_error(spec, path, changed, error, missing_export=missing_export)
            if repaired:
                changed[path] = repaired
                repaired_any = True
                extra = f" export {missing_export}" if missing_export else ""
                logs.append(f"Dependency-aware repair updated {path}{extra}")
            else:
                logs.append(f"Repair failed for {path}")
        if not repaired_any:
            logs.append("Real build repair could not repair any files this round")
            return changed, logs, False
    logs.append("Real build repair stopped with remaining build problems")
    return changed, logs, False

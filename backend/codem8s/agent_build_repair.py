from __future__ import annotations

import json
import os
import py_compile
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .agent_llm import chat_json
from .agent_blueprint import blueprint_from_spec
from .models import ProjectSpec


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
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        return proc.returncode == 0, output[-12000:]
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
            rel = file.relative_to(root).as_posix()
            problems.append({"path": rel, "error": str(exc)})
    return problems


def check_frontend(root: Path) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    frontend = root / "frontend"
    if not frontend.exists() or not (frontend / "package.json").exists():
        return problems

    # npm install is needed because the temp folder is clean.
    ok, out = run_cmd(["npm", "install", "--silent"], frontend, timeout=180)
    if not ok:
        problems.append({"path": "frontend/package.json", "error": "npm install failed\n" + out})
        return problems

    ok, out = run_cmd(["npm", "run", "build"], frontend, timeout=180)
    if not ok:
        problems.append({"path": guess_frontend_error_file(out), "error": "npm build failed\n" + out})

    return problems


def guess_frontend_error_file(output: str) -> str:
    patterns = [
        r"frontend/src/[A-Za-z0-9_./-]+\.(?:jsx|js|css)",
        r"src/[A-Za-z0-9_./-]+\.(?:jsx|js|css)",
        r"([A-Za-z0-9_./-]+\.(?:jsx|js|css))",
    ]
    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            path = match.group(0)
            if path.startswith("src/"):
                return "frontend/" + path
            if path.startswith("frontend/"):
                return path
    if "App.jsx" in output:
        return "frontend/src/App.jsx"
    return "frontend/src/App.jsx"


def repair_file_against_error(spec: ProjectSpec, path: str, files: dict[str, str], error: str) -> str | None:
    blueprint = blueprint_from_spec(spec)
    existing_paths = list(files.keys())
    compact_files = {p: c[:7000] for p, c in files.items()}
    current = files.get(path, "")

    system = """
You are Codem8s Build Repair.
Return JSON only: {"content": "full replacement file contents"}

Repair the target file against the REAL build error.

Rules:
- Fix the actual error, not a guess.
- No markdown.
- No placeholders.
- No TODO/future-work comments.
- Keep language correct for file extension.
- Only import files listed in existing_paths.
- If an imported helper does not exist, remove the import and define the helper locally.
- React/Vite files must compile.
- Python files must compile.
- Keep the app feature-complete according to the blueprint.
"""
    payload = {
        "blueprint": blueprint,
        "target_path": path,
        "existing_paths": existing_paths,
        "build_error": error,
        "current_file": current[:12000],
        "all_files": compact_files,
    }
    data = chat_json(system, json.dumps(payload, indent=2), temperature=0.16)
    if data and isinstance(data.get("content"), str):
        return clean(data["content"])
    return None


def real_build_repair_project(spec: ProjectSpec, files: dict[str, str], max_rounds: int = 3) -> tuple[dict[str, str], list[str]]:
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
            return changed, logs

        logs.append(f"Real build check found {len(problems)} problem(s) on round {round_number}")

        repaired_any = False
        for problem in problems[:5]:
            path = problem.get("path") or ""
            error = problem.get("error") or ""
            if path not in changed:
                # Try App.jsx for unknown frontend errors.
                if path.startswith("frontend/") and "frontend/src/App.jsx" in changed:
                    path = "frontend/src/App.jsx"
                else:
                    logs.append(f"Could not repair missing target: {problem.get('path')}")
                    continue

            repaired = repair_file_against_error(spec, path, changed, error)
            if repaired:
                changed[path] = repaired
                repaired_any = True
                logs.append(f"Repaired {path} from real build error")
            else:
                logs.append(f"Repair failed for {path}")

        if not repaired_any:
            break

    logs.append("Real build repair stopped with remaining build problems")
    return changed, logs

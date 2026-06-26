from __future__ import annotations

import json
from dataclasses import dataclass

from .agent_llm import chat_json
from .models import BuildState
from .project_importer import build_topology, refactor_file_with_ai

MAX_FILES_TO_EDIT = 6


@dataclass
class CommandResult:
    changed_files: list[str]
    notes: list[str]


def _short_file_summary(path: str, content: str, meta: dict) -> dict:
    return {
        "path": path,
        "role": meta.get("role", "project file"),
        "imports": meta.get("imports", [])[:12],
        "dependents": meta.get("dependents", [])[:12],
        "exports": meta.get("exports", [])[:12],
        "lines": meta.get("lines", 0),
        "head": content[:1800],
    }


def plan_command(state: BuildState, instruction: str, selected_path: str | None = None) -> dict:
    files = {path: item.content for path, item in state.files.items() if item.content}
    topology = build_topology(files)
    summaries = [_short_file_summary(path, files[path], topology.get(path, {})) for path in sorted(files)[:140]]
    system = """
You are Codem8s command planner. Return JSON only.
Choose the smallest safe set of existing files to edit for the user's request.
Do not invent files unless the request clearly needs a new file.
Prefer the selected file when it is relevant.
Return shape: {"mode":"selected_file|multi_file|plan_only|run_only", "files":["path"], "notes":["short note"], "run_after":true|false}
"""
    data = chat_json(system, json.dumps({
        "instruction": instruction,
        "selected_path": selected_path,
        "project": {"name": state.spec.app_name, "goal": state.spec.goal, "stack": state.spec.stack},
        "files": summaries,
    }, indent=2), temperature=0.05)
    if not data:
        fallback_files = [selected_path] if selected_path and selected_path in files else []
        if not fallback_files:
            lower = instruction.lower()
            for path in files:
                if any(token in path.lower() for token in ["app", "index", "main", "style", "css", "html"]):
                    fallback_files.append(path)
                    break
        return {"mode": "selected_file" if fallback_files else "plan_only", "files": fallback_files[:1], "notes": ["Used fallback command planning."], "run_after": any(w in instruction.lower() for w in ["run", "preview", "build", "show", "make it work"])}
    files_to_edit = [p for p in data.get("files", []) if isinstance(p, str) and p in files]
    data["files"] = files_to_edit[:MAX_FILES_TO_EDIT]
    data["notes"] = [str(n) for n in data.get("notes", [])[:8]]
    data["run_after"] = bool(data.get("run_after")) or any(w in instruction.lower() for w in ["run", "preview", "build", "show", "make it work"])
    return data


def apply_project_command(state: BuildState, instruction: str, selected_path: str | None = None) -> CommandResult:
    plan = plan_command(state, instruction, selected_path=selected_path)
    changed: list[str] = []
    notes = list(plan.get("notes") or [])
    files = {path: item.content for path, item in state.files.items() if item.content}
    for path in plan.get("files", [])[:MAX_FILES_TO_EDIT]:
        if path not in state.files:
            continue
        before = state.files[path].content
        edit_instruction = f"{instruction}\n\nYou are editing {path} as part of a project command. Keep the public API stable unless the request requires otherwise."
        try:
            after = refactor_file_with_ai(files, path, edit_instruction)
        except Exception as exc:
            notes.append(f"Skipped {path}: {exc}")
            continue
        if after and after != before:
            state.files[path].content = after
            state.files[path].status = "valid"
            state.files[path].errors = []
            files[path] = after
            changed.append(path)
    if not changed and selected_path and selected_path in state.files:
        try:
            after = refactor_file_with_ai(files, selected_path, instruction)
            if after and after != state.files[selected_path].content:
                state.files[selected_path].content = after
                state.files[selected_path].status = "valid"
                state.files[selected_path].errors = []
                changed.append(selected_path)
        except Exception as exc:
            notes.append(f"Selected-file edit failed: {exc}")
    return CommandResult(changed_files=changed, notes=notes or ["Command processed."])

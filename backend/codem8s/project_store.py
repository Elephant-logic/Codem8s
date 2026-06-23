from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

from .models import BuildState

DEFAULT_DATA_DIR = Path(os.getenv("CODEM8S_DATA_DIR", "/data/codem8s"))
STORE_DIR = DEFAULT_DATA_DIR / "projects"
LEGACY_STORE_DIR = Path("/opt/render/.codem8s/projects")
FALLBACK_DIR = Path("/tmp/codem8s_projects")


def store_dir() -> Path:
    for candidate in [STORE_DIR, LEGACY_STORE_DIR, FALLBACK_DIR]:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test = candidate / ".write_test"
            test.write_text("ok", encoding="utf-8")
            test.unlink(missing_ok=True)
            return candidate
        except Exception:
            continue
    FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    return FALLBACK_DIR


def candidate_dirs() -> list[Path]:
    seen: set[str] = set()
    dirs: list[Path] = []
    for candidate in [store_dir(), STORE_DIR, LEGACY_STORE_DIR, FALLBACK_DIR]:
        key = str(candidate)
        if key not in seen and candidate.exists():
            seen.add(key)
            dirs.append(candidate)
    return dirs


def _path(project_id: str) -> Path:
    safe = "".join(ch for ch in project_id if ch.isalnum() or ch in "-_")
    return store_dir() / f"{safe}.json"


def _dump_model(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def _load_path(path: Path) -> BuildState | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if hasattr(BuildState, "model_validate"):
            return BuildState.model_validate(data)
        return BuildState.parse_obj(data)
    except Exception:
        return None


def save_project(state: BuildState) -> None:
    data = _dump_model(state)
    _path(state.project_id).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_latest_project() -> BuildState | None:
    files: list[Path] = []
    for directory in candidate_dirs():
        files.extend(directory.glob("*.json"))
    files = sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)
    for path in files:
        state = _load_path(path)
        if state:
            state.logs.append("Recovered latest saved project from persistent project store")
            save_project(state)
            return state
    return None


def load_project(project_id: str) -> BuildState | None:
    safe = "".join(ch for ch in project_id if ch.isalnum() or ch in "-_")
    for directory in candidate_dirs():
        path = directory / f"{safe}.json"
        if path.exists():
            state = _load_path(path)
            if state:
                save_project(state)
                return state
    return load_latest_project()


def load_all_projects() -> Dict[str, BuildState]:
    projects: Dict[str, BuildState] = {}
    for directory in candidate_dirs():
        for path in directory.glob("*.json"):
            state = _load_path(path)
            if state:
                projects[state.project_id] = state
    return projects

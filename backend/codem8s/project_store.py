from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from .models import BuildState

STORE_DIR = Path('/opt/render/.codem8s/projects')
FALLBACK_DIR = Path('/tmp/codem8s_projects')


def store_dir() -> Path:
    try:
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        test = STORE_DIR / '.write_test'
        test.write_text('ok', encoding='utf-8')
        test.unlink(missing_ok=True)
        return STORE_DIR
    except Exception:
        FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
        return FALLBACK_DIR


def _path(project_id: str) -> Path:
    safe = ''.join(ch for ch in project_id if ch.isalnum() or ch in '-_')
    return store_dir() / f'{safe}.json'


def _dump_model(model) -> dict:
    if hasattr(model, 'model_dump'):
        return model.model_dump(mode='json')
    return json.loads(model.json())


def save_project(state: BuildState) -> None:
    data = _dump_model(state)
    _path(state.project_id).write_text(json.dumps(data, indent=2), encoding='utf-8')


def load_project(project_id: str) -> BuildState | None:
    path = _path(project_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if hasattr(BuildState, 'model_validate'):
            return BuildState.model_validate(data)
        return BuildState.parse_obj(data)
    except Exception:
        return None


def load_all_projects() -> Dict[str, BuildState]:
    projects: Dict[str, BuildState] = {}
    for path in store_dir().glob('*.json'):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if hasattr(BuildState, 'model_validate'):
                state = BuildState.model_validate(data)
            else:
                state = BuildState.parse_obj(data)
            projects[state.project_id] = state
        except Exception:
            continue
    return projects
